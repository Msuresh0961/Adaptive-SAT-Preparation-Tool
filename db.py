import os
import random
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Use DB_PATH env var if set (e.g. on Railway: /data/quiz.db so it survives
# redeploys via the mounted volume). Falls back to a local file for dev.
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "quiz.db"))


def get_connection():
    """Open and return a connection to the quiz database."""
    # Make sure the parent directory exists (matters for a fresh volume mount).
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    """Create all required tables if they do not already exist."""
    con = get_connection()
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS game_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            score INTEGER NOT NULL,
            total INTEGER NOT NULL,
            skipped INTEGER NOT NULL DEFAULT 0,
            mode TEXT NOT NULL,
            played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS question_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            correct INTEGER NOT NULL DEFAULT 0,
            skipped INTEGER NOT NULL DEFAULT 0,
            timed_out INTEGER NOT NULL DEFAULT 0,
            time_spent REAL NOT NULL DEFAULT 0,
            FOREIGN KEY(session_id) REFERENCES game_sessions(id),
            FOREIGN KEY(question_id) REFERENCES questions(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            choice_a TEXT,
            choice_b TEXT,
            choice_c TEXT,
            choice_d TEXT,
            answer TEXT NOT NULL,
            category TEXT NOT NULL,
            difficulty TEXT NOT NULL DEFAULT 'medium',
            mode TEXT NOT NULL DEFAULT 'quick',
            question_type TEXT NOT NULL DEFAULT 'multiple_choice',
            explanation TEXT,
            ai_generated INTEGER DEFAULT 0,
            test_number INTEGER DEFAULT NULL
        )
    """)

    con.commit()
    con.close()


init_db()


def seed_questions_if_empty(seed_path=None):
    """If the questions table is empty, load questions from a JSON seed file.

    This protects against a fresh/empty database (e.g. a brand-new Railway
    volume, or a lost volume) by restoring the question bank from a file
    committed to git. Safe to call every startup -- it only inserts when
    the table is empty, and it never touches users or game_sessions.
    """
    seed_path = seed_path or os.path.join(BASE_DIR, "questions_seed.json")
    if not os.path.exists(seed_path):
        return 0

    con = get_connection()
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM questions")
    count = cur.fetchone()[0]
    if count > 0:
        con.close()
        return 0

    import json
    with open(seed_path, "r", encoding="utf-8") as f:
        rows = json.load(f)

    inserted = 0
    for q in rows:
        cur.execute("""
            INSERT INTO questions
                (question, choice_a, choice_b, choice_c, choice_d,
                 answer, category, difficulty, mode, question_type,
                 explanation, ai_generated, test_number)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            q.get("question"), q.get("choice_a"), q.get("choice_b"),
            q.get("choice_c"), q.get("choice_d"), q.get("answer"),
            q.get("category"), q.get("difficulty", "medium"),
            q.get("mode", "quick"), q.get("question_type", "multiple_choice"),
            q.get("explanation"), q.get("ai_generated", 0), q.get("test_number"),
        ))
        inserted += 1

    con.commit()
    con.close()
    return inserted


seed_questions_if_empty()


# ── User authentication ───────────────────────────────────────────────────────

def create_user(username, password_hash):
    """Create a new user. Returns True on success, False if username taken."""
    con = get_connection()
    cur = con.cursor()
    try:
        cur.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash)
        )
        con.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        con.close()


def get_user(username):
    """Fetch a user row by username (case-insensitive). Returns dict or None."""
    con = get_connection()
    cur = con.cursor()
    cur.execute(
        "SELECT id, username, password_hash FROM users WHERE username = ? COLLATE NOCASE",
        (username,)
    )
    row = cur.fetchone()
    con.close()
    return dict(row) if row else None


# ── Question fetching ─────────────────────────────────────────────────────────

def get_questions(limit=20, mode="quick", category=None, difficulty=None):
    """Fetch a random selection of questions from the database."""
    con = get_connection()
    cur = con.cursor()

    MATH_CATEGORIES = [
        "Algebra", "Advanced Math",
        "Problem-Solving and Data Analysis", "Geometry and Trigonometry", "Math"
    ]
    RW_CATEGORIES = [
        "Information and Ideas", "Craft and Structure",
        "Expression of Ideas", "Standard English Conventions", "Reading and Writing"
    ]

    # SAT mode — equal split of Math and Reading and Writing
    if mode == "sat" and not category:
        half = limit // 2

        def fetch_category(subcategories, n):
            placeholders = ",".join(["?"] * len(subcategories))
            q = f"""SELECT * FROM questions
                   WHERE mode = 'sat' AND category IN ({placeholders})"""
            params = subcategories[:]
            if difficulty:
                q += " AND difficulty = ?"
                params.append(difficulty)
            q += " ORDER BY RANDOM() LIMIT ?"
            params.append(n)
            cur.execute(q, params)
            return [dict(row) for row in cur.fetchall()]

        math_qs = fetch_category(MATH_CATEGORIES, half)
        reading_qs = fetch_category(RW_CATEGORIES, limit - half)

        combined = math_qs + reading_qs
        random.shuffle(combined)
        con.close()
        return combined

    query = "SELECT * FROM questions WHERE mode = ?"
    params = [mode]

    if category:
        query += " AND category = ?"
        params.append(category)
    if difficulty:
        query += " AND difficulty = ?"
        params.append(difficulty)

    query += " ORDER BY RANDOM() LIMIT ?"
    params.append(limit)

    cur.execute(query, params)
    questions = [dict(row) for row in cur.fetchall()]

    # Backfill if not enough questions
    if len(questions) < limit:
        existing_ids = [q["id"] for q in questions]
        placeholders = ",".join(["?"] * len(existing_ids)) if existing_ids else "0"
        fallback_query = f"""
            SELECT * FROM questions
            WHERE mode = ?
            AND id NOT IN ({placeholders})
            ORDER BY RANDOM()
            LIMIT ?
        """
        fallback_params = [mode] + existing_ids + [limit - len(questions)]
        cur.execute(fallback_query, fallback_params)
        questions.extend([dict(row) for row in cur.fetchall()])

    random.shuffle(questions)
    con.close()
    return questions[:limit]


def get_focus_questions(limit=10, category="Math", difficulty="medium"):
    con = get_connection()
    cur = con.cursor()

    MATH_CATEGORIES = [
        "Algebra", "Advanced Math",
        "Problem-Solving and Data Analysis", "Geometry and Trigonometry", "Math"
    ]
    RW_CATEGORIES = [
        "Information and Ideas", "Craft and Structure",
        "Expression of Ideas", "Standard English Conventions", "Reading and Writing"
    ]

    if category == "Math":
        subcategories = MATH_CATEGORIES
    elif category == "Reading and Writing":
        subcategories = RW_CATEGORIES
    else:
        subcategories = [category]

    placeholders = ",".join(["?"] * len(subcategories))

    cur.execute(
        f"""SELECT * FROM questions
           WHERE mode = 'sat'
             AND category IN ({placeholders})
             AND difficulty = ?
           ORDER BY RANDOM()
           LIMIT ?""",
        subcategories + [difficulty, limit]
    )
    rows = cur.fetchall()

    if len(rows) < limit:
        existing_ids = [dict(r)["id"] for r in rows]
        excl = ",".join(["?"] * len(existing_ids)) if existing_ids else "0"
        cur.execute(
            f"""SELECT * FROM questions
                WHERE mode = 'sat'
                  AND category IN ({placeholders})
                  AND id NOT IN ({excl})
                ORDER BY RANDOM()
                LIMIT ?""",
            subcategories + existing_ids + [limit - len(rows)]
        )
        rows = list(rows) + list(cur.fetchall())

    con.close()
    result = [dict(row) for row in rows]
    random.shuffle(result)
    return result


def get_full_test_module(test_number, category, difficulty, limit=27, exclude_ids=None):
    """Fetch questions for a specific full test module.

    Args:
        test_number: 1, 2, 3, 4, or 5
        category:    'Math' or 'Reading and Writing'
        difficulty:  'easy', 'medium', or 'hard'
        limit:       27 questions per module (real SAT standard)
        exclude_ids: list of question IDs already used in previous modules

    Returns:
        List of question dicts in randomized order.
    """
    con = get_connection()
    cur = con.cursor()

    exclude_ids = exclude_ids or []

    MATH_CATEGORIES = [
        "Algebra", "Advanced Math",
        "Problem-Solving and Data Analysis", "Geometry and Trigonometry", "Math"
    ]
    RW_CATEGORIES = [
        "Information and Ideas", "Craft and Structure",
        "Expression of Ideas", "Standard English Conventions", "Reading and Writing"
    ]

    if category == "Math":
        subcategories = MATH_CATEGORIES
    elif category == "Reading and Writing":
        subcategories = RW_CATEGORIES
    else:
        subcategories = [category]

    cat_placeholders = ",".join(["?"] * len(subcategories))
    excl_placeholders = ",".join(["?"] * len(exclude_ids)) if exclude_ids else "0"

    cur.execute(
        f"""SELECT * FROM questions
           WHERE mode = 'full_test'
             AND test_number = ?
             AND category IN ({cat_placeholders})
             AND difficulty = ?
             AND id NOT IN ({excl_placeholders})
           ORDER BY RANDOM()
           LIMIT ?""",
        [test_number] + subcategories + [difficulty] + exclude_ids + [limit]
    )
    rows = cur.fetchall()

    if len(rows) < limit:
        existing_ids = [dict(r)["id"] for r in rows]
        all_excl = exclude_ids + existing_ids
        excl2 = ",".join(["?"] * len(all_excl)) if all_excl else "0"
        cur.execute(
            f"""SELECT * FROM questions
                WHERE mode = 'full_test'
                  AND test_number = ?
                  AND category IN ({cat_placeholders})
                  AND id NOT IN ({excl2})
                ORDER BY RANDOM()
                LIMIT ?""",
            [test_number] + subcategories + all_excl + [limit - len(rows)]
        )
        rows = list(rows) + list(cur.fetchall())

    con.close()
    result = [dict(row) for row in rows]
    random.shuffle(result)
    return result


def get_question_by_id(question_id):
    """Fetch a single question from the database by its ID."""
    con = get_connection()
    cur = con.cursor()
    cur.execute("SELECT * FROM questions WHERE id = ?", (question_id,))
    row = cur.fetchone()
    con.close()
    return dict(row) if row else None


def fetch_questions_from_api(amount=20, category_id=None, difficulty=None):
    """Fetch questions from the Open Trivia Database API and save locally."""
    import requests

    url = f"https://opentdb.com/api.php?amount={amount}&type=boolean"
    if category_id:
        url += f"&category={category_id}"
    if difficulty:
        url += f"&difficulty={difficulty}"

    response = requests.get(url)
    data = response.json()

    if data["response_code"] != 0:
        return 0

    con = get_connection()
    cur = con.cursor()
    saved = 0

    for item in data["results"]:
        cur.execute("SELECT id FROM questions WHERE question = ?", (item["question"],))
        if cur.fetchone():
            continue
        cur.execute(
            """INSERT INTO questions (question, answer, category, difficulty, mode, question_type)
               VALUES (?, ?, ?, ?, 'quick', 'text')""",
            (item["question"], item["correct_answer"], item["category"], item["difficulty"])
        )
        saved += 1

    con.commit()
    con.close()
    return saved


# ── Saving results ───────────────────────────────────────────────────────────

def save_game_session(username, score, total, skipped, mode="quick"):
    """Save a completed game session. Returns the session ID."""
    con = get_connection()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO game_sessions (username, score, total, skipped, mode) VALUES (?, ?, ?, ?, ?)",
        (username, score, total, skipped, mode)
    )
    session_id = cur.lastrowid
    con.commit()
    con.close()
    return session_id


def save_question_result(session_id, question_id, correct, skipped, timed_out, time_spent=0):
    """Save the outcome of a single question for a given session."""
    con = get_connection()
    cur = con.cursor()
    cur.execute(
        """INSERT INTO question_results
           (session_id, question_id, correct, skipped, timed_out, time_spent)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (session_id, question_id, int(correct), int(skipped), int(timed_out), float(time_spent))
    )
    con.commit()
    con.close()


# ── Leaderboard ──────────────────────────────────────────────────────────────

def get_leaderboard(mode="quick", limit=10):
    """Get top scores for a given mode ranked by percentage then most recent."""
    con = get_connection()
    cur = con.cursor()
    cur.execute(
        """SELECT username, score, total, skipped, played_at,
                  ROUND(CAST(score AS FLOAT) / total * 100, 1) AS pct
           FROM game_sessions
           WHERE mode = ? AND total > 0
           ORDER BY pct DESC, played_at DESC
           LIMIT ?""",
        (mode, limit)
    )
    rows = cur.fetchall()
    con.close()
    return [dict(row) for row in rows]


# ── Performance stats ────────────────────────────────────────────────────────

def get_user_stats(username, mode=None):
    """Get performance stats for a specific user."""
    con = get_connection()
    cur = con.cursor()

    mode_filter = "AND gs.mode = ?" if mode else ""
    params_base = [username] + ([mode] if mode else [])

    cur.execute(
        f"""SELECT COUNT(*) as total_games,
                   ROUND(AVG(CAST(gs.score AS FLOAT) / gs.total * 100), 1) as avg_pct,
                   ROUND(MAX(CAST(gs.score AS FLOAT) / gs.total * 100), 1) as best_pct
            FROM game_sessions gs
            WHERE gs.username = ? {mode_filter} AND gs.total > 0""",
        params_base
    )
    overall = dict(cur.fetchone())

    cur.execute(
        f"""SELECT q.category,
                   SUM(qr.correct) as correct,
                   COUNT(*) as total,
                   ROUND(CAST(SUM(qr.correct) AS FLOAT) / COUNT(*) * 100, 1) as pct
            FROM question_results qr
            JOIN game_sessions gs ON qr.session_id = gs.id
            JOIN questions q ON qr.question_id = q.id
            WHERE gs.username = ? {mode_filter}
              AND qr.skipped = 0
            GROUP BY q.category
            ORDER BY pct DESC""",
        params_base
    )
    category_stats = [dict(row) for row in cur.fetchall()]

    cur.execute(
        f"""SELECT ROUND(CAST(gs.score AS FLOAT) / gs.total * 100, 1) as pct, gs.played_at
            FROM game_sessions gs
            WHERE gs.username = ? {mode_filter} AND gs.total > 0
            ORDER BY gs.played_at DESC
            LIMIT 10""",
        params_base
    )
    recent = [dict(row) for row in cur.fetchall()]
    recent_scores = list(reversed([r["pct"] for r in recent]))

    cur.execute(
        f"""SELECT ROUND(AVG(qr.time_spent), 1) as avg_time
            FROM question_results qr
            JOIN game_sessions gs ON qr.session_id = gs.id
            WHERE gs.username = ? {mode_filter}
              AND qr.skipped = 0 AND qr.timed_out = 0
              AND qr.time_spent > 0""",
        params_base
    )
    time_row = cur.fetchone()
    avg_time = time_row["avg_time"] if time_row and time_row["avg_time"] else 0

    con.close()

    return {
        "total_games": overall["total_games"] or 0,
        "avg_score_pct": overall["avg_pct"] or 0,
        "best_score_pct": overall["best_pct"] or 0,
        "category_stats": category_stats,
        "recent_scores": recent_scores,
        "avg_time_spent": avg_time,
    }
