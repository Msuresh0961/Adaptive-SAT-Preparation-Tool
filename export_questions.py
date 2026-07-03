"""
Run this locally (where your quiz.db already has questions in it) to export
the questions table into questions_seed.json. Commit that JSON file to git --
it contains no user data, only question content, so it's safe to share.

On startup, db.py's seed_questions_if_empty() will automatically load this
file into a fresh/empty database (e.g. a new Railway volume).

Usage:
    python export_questions.py
"""
import json
import sqlite3
from db import DB_PATH

OUTPUT_FILE = "questions_seed.json"

FIELDS = [
    "question", "choice_a", "choice_b", "choice_c", "choice_d",
    "answer", "category", "difficulty", "mode", "question_type",
    "explanation", "ai_generated", "test_number",
]


def main():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute(f"SELECT {', '.join(FIELDS)} FROM questions")
    rows = [dict(row) for row in cur.fetchall()]
    con.close()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)

    print(f"Exported {len(rows)} questions to {OUTPUT_FILE}")
    print("Now git add / commit / push this file.")


if __name__ == "__main__":
    main()