import sqlite3
import re

con = sqlite3.connect('quiz.db')
cur = con.cursor()

cur.execute("SELECT id, question, choice_a, choice_b, choice_c, choice_d FROM questions WHERE mode='sat'")
rows = cur.fetchall()
print(f"Total SAT questions before cleanup: {len(rows)}")

bad_ids = []

for row in rows:
    qid = row[0]
    q   = row[1] or ""
    choices = [row[2] or "", row[3] or "", row[4] or "", row[5] or ""]
    all_text = q + " ".join(choices)

    should_delete = False

    # LaTeX table/environment syntax MathJax can't render
    if re.search(r'\\begin\{(tabular|center|array|table)\}', all_text):
        should_delete = True

    # Questions referencing a graph, chart, or table not shown
    visual_phrases = [
        'the graph above', 'the table above', 'the figure above',
        'the chart above', 'the scatterplot above', 'shown above',
        'the bar graph', 'the line graph', 'the histogram',
        'shown in the graph', 'shown in the table', 'shown in the figure',
        'data from the graph', 'data from the table', 'data from the chart',
        'the graph in the xy-plane models', 'the graph shows',
        'the scatterplot shows', 'the bar graph shows', 'the line graph shows',
    ]
    for phrase in visual_phrases:
        if phrase.lower() in all_text.lower():
            should_delete = True
            break

    # Old OCR garbled questions
    if re.search(r'\b22\s*[—–-]\s*3\b', q):
        should_delete = True

    # OCR garbage characters in question or choices
    if re.search(r'[|\\@#~`\^]|[^\x00-\x7F]', q):
        should_delete = True
    for c in choices:
        if c and re.search(r'[|\\@#~`\^]|[^\x00-\x7F]', c):
            should_delete = True
            break

    # Choices with no spaces between them (OCR merge)
    for c in choices:
        if c and re.search(r'[a-z]-[a-z]', c):
            should_delete = True
            break

    # Font/encoding issues
    if re.search(r'perunit|thedemand', all_text):
        should_delete = True

    # Data set frequency table dumps
    if re.search(r'Data set [AB] frequency', q, re.IGNORECASE):
        should_delete = True

    # Raw table data — repeated number sequences
    if re.search(r'\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+', q):
        should_delete = True

    # Unknown environment errors
    if 'Unknown environment' in all_text:
        should_delete = True

    # Questions where graph data is dumped as text (axis labels, numbers)
    if re.search(r'\d+,\d+\s+\d+,\d+\s+\d+,\d+', q):
        should_delete = True

    # OCR axis label garbage like "NN BR WD oO x O*2"
    if re.search(r'NN BR WD|O\*\d|°\d|12:14', q):
        should_delete = True

    # Choices that are just single letters (completely empty choices)
    if row[2] and row[3] and row[4] and row[5]:
        if all(len(c.strip()) <= 1 for c in choices):
            should_delete = True

    # Questions with "the results are summarized in the table"
    if re.search(r'summarized in the table|results.*table.*above', q, re.IGNORECASE):
        should_delete = True

    if should_delete:
        bad_ids.append(qid)

print(f"Found {len(bad_ids)} bad questions to delete")

if bad_ids:
    cur.executemany("DELETE FROM questions WHERE id=?", [(i,) for i in bad_ids])
    con.commit()
    print(f"Deleted {len(bad_ids)} questions")

cur.execute("SELECT mode, category, question_type, COUNT(*) FROM questions GROUP BY mode, category, question_type")
print("\nRemaining questions:")
for row in cur.fetchall():
    print(f"  {row}")

con.close()