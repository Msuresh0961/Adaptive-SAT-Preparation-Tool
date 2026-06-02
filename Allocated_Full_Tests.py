import sqlite3
import random

con = sqlite3.connect("quiz.db")
cur = con.cursor()

# Reset only NON-AI-generated full_test questions back to sat
cur.execute("""
    UPDATE questions
    SET mode='sat', test_number=NULL
    WHERE mode='full_test'
      AND (ai_generated IS NULL OR ai_generated = 0)
""")
con.commit()
print("Reset previous full test allocation (non-AI questions only)")

# Fetch all SAT questions that are NOT AI-generated
cur.execute("""
    SELECT id, category FROM questions
    WHERE mode='sat'
      AND (ai_generated IS NULL OR ai_generated = 0)
    ORDER BY RANDOM()
""")
all_sat = cur.fetchall()

math_qs    = [row[0] for row in all_sat if row[1] == 'Math']
reading_qs = [row[0] for row in all_sat if row[1] == 'Reading and Writing']

print(f"Available (non-AI) — Math: {len(math_qs)}, Reading: {len(reading_qs)}")

# Each test needs 54 Math + 54 Reading = 108 questions
# Allocate up to 5 tests from available questions
NUM_TESTS      = 5
PER_TEST       = 54  # per subject per test

allocated_tests = 0
for test_num in range(1, NUM_TESTS + 1):
    start = (test_num - 1) * PER_TEST
    end   = start + PER_TEST

    t_math    = math_qs[start:end]
    t_reading = reading_qs[start:end]

    if len(t_math) < PER_TEST or len(t_reading) < PER_TEST:
        print(f"Test {test_num}: Not enough questions (Math: {len(t_math)}, Reading: {len(t_reading)}) — skipping")
        continue

    for qid in t_math + t_reading:
        cur.execute(
            "UPDATE questions SET mode='full_test', test_number=? WHERE id=?",
            (test_num, qid)
        )
    allocated_tests += 1
    print(f"Test {test_num}: {len(t_math)} Math + {len(t_reading)} Reading allocated")

con.commit()

# Verify final state
print("\nFinal allocation:")
cur.execute("""
    SELECT test_number, category, COUNT(*)
    FROM questions
    WHERE mode='full_test'
    GROUP BY test_number, category
    ORDER BY test_number, category
""")
for row in cur.fetchall():
    print(f"  Test {row[0]} | {row[1]} | {row[2]} questions")

# Also show AI-generated full test questions separately
print("\nAI-generated full test questions:")
cur.execute("""
    SELECT test_number, category, COUNT(*)
    FROM questions
    WHERE mode='full_test' AND ai_generated=1
    GROUP BY test_number, category
    ORDER BY test_number, category
""")
rows = cur.fetchall()
if rows:
    for row in rows:
        print(f"  Test {row[0]} | {row[1]} | {row[2]} questions")
else:
    print("  None yet — run generate_questions.py --test 2 to generate")

con.close()
print(f"\nDone. {allocated_tests} tests allocated from existing SAT questions.")