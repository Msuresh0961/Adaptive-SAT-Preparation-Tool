import sqlite3
import csv
import json
import sys
import os

# Path to the SQLite database file
DB_PATH = "quiz.db"


def import_from_csv(filepath):
    """Import questions from a CSV file into the database.

    Expected CSV columns (with header row):
        question, answer, category, difficulty, mode, question_type,
        choice_a, choice_b, choice_c, choice_d

    - difficulty must be: easy, medium, or hard
    - mode must be: quick or sat
    - question_type must be: text or multiple_choice
    - choice_a/b/c/d are only required when question_type is multiple_choice
    - answer for multiple_choice should be the letter: A, B, C, or D

    Example CSV row for a multiple choice SAT question:
        "Which word is closest in meaning to 'benevolent'?",A,SAT Reading,medium,sat,multiple_choice,Kind,Cruel,Lazy,Loud
    """
    if not os.path.exists(filepath):
        print(f"Error: file not found at {filepath}")
        return

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    saved = 0
    skipped = 0

    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            # Skip rows where the question already exists in the database
            cur.execute("SELECT id FROM questions WHERE question = ?", (row["question"],))
            if cur.fetchone():
                skipped += 1
                continue

            cur.execute(
                """INSERT INTO questions
                   (question, answer, category, difficulty, mode, question_type,
                    choice_a, choice_b, choice_c, choice_d)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    row["question"],
                    row["answer"],
                    row.get("category", "General"),
                    row.get("difficulty", "medium"),
                    row.get("mode", "sat"),
                    row.get("question_type", "multiple_choice"),
                    row.get("choice_a"),
                    row.get("choice_b"),
                    row.get("choice_c"),
                    row.get("choice_d"),
                )
            )
            saved += 1

    con.commit()
    con.close()
    print(f"Import complete: {saved} added, {skipped} duplicates skipped.")


def import_from_json(filepath):
    """Import questions from a JSON file into the database.

    Expected JSON format — a list of objects:
    [
        {
            "question":      "Which word means happy?",
            "answer":        "A",
            "category":      "SAT Reading",
            "difficulty":    "easy",
            "mode":          "sat",
            "question_type": "multiple_choice",
            "choice_a":      "Joyful",
            "choice_b":      "Angry",
            "choice_c":      "Tired",
            "choice_d":      "Bored"
        },
        ...
    ]
    """
    if not os.path.exists(filepath):
        print(f"Error: file not found at {filepath}")
        return

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    saved = 0
    skipped = 0

    with open(filepath, encoding="utf-8") as f:
        questions = json.load(f)

    for row in questions:
        # Skip rows where the question already exists in the database
        cur.execute("SELECT id FROM questions WHERE question = ?", (row["question"],))
        if cur.fetchone():
            skipped += 1
            continue

        cur.execute(
            """INSERT INTO questions
               (question, answer, category, difficulty, mode, question_type,
                choice_a, choice_b, choice_c, choice_d)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row["question"],
                row["answer"],
                row.get("category", "General"),
                row.get("difficulty", "medium"),
                row.get("mode", "sat"),
                row.get("question_type", "multiple_choice"),
                row.get("choice_a"),
                row.get("choice_b"),
                row.get("choice_c"),
                row.get("choice_d"),
            )
        )
        saved += 1

    con.commit()
    con.close()
    print(f"Import complete: {saved} added, {skipped} duplicates skipped.")


# ── Run from command line ──────────────────────────────────────
# Usage:
#   python import_questions.py sat_questions.csv
#   python import_questions.py sat_questions.json

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python import_questions.py <filename.csv or filename.json>")
        sys.exit(1)

    filepath = sys.argv[1]

    if filepath.endswith(".csv"):
        import_from_csv(filepath)
    elif filepath.endswith(".json"):
        import_from_json(filepath)
    else:
        print("Error: only .csv and .json files are supported.")