"""
backfill_explanations.py
------------------------
Generates explanations for existing questions that don't have one.
Run after generate_questions.py has been used to create questions.

Usage:
    python backfill_explanations.py
"""

import sqlite3
import os
import json
import time
import re
import requests
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"
DB_PATH      = "quiz.db"
DELAY        = 2   # seconds between requests
MAX_RETRY    = 5
BATCH        = 100  # questions per run — increase if quota allows


def call_groq(prompt):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GROQ_API_KEY}"
    }
    body = {
        "model": "meta-llama/llama-4-scout-17b-16e-instruct",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5,
        "max_tokens": 1024
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
        if not text:
            raise Exception("Empty response from API")
        return text

    raise Exception("Max retries exceeded")


def build_explanation_prompt(question, choice_a, choice_b, choice_c, choice_d, correct_answer):
    return f"""Given this multiple choice question, explain in 1-2 clear sentences why the correct answer is correct.
Do not use any quotation marks in your explanation.

Question: {question}
A) {choice_a}
B) {choice_b}
C) {choice_c}
D) {choice_d}
Correct Answer: {correct_answer}

Return ONLY a JSON object, no markdown:
{{"explanation": "Your 1-2 sentence explanation here without any quotation marks"}}"""


def backfill(db_path=DB_PATH, limit=BATCH):
    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()

    # Ensure explanation column exists
    try:
        cur.execute("ALTER TABLE questions ADD COLUMN explanation TEXT DEFAULT NULL")
        conn.commit()
        print("Added explanation column")
    except Exception:
        pass

    # Fetch questions without explanations
    cur.execute("""
        SELECT id, question, choice_a, choice_b, choice_c, choice_d, answer
        FROM questions
        WHERE (explanation IS NULL OR explanation = '')
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()

    if not rows:
        print("All questions already have explanations!")
        conn.close()
        return

    print(f"Generating explanations for {len(rows)} questions...\n")
    updated = 0

    for i, row in enumerate(rows):
        qid, question, a, b, c, d, answer = row
        print(f"  [{i+1}/{len(rows)}] Q{qid}...", end=" ", flush=True)

        try:
            prompt = build_explanation_prompt(question, a, b, c, d, answer)
            text   = call_groq(prompt)

            # Parse JSON response
            text = re.sub(r'```json|```', '', text).strip()
            start = text.find("{")
            end   = text.rfind("}") + 1
            text  = text[start:end]
            # Fix invalid escape sequences
            text  = re.sub(r'\\([^"\\/bfnrtu])', lambda m: m.group(1), text)
            # Remove control characters
            text  = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
            # Fix unterminated strings by removing smart quotes
            text  = text.replace('\u201c', '"').replace('\u201d', '"').replace('\u2019', "'").replace('\u2018', "'")
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                # Last resort — extract explanation with regex
                match = re.search(r'"explanation"\s*:\s*"([^"]+)"', text)
                if match:
                    data = {"explanation": match.group(1)}
                else:
                    raise
            explanation = data.get("explanation", "").strip()

            if explanation:
                cur.execute("UPDATE questions SET explanation=? WHERE id=?", (explanation, qid))
                conn.commit()
                updated += 1
                print(f"✓")
            else:
                print(f"✗ Empty explanation")

        except Exception as e:
            print(f"✗ Error: {e}")

        time.sleep(DELAY)

    conn.close()
    print(f"\n✅ Done! {updated}/{len(rows)} explanations added.")
    print(f"Run again to continue with remaining questions.")


if __name__ == "__main__":
    backfill()