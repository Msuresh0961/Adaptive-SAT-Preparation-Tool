import pandas as pd
import csv
import re

df = pd.read_parquet("0000.parquet")
print(f"Total rows: {len(df)}")

questions = []
skipped = 0

for i in range(len(df)):
    try:
        row = df.iloc[i]
        query = str(row["query"])
        choices = list(row["choices"])
        gold = list(row["gold"])

        # Convert numpy int64 to plain Python int
        gold_idx = int(gold[0])

        if len(choices) < 4 or gold_idx > 3:
            skipped += 1
            continue

        # Extract question text before "Answer Choices:"
        q_match = re.search(r'Q:\s*(.*?)Answer Choices:', query, re.DOTALL)
        if not q_match:
            skipped += 1
            continue

        question_text = re.sub(r'\s+', ' ', q_match.group(1)).strip()

        if len(question_text) < 10:
            skipped += 1
            continue

        answer_letter = ["A", "B", "C", "D"][gold_idx]

        def clean_choice(c):
            return re.sub(r'^\([ABCD]\)\s*', '', str(c)).strip()

        questions.append({
            "question":      question_text,
            "answer":        answer_letter,
            "category":      "Math",
            "difficulty":    "medium",
            "mode":          "sat",
            "question_type": "multiple_choice",
            "choice_a":      clean_choice(choices[0]),
            "choice_b":      clean_choice(choices[1]),
            "choice_c":      clean_choice(choices[2]),
            "choice_d":      clean_choice(choices[3]),
        })

    except Exception as e:
        print(f"Row {i} error: {e}")
        skipped += 1

print(f"Converted {len(questions)}, skipped {skipped}")

fieldnames = ["question","answer","category","difficulty","mode","question_type",
              "choice_a","choice_b","choice_c","choice_d"]
with open("sat_math_hf.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(questions)
print("Saved to sat_math_hf.csv")
