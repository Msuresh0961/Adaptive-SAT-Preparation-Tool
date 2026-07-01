"""
generate_questions.py
---------------------
Manually generate SAT/Quick quiz questions using Gemini and insert into quiz.db.

Usage:
    python generate_questions.py --mode sat --category "Math" --difficulty medium --count 50
    python generate_questions.py --mode quick --count 50
    python generate_questions.py --test 2
"""

import argparse
from itertools import count
import json
import sqlite3
import time
import os
from unicodedata import category
import requests
from dotenv import load_dotenv
import re

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

DB_PATH    = "quiz.db"
BATCH_SIZE = 10
DELAY      = 15   # seconds between batches
MAX_RETRY  = 5    # max retries on 429

SAT_RW_CATEGORIES = [
    "Information and Ideas",
    "Craft and Structure",
    "Expression of Ideas",
    "Standard English Conventions",
]

SAT_MATH_CATEGORIES = [
    "Algebra",
    "Advanced Math",
    "Problem-Solving and Data Analysis",
    "Geometry and Trigonometry",
]


def build_prompt(mode, category, difficulty, count, previous=[]):
    is_math = category in SAT_MATH_CATEGORIES or category == "Math"
    subject_note = f"SAT-style {'Math' if is_math else 'Reading and Writing'}" if mode != "quick" else "general knowledge trivia"

    avoid = ""
    if previous:
        avoid = f"\nDo NOT generate questions similar to these:\n" + "\n".join(f"- {q}" for q in previous[-10:])

    if is_math:
        type_note = """- Questions must be self-contained math problems
- You MUST wrap every math expression, equation, variable, and number used in math context in dollar signs
- Examples: '$2x + 5 = 11$', '$f(x) = 3x^2 - 2x + 1$', '$x = 4$', '$\\frac{1}{2}$'
- NEVER write math without dollar signs: wrong: '2x + 5 = 11', correct: '$2x + 5 = 11$'
- Every choice_a, choice_b, choice_c, choice_d that contains math must also use dollar signs
- NEVER generate questions involving limits, derivatives, integrals, matrices, or complex numbers
- Only use SAT Math topics: algebra, functions, geometry, trigonometry, statistics"""

    else:
        type_note = f"""- Each question MUST include a short self-contained passage (2-4 sentences) followed by one question about it
- The passage and question together must be fully self-contained
- For category '{category}', focus on: """ + {
            "Information and Ideas": "main idea, inference, evidence, central claim",
            "Craft and Structure": "word choice, text structure, author purpose, point of view",
            "Expression of Ideas": "transitions, sentence clarity, adding/removing information, organization",
            "Standard English Conventions": "grammar, punctuation, verb tense, subject-verb agreement — include a sentence with a blank or underline for the student to fix"
        }.get(category, "reading comprehension") + """
- Cover diverse topics: science, history, literature, social studies, culture
- Never reference external texts"""

    return f"""Generate {count} UNIQUE {subject_note} multiple choice questions about {category}.
Difficulty: {difficulty}
Rules:
- Exactly 4 options (A, B, C, D), one correct answer
- Each question must be completely different
- No markdown, no special characters
{type_note}
{avoid}
Also include a brief explanation (1-2 sentences) of why the correct answer is right.

Return ONLY a JSON array, no markdown:
[{{"question":"...","choice_a":"...","choice_b":"...","choice_c":"...","choice_d":"...","correct_answer":"A","explanation":"Brief explanation of why A is correct","category":"{category}","difficulty":"{difficulty}"}}]"""
def call_gemini(prompt):
    """Call Groq API with automatic retry on rate limit errors."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GROQ_API_KEY}"
    }
    body = {
        "model": "meta-llama/llama-4-scout-17b-16e-instruct",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 1.2,
        "max_tokens": 2048
    }

    for attempt in range(1, MAX_RETRY + 1):
        resp = requests.post(GROQ_URL, headers=headers, json=body, timeout=60)

        if resp.status_code in (429, 503):
            wait = 30 * attempt
            print(f"\n  ⏳ Rate limited. Waiting {wait}s (attempt {attempt}/{MAX_RETRY})...", end=" ", flush=True)
            time.sleep(wait)
            continue

        if resp.status_code != 200:
            raise Exception(f"API error {resp.status_code}: {resp.text}")

        text = resp.json()["choices"][0]["message"]["content"].strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip().rstrip("```").strip()
        start = text.find("[")
        end   = text.rfind("]") + 1
        text  = text[start:end]
        print(f"\n  DEBUG: {text[:200]}")  # add this line
        # Only remove backslashes before single characters that are truly invalid JSON escapes
# Leave anything that looks like it could be a LaTeX command
        # Step 1: replace raw string to avoid Python interpreting \f, \t etc
        text = text.replace('\\\\', '§§DOUBLE§§')  # protect already-doubled backslashes
        text = text.replace('\\', '\\\\')           # double all single backslashes
        text = text.replace('§§DOUBLE§§', '\\\\')  # restore doubled ones (now correct)
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)  # remove control chars
        return json.loads(text)
    
    
    raise Exception("Max retries exceeded")


def insert_questions(questions, mode, test_number=None, db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()

    for col in ["ai_generated INTEGER DEFAULT 0", "test_number INTEGER DEFAULT NULL"]:
        try:
            cur.execute(f"ALTER TABLE questions ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass

    inserted = 0
    for q in questions:
        try:
        # Check if question already exists
            cur.execute("SELECT id FROM questions WHERE question = ?", (q["question"].strip(),))
            if cur.fetchone():
                continue  # skip duplicate
            cur.execute("""
                INSERT INTO questions
                    (question, choice_a, choice_b, choice_c, choice_d,
                    answer, category, difficulty, mode, question_type,
                    ai_generated, test_number, explanation)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'multiple_choice', 1, ?, ?)
            """, (
                q["question"].strip(),
                q["choice_a"].strip(),
                q["choice_b"].strip(),
                q["choice_c"].strip(),
                q["choice_d"].strip(),
                q["correct_answer"].strip().upper(),
                q.get("category", "General"),
                q.get("difficulty", "medium"),
                mode,
                test_number,
                q.get("explanation", "").strip() if q.get("explanation") else None,
))
            inserted += 1
        except Exception as e:
            print(f"  ⚠ Skipping question: {e}")

    conn.commit()
    conn.close()
    return inserted




def generate(mode, category, difficulty, total_count, test_number=None, db_path=DB_PATH):
    print(f"\n🔄 {mode} | {category} | {difficulty} | {total_count} questions")
    total_inserted = 0
    batches = (total_count + BATCH_SIZE - 1) // BATCH_SIZE

    # Load existing questions from DB to avoid repeats
    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()
    cur.execute("SELECT question FROM questions WHERE mode=? AND category IN ('Math', 'Reading and Writing', ?)", (mode, category))
    previous_questions = [row[0][:80] for row in cur.fetchall()]  # first 80 chars
    conn.close()

    print(f"  (Loaded {len(previous_questions)} existing questions to avoid)")

    for batch_num in range(batches):
        remaining = total_count - total_inserted
        count     = min(BATCH_SIZE, remaining)
        print(f"  Batch {batch_num + 1}/{batches} ({count} questions)...", end=" ", flush=True)

        try:
            prompt    = build_prompt(mode, category, difficulty, count, previous_questions)
            questions = call_gemini(prompt)
            inserted  = insert_questions(questions, mode, test_number, db_path)
            total_inserted += inserted
            previous_questions.extend([q["question"][:80] for q in questions])
            print(f"✓ {inserted} inserted (total: {total_inserted})")
        except Exception as e:
            print(f"✗ Failed: {e} — skipping batch")

        if batch_num < batches - 1:
            time.sleep(DELAY)

    return total_inserted


def generate_full_test(test_number, db_path=DB_PATH):
    """Generate all questions for one complete practice test."""
    print(f"\n📋 Generating Full Practice Test {test_number}")
    print("=" * 50)

    specs = [
        (SAT_RW_CATEGORIES,   "medium", 27),
        (SAT_RW_CATEGORIES,   "easy",   27),
        (SAT_RW_CATEGORIES,   "hard",   27),
        (SAT_MATH_CATEGORIES, "medium", 27),
        (SAT_MATH_CATEGORIES, "easy",   27),
        (SAT_MATH_CATEGORIES, "hard",   27),
    ]

    total_inserted = 0
    for categories, difficulty, count in specs:
        per_cat = max(1, count // len(categories))
        for cat in categories:
            inserted = generate(
                mode="full_test",
                category=cat,
                difficulty=difficulty,
                total_count=per_cat,
                test_number=test_number,
                db_path=db_path
            )
            total_inserted += inserted
            time.sleep(DELAY)

    print(f"\n🎉 Practice Test {test_number} complete! {total_inserted} questions inserted.")
    return total_inserted


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate quiz questions with Gemini AI")
    parser.add_argument("--mode",       default="sat",    choices=["quick", "sat", "full_test"])
    parser.add_argument("--category",   default="Math")
    parser.add_argument("--difficulty", default="medium", choices=["easy", "medium", "hard"])
    parser.add_argument("--count",      type=int, default=50)
    parser.add_argument("--test",       type=int, default=None, help="Generate full practice test (1-5)")
    parser.add_argument("--db",         default=DB_PATH)
    args = parser.parse_args()

    if not GROQ_API_KEY:
        print("❌ GROQ _API_KEY not found.")
        exit(1)

    if args.mode == "full_test" and args.test:
        generate_full_test(test_number=args.test, db_path=args.db)
    else:
        total = generate(
            mode=args.mode,
            category=args.category,
            difficulty=args.difficulty,
            total_count=args.count,
            test_number=args.test,
            db_path=args.db
        )
        print(f"\n✅ Done! {total} questions inserted.")