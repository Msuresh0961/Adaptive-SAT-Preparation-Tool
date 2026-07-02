from flask import Flask, request, render_template, redirect, url_for, session
from markupsafe import escape
from werkzeug.security import generate_password_hash, check_password_hash
from db import (get_questions, get_question_by_id, get_full_test_module,
                get_focus_questions, save_game_session, save_question_result,
                get_leaderboard, get_user_stats, create_user, get_user)
import os, json, time, requests
from dotenv import load_dotenv
load_dotenv()

import os
print("DB PATH:", os.path.abspath("quiz.db"))

app = Flask(__name__)
app.secret_key = "replace-with-a-random-secret"

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

ADMIN_USERNAME = "Test_1"

SAT_RW_CATEGORIES = [
    "Information and Ideas", "Craft and Structure",
    "Expression of Ideas", "Standard English Conventions",
]
SAT_MATH_CATEGORIES = [
    "Algebra", "Advanced Math",
    "Problem-Solving and Data Analysis", "Geometry and Trigonometry",
]

# ── SAT Adaptive Score Conversion ──
# Module 1 is always the same (medium difficulty)
# Module 2 easy caps at ~630 RW / ~610 Math
# Module 2 hard can reach 800

# RW scoring based on module 2 difficulty
RW_EASY_M2_CONVERSION = {
    # Max ~630, min ~480 if M1 perfect but M2 zero
    54:630, 53:625, 52:620, 51:615, 50:610, 49:605, 48:600,
    47:595, 46:590, 45:585, 44:580, 43:575, 42:570, 41:565,
    40:560, 39:555, 38:550, 37:545, 36:540, 35:535, 34:530,
    33:525, 32:520, 31:515, 30:510, 29:505, 28:500, 27:495,
    26:490, 25:485, 24:480, 23:475, 22:470, 21:465, 20:460,
    19:455, 18:450, 17:445, 16:440, 15:435, 14:430, 13:425,
    12:420, 11:415, 10:410, 9:405, 8:400, 7:395, 6:390,
    5:385, 4:380, 3:370, 2:360, 1:340, 0:320
}

RW_HARD_M2_CONVERSION = {
    54:800, 53:790, 52:780, 51:770, 50:760, 49:750, 48:740,
    47:730, 46:720, 45:710, 44:700, 43:690, 42:680, 41:670,
    40:660, 39:650, 38:640, 37:630, 36:620, 35:610, 34:600,
    33:590, 32:580, 31:570, 30:560, 29:550, 28:540, 27:530,
    26:520, 25:510, 24:500, 23:490, 22:480, 21:470, 20:460,
    19:450, 18:440, 17:430, 16:420, 15:410, 14:400, 13:390,
    12:380, 11:370, 10:360, 9:350, 8:340, 7:330, 6:320,
    5:310, 4:300, 3:290, 2:280, 1:270, 0:200
}

# Math scoring based on module 2 difficulty
MATH_EASY_M2_CONVERSION = {
    # Max ~610, min ~520 if M1 perfect but M2 zero
    54:610, 53:605, 52:600, 51:595, 50:590, 49:585, 48:580,
    47:575, 46:570, 45:565, 44:560, 43:555, 42:550, 41:545,
    40:540, 39:535, 38:530, 37:525, 36:520, 35:515, 34:510,
    33:505, 32:500, 31:495, 30:490, 29:485, 28:480, 27:475,
    26:470, 25:465, 24:460, 23:455, 22:450, 21:445, 20:440,
    19:435, 18:430, 17:425, 16:420, 15:415, 14:410, 13:405,
    12:400, 11:395, 10:390, 9:385, 8:380, 7:375, 6:370,
    5:365, 4:360, 3:350, 2:340, 1:330, 0:310
}

MATH_HARD_M2_CONVERSION = {
    54:800, 53:790, 52:780, 51:770, 50:760, 49:750, 48:740,
    47:730, 46:720, 45:710, 44:700, 43:690, 42:680, 41:670,
    40:660, 39:650, 38:640, 37:630, 36:620, 35:610, 34:600,
    33:590, 32:580, 31:570, 30:560, 29:550, 28:540, 27:530,
    26:520, 25:510, 24:500, 23:490, 22:480, 21:470, 20:460,
    19:450, 18:440, 17:430, 16:420, 15:410, 14:400, 13:390,
    12:380, 11:370, 10:360, 9:350, 8:340, 7:330, 6:320,
    5:310, 4:300, 3:290, 2:280, 1:270, 0:200
}


def estimate_sat_score(rw_m1, rw_m2, math_m1, math_m2, rw_m2_diff="hard", math_m2_diff="hard"):
    """Convert raw module scores to estimated SAT scaled score (400-1600).
    
    Args:
        rw_m1:        correct answers in RW Module 1 (0-27)
        rw_m2:        correct answers in RW Module 2 (0-27)
        math_m1:      correct answers in Math Module 1 (0-27)
        math_m2:      correct answers in Math Module 2 (0-27)
        rw_m2_diff:   'easy' or 'hard'
        math_m2_diff: 'easy' or 'hard'
    """
    rw_total   = min(rw_m1 + rw_m2, 54)
    math_total = min(math_m1 + math_m2, 54)

    if rw_m2_diff == "easy":
        rw_scaled = RW_EASY_M2_CONVERSION.get(rw_total, 200)
    else:
        rw_scaled = RW_HARD_M2_CONVERSION.get(rw_total, 200)

    if math_m2_diff == "easy":
        math_scaled = MATH_EASY_M2_CONVERSION.get(math_total, 200)
    else:
        math_scaled = MATH_HARD_M2_CONVERSION.get(math_total, 200)

    return rw_scaled + math_scaled

# ── Auth helpers ──────────────────────────────────────────────

def logged_in():
    return "logged_in_name" in session

def current_user():
    return session.get("logged_in_name", "")


# ── Auth routes ───────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if logged_in():
        return redirect(url_for("home"))
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            error = "Please enter both a username and password."
        else:
            user = get_user(username)
            if not user:
                error = "No account found with that username."
            elif not check_password_hash(user["password_hash"], password):
                error = "Incorrect password."
            else:
                session["logged_in_name"] = user["username"]
                return redirect(url_for("home"))
    return render_template("login.html", error=error)


@app.route("/register", methods=["GET", "POST"])
def register():
    if logged_in():
        return redirect(url_for("home"))
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm", "")
        if not username or not password:
            error = "Please fill in all fields."
        elif len(username) < 2:
            error = "Username must be at least 2 characters."
        elif len(password) < 4:
            error = "Password must be at least 4 characters."
        elif password != confirm:
            error = "Passwords do not match."
        else:
            success = create_user(username, generate_password_hash(password))
            if not success:
                error = "That username is already taken."
            else:
                session["logged_in_name"] = username
                return redirect(url_for("home"))
    return render_template("register.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── Home ──────────────────────────────────────────────────────

@app.route("/", methods=["GET", "POST"])
def home():
    if not logged_in():
        return redirect(url_for("login"))

    username = current_user()

    if request.method == "POST":
        mode = request.form.get("mode", "quick")

        if mode == "full_test":
            test_number = int(request.form.get("test_number", 1))
            return start_full_test(test_number)

        questions = get_questions(limit=20, mode=mode)
        session["name"]         = username
        session["score"]        = 0
        session["current"]      = 0
        session["skipped"]      = 0
        session["mode"]         = mode
        session["results"]      = []
        session["question_ids"] = [q["id"] for q in questions]
        return redirect(url_for("question"))

    return render_template("home.html", username=username)


# ── Regular quiz routes ───────────────────────────────────────

@app.route("/question", methods=["GET", "POST"])
def question():
    if not logged_in():
        return redirect(url_for("login"))

    idx          = session.get("current", 0)
    question_ids = session.get("question_ids", [])

    if idx >= len(question_ids):
        session_id = save_game_session(
            username=session["name"],
            score=session["score"],
            total=len(question_ids),
            skipped=session.get("skipped", 0),
            mode=session.get("mode", "quick")
        )
        for result in session.get("results", []):
            save_question_result(
                session_id=session_id,
                question_id=result["question_id"],
                correct=result["correct"],
                skipped=result["skipped"],
                timed_out=result["timed_out"],
                time_spent=result.get("time_spent", 0)
            )
        return redirect(url_for("result"))

    q = get_question_by_id(question_ids[idx])

    if request.method == "POST":
        skipped    = request.form.get("skipped") == "1"
        time_spent = float(request.form.get("time_spent", 0))

        if skipped:
            session["results"].append({
                "question_id": q["id"], "correct": False,
                "skipped": True, "timed_out": False, "time_spent": 0
            })
            session["current"] += 1
            session["skipped"] = session.get("skipped", 0) + 1
            return redirect(url_for("question"))

        answer    = escape(request.form.get("answer", ""))
        timed_out = request.form.get("timed_out") == "1"
        correct   = answer.lower() == q["answer"].lower() and not timed_out

        if correct:
            session["score"] += 1

        session["current"] += 1
        session["results"].append({
            "question_id": q["id"], "correct": correct,
            "skipped": False, "timed_out": timed_out, "time_spent": time_spent
        })
        session["last_correct"]   = correct
        session["last_answer"]    = q["answer"]
        session["last_timed_out"] = timed_out
        return redirect(url_for("feedback"))

    return render_template(
        "question.html",
        question=q["question"],
        username=session["name"],
        time_left=10,
        question_num=idx + 1,
        total=len(question_ids),
        question_type=q["question_type"],
        choice_a=q.get("choice_a"),
        choice_b=q.get("choice_b"),
        choice_c=q.get("choice_c"),
        choice_d=q.get("choice_d"),
        mode=session.get("mode", "quick"),
        category=q.get("category", "")
    )


@app.route("/feedback")
def feedback():
    if not logged_in():
        return redirect(url_for("login"))
    return render_template(
        "feedback.html",
        username=session["name"],
        correct=session["last_correct"],
        correct_answer=session["last_answer"],
        timed_out=session["last_timed_out"],
        score=session["score"],
        questions_done=session["current"]
    )


@app.route("/result")
def result():
    if not logged_in():
        return redirect(url_for("login"))
    return render_template(
        "result.html",
        username=session["name"],
        score=session["score"],
        total=len(session.get("question_ids", [1])),
        skipped=session.get("skipped", 0),
        mode=session.get("mode", "quick")
    )


# ── Full test routes ──────────────────────────────────────────

# Module config: (category, module_num, time_seconds, label)
MODULES = [
    ("Reading and Writing", 1, 32 * 60, "RW Module 1"),
    ("Reading and Writing", 2, 32 * 60, "RW Module 2"),
    ("Math",                1, 35 * 60, "Math Module 1"),
    ("Math",                2, 35 * 60, "Math Module 2"),
]

# Adaptive thresholds
RW_HARD_THRESHOLD   = 20
MATH_HARD_THRESHOLD = 17


def start_full_test(test_number):
    """Initialize a full test session and load RW Module 1."""
    username = current_user()

    # Reset used IDs tracker for new test
    session["ft_used_question_ids"] = []

    questions = get_full_test_module(
        test_number=test_number,
        category="Reading and Writing",
        difficulty="medium",
        limit=27,
        exclude_ids=[]
    )

    # Track used IDs to prevent duplicates across modules
    session["ft_used_question_ids"] = [q["id"] for q in questions]

    n = len(questions)
    session["name"]                     = username
    session["mode"]                     = "full_test"
    session["ft_test_number"]           = test_number
    session["ft_module_index"]          = 0
    session["ft_question_ids"]          = [q["id"] for q in questions]
    session["ft_current"]               = 0
    session["ft_answers"]               = {str(i): "" for i in range(n)}
    session["ft_module_scores"]         = []
    session["ft_module_seconds"]        = MODULES[0][2]
    session["ft_results_before_module"] = 0

    return redirect(url_for("full_test_module"))


@app.route("/full_test", methods=["GET", "POST"])
def full_test_module():
    """Handle questions within a full test module."""
    if not logged_in():
        return redirect(url_for("login"))
    if "ft_test_number" not in session:
        return redirect(url_for("home"))

    module_idx   = session["ft_module_index"]
    question_ids = session["ft_question_ids"]

    if len(question_ids) == 0:
        return "Error: No full test questions found. Run allocate_full_tests.py first.", 500

    if request.method == "POST":
        remaining = int(request.form.get("module_seconds_remaining", session["ft_module_seconds"]))
        session["ft_module_seconds"] = max(remaining, 0)

        action     = request.form.get("action", "save")
        answer     = escape(request.form.get("answer", ""))
        time_spent = float(request.form.get("time_spent", 0))
        current_q  = session["ft_current"]

        answers = session.get("ft_answers", {})
        answers[str(current_q)] = answer
        session["ft_answers"] = answers

        if action == "timeout":
            return _finish_module_with_answers()
        elif action == "finish":
            return _finish_module_with_answers()
        elif action.startswith("goto:"):
            target = int(action.split(":")[1])
            target = max(0, min(target, len(question_ids) - 1))
            session["ft_current"] = target
            return redirect(url_for("full_test_module"))
        else:
            # "save" — stay on same question
            return redirect(url_for("full_test_module"))

    # GET — render current question
    current_q = session["ft_current"]

    goto = request.args.get("goto")
    if goto is not None:
        current_q = max(0, min(int(goto), len(question_ids) - 1))
        session["ft_current"] = current_q

    q = get_question_by_id(question_ids[current_q])
    cat, mod_num, mod_seconds, label = MODULES[module_idx]

    answers = session.get("ft_answers", {})
    current_answer = answers.get(str(current_q), "")
    answered_flags = [bool(answers.get(str(i), "")) for i in range(len(question_ids))]

    return render_template(
        "full_test_question.html",
        question=q["question"],
        username=current_user(),
        question_num=current_q + 1,
        total=len(question_ids),
        question_type=q["question_type"],
        choice_a=q.get("choice_a"),
        choice_b=q.get("choice_b"),
        choice_c=q.get("choice_c"),
        choice_d=q.get("choice_d"),
        category=q.get("category", ""),
        module_label=label,
        module_seconds_remaining=session["ft_module_seconds"],
        time_display=f"{session['ft_module_seconds'] // 60}:{session['ft_module_seconds'] % 60:02d}",
        current_answer=current_answer,
        answered_flags=answered_flags
    )


def _finish_module_with_answers():
    """Convert ft_answers dict into ft_results list and call finish_module."""
    question_ids = session["ft_question_ids"]
    answers      = session.get("ft_answers", {})
    prev_count   = session.get("ft_results_before_module", 0)

    module_results = []
    for i, qid in enumerate(question_ids):
        chosen  = answers.get(str(i), "")
        q       = get_question_by_id(qid)
        correct = bool(chosen) and chosen.lower() == q["answer"].lower()
        skipped = not bool(chosen)
        module_results.append({
            "question_id": qid,
            "correct":    correct,
            "skipped":    skipped,
            "timed_out":  False,
            "time_spent": 0
        })

    all_results = session.get("ft_results", [])
    all_results = all_results[:prev_count] + module_results
    session["ft_results"] = all_results

    return finish_module()


def finish_module():
    """Advance to next module or finish test."""
    module_idx = session["ft_module_index"]

    prev_count     = session.get("ft_results_before_module", 0)
    module_results = session["ft_results"][prev_count:]
    module_score   = sum(1 for r in module_results if r["correct"])
    session["ft_module_scores"].append(module_score)

    next_module_idx = module_idx + 1

    def load_module(category, difficulty, mod_idx):
        questions = get_full_test_module(
            test_number=session["ft_test_number"],
            category=category,
            difficulty=difficulty,
            limit=27,
            exclude_ids=session.get("ft_used_question_ids", [])
        )

        # Add newly loaded IDs to used list to prevent future duplicates
        used_ids = session.get("ft_used_question_ids", [])
        used_ids.extend([q["id"] for q in questions])
        session["ft_used_question_ids"] = used_ids

        n = len(questions)
        session["ft_module_index"]          = mod_idx
        session["ft_question_ids"]          = [q["id"] for q in questions]
        session["ft_current"]               = 0
        session["ft_module_seconds"]        = MODULES[mod_idx][2]
        session["ft_results_before_module"] = len(session["ft_results"])
        session["ft_answers"]               = {str(i): "" for i in range(n)}

    # After RW Module 1 — load RW Module 2
    if module_idx == 0:
        m2_difficulty = "hard" if module_score >= RW_HARD_THRESHOLD else "easy"
        session["ft_rw_m2_difficulty"] = m2_difficulty
        load_module("Reading and Writing", m2_difficulty, next_module_idx)
        return redirect(url_for("full_test_module"))

    # After RW Module 2 — show break before Math
    if module_idx == 1:
        rw_total_score = session["ft_module_scores"][0] + module_score
        session["ft_module_index"] = next_module_idx
        return render_template(
            "break.html",
            rw_score=rw_total_score,
            rw_total=54
        )

    # After Math Module 1 — load Math Module 2
    if module_idx == 2:
        m2_difficulty = "hard" if module_score >= MATH_HARD_THRESHOLD else "easy"
        session["ft_math_m2_difficulty"] = m2_difficulty
        load_module("Math", m2_difficulty, next_module_idx)
        return redirect(url_for("full_test_module"))

    # After Math Module 2 — test complete
    if module_idx == 3:
        return finish_full_test()

    return redirect(url_for("home"))


@app.route("/full_test/break_done")
def break_done():
    """Called when break ends. Loads Math Module 1."""
    if not logged_in() or "ft_test_number" not in session:
        return redirect(url_for("home"))

    questions = get_full_test_module(
        test_number=session["ft_test_number"],
        category="Math",
        difficulty="medium",
        limit=27,
        exclude_ids=session.get("ft_used_question_ids", [])
    )

    # Track used IDs
    used_ids = session.get("ft_used_question_ids", [])
    used_ids.extend([q["id"] for q in questions])
    session["ft_used_question_ids"] = used_ids

    n = len(questions)
    session["ft_module_index"]          = 2
    session["ft_question_ids"]          = [q["id"] for q in questions]
    session["ft_current"]               = 0
    session["ft_module_seconds"]        = MODULES[2][2]
    session["ft_results_before_module"] = len(session.get("ft_results", []))
    session["ft_answers"]               = {str(i): "" for i in range(n)}
    return redirect(url_for("full_test_module"))


def finish_full_test():
    """Calculate final scores and show results."""
    scores = session["ft_module_scores"]

    rw_m1   = scores[0] if len(scores) > 0 else 0
    rw_m2   = scores[1] if len(scores) > 1 else 0
    math_m1 = scores[2] if len(scores) > 2 else 0
    math_m2 = scores[3] if len(scores) > 3 else 0

    rw_total   = rw_m1 + rw_m2
    math_total = math_m1 + math_m2

    sat_score = estimate_sat_score(
        rw_m1, rw_m2, math_m1, math_m2,
        rw_m2_diff=session.get("ft_rw_m2_difficulty", "hard"),
        math_m2_diff=session.get("ft_math_m2_difficulty", "hard")
    )

    session_id = save_game_session(
        username=current_user(),
        score=rw_total + math_total,
        total=108,
        skipped=sum(1 for r in session["ft_results"] if r["skipped"]),
        mode="full_test"
    )
    for result in session["ft_results"]:
        save_question_result(
            session_id=session_id,
            question_id=result["question_id"],
            correct=result["correct"],
            skipped=result["skipped"],
            timed_out=result["timed_out"],
            time_spent=result.get("time_spent", 0)
        )
    session["ft_answers_final"] = session.get("ft_answers", {})

    return render_template(
        "full_result.html",
        test_number=session["ft_test_number"],
        sat_score=sat_score,
        rw_score=rw_total,   rw_total=54,
        rw_m1_score=rw_m1,  rw_m1_total=27,
        rw_m2_score=rw_m2,  rw_m2_total=27,
        rw_m2_diff=session.get("ft_rw_m2_difficulty", "medium"),
        math_score=math_total, math_total=54,
        math_m1_score=math_m1, math_m1_total=27,
        math_m2_score=math_m2, math_m2_total=27,
        math_m2_diff=session.get("ft_math_m2_difficulty", "medium"),
    )


# ── Focus practice routes ─────────────────────────────────────

@app.route("/focus")
def focus_select():
    if not logged_in():
        return redirect(url_for("login"))
    return render_template("focus_select.html")


@app.route("/focus/start", methods=["POST"])
def focus_start():
    if not logged_in():
        return redirect(url_for("login"))

    category   = request.form.get("category", "Math")
    difficulty = request.form.get("difficulty", "medium")

    questions = get_focus_questions(limit=10, category=category, difficulty=difficulty)

    if not questions:
        return redirect(url_for("focus_select"))

    session["name"]         = current_user()
    session["score"]        = 0
    session["current"]      = 0
    session["skipped"]      = 0
    session["mode"]         = "sat"
    session["results"]      = []
    session["question_ids"] = [q["id"] for q in questions]

    return redirect(url_for("question"))


# ── Leaderboard & stats ───────────────────────────────────────

@app.route("/leaderboard")
def leaderboard():
    quick_board = get_leaderboard(mode="quick", limit=10)
    sat_board   = get_leaderboard(mode="sat",   limit=10)
    return render_template("leaderboard.html", quick_board=quick_board, sat_board=sat_board)


@app.route("/stats")
def stats():
    if not logged_in():
        return redirect(url_for("login"))
    username    = request.args.get("username", current_user()).strip()
    quick_stats = get_user_stats(username, mode="quick")
    sat_stats   = get_user_stats(username, mode="sat")
    all_stats   = get_user_stats(username)

    cat_stats = sat_stats.get("category_stats") or all_stats.get("category_stats") or []

    weakest_category   = None
    weakest_pct        = None
    weakest_difficulty = "medium"

    if cat_stats:
        eligible = [c for c in cat_stats if c.get("total", 0) >= 3]
        if not eligible:
            eligible = cat_stats
        if eligible:
            worst = min(eligible, key=lambda c: c.get("pct") or 0)
            weakest_category = worst.get("category")
            weakest_pct      = worst.get("pct")
            if weakest_pct is not None:
                if weakest_pct < 40:
                    weakest_difficulty = "easy"
                elif weakest_pct < 70:
                    weakest_difficulty = "medium"
                else:
                    weakest_difficulty = "hard"

    return render_template(
        "stats.html",
        username=username,
        quick_stats=quick_stats,
        sat_stats=sat_stats,
        all_stats=all_stats,
        weakest_category=weakest_category,
        weakest_pct=weakest_pct,
        weakest_difficulty=weakest_difficulty,
    )


def _gemini_generate(prompt):
    """Call Groq API and return parsed list of question dicts."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GROQ_API_KEY}"
    }
    body = {
        "model": "meta-llama/llama-4-scout-17b-16e-instruct",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.9,
        "max_tokens": 8192
    }
    resp = requests.post(GROQ_URL, headers=headers, json=body, timeout=60)
    resp.raise_for_status()
    text = resp.json()["choices"][0]["message"]["content"].strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip().rstrip("```").strip())


def _build_prompt(mode, category, difficulty, count):
    is_math = category in SAT_MATH_CATEGORIES or category == "Math"
    math_note = "- You may use simple LaTeX wrapped in \\( \\) for inline math\n" if is_math else ""
    subject_note = f"SAT-style {'Math' if is_math else 'Reading and Writing'}" if mode != "quick" else "general knowledge trivia"

    return f"""Generate {count} {subject_note} multiple choice questions about {category}.
Difficulty: {difficulty}
Rules:
- Exactly 4 options (A, B, C, D), one correct answer
- Questions must be self-contained and factually accurate
- Mirror real SAT style if SAT mode
{math_note}
Return ONLY a JSON array, no markdown:
[{{"question":"...","choice_a":"...","choice_b":"...","choice_c":"...","choice_d":"...","correct_answer":"A","category":"{category}","difficulty":"{difficulty}"}}]"""


def _insert_questions_to_db(questions, mode, test_number=None):
    """Insert generated questions into quiz.db."""
    import sqlite3
    conn = sqlite3.connect("quiz.db")
    cur  = conn.cursor()

    for col in ["ai_generated INTEGER DEFAULT 0", "test_number INTEGER DEFAULT NULL"]:
        try:
            cur.execute(f"ALTER TABLE questions ADD COLUMN {col}")
        except Exception:
            pass

    inserted = 0
    for q in questions:
        try:
            cur.execute("""
                INSERT INTO questions
                    (question, choice_a, choice_b, choice_c, choice_d,
                     answer, category, difficulty, mode, question_type,
                     ai_generated, test_number)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'multiple_choice', 1, ?)
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
            ))
            inserted += 1
        except Exception:
            pass
    conn.commit()
    conn.close()
    return inserted


@app.route("/admin/generate_questions")
def admin_generate_page():
    return render_template("admin_generate.html")


@app.route("/admin/question_stats")
def admin_question_stats():
    if not logged_in() or current_user() != ADMIN_USERNAME:
        return {"error": "Unauthorized"}, 403
    import sqlite3
    conn = sqlite3.connect("quiz.db")
    cur  = conn.cursor()
    total = cur.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    sat   = cur.execute("SELECT COUNT(*) FROM questions WHERE mode='sat'").fetchone()[0]
    full  = cur.execute("SELECT COUNT(*) FROM questions WHERE mode='full_test'").fetchone()[0]
    ai    = cur.execute("SELECT COUNT(*) FROM questions WHERE ai_generated=1").fetchone()[0]
    conn.close()
    return {"total": total, "sat": sat, "full": full, "ai": ai}


@app.route("/admin/generate", methods=["POST"])
def admin_generate():
    if not logged_in() or current_user() != ADMIN_USERNAME:
        return {"error": "Unauthorized"}, 403

    from flask import jsonify
    data       = request.get_json()
    mode       = data.get("mode", "sat")
    category   = data.get("category", "Math")
    difficulty = data.get("difficulty", "medium")
    count      = min(int(data.get("count", 20)), 100)

    BATCH = 10
    total_inserted = 0
    batches = (count + BATCH - 1) // BATCH

    try:
        for _ in range(batches):
            c = min(BATCH, count - total_inserted)
            prompt    = _build_prompt(mode, category, difficulty, c)
            questions = _gemini_generate(prompt)
            total_inserted += _insert_questions_to_db(questions, mode)
            time.sleep(6)
        return jsonify({"inserted": total_inserted})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/admin/generate_full_test", methods=["POST"])
def admin_generate_full_test():
    if not logged_in() or current_user() != ADMIN_USERNAME:
        return {"error": "Unauthorized"}, 403

    from flask import jsonify
    data        = request.get_json()
    test_number = int(data.get("test_number", 1))

    specs = [
        (SAT_RW_CATEGORIES,   "medium", 27),
        (SAT_RW_CATEGORIES,   "easy",   27),
        (SAT_RW_CATEGORIES,   "hard",   27),
        (SAT_MATH_CATEGORIES, "medium", 27),
        (SAT_MATH_CATEGORIES, "easy",   27),
        (SAT_MATH_CATEGORIES, "hard",   27),
    ]

    total_inserted = 0
    try:
        for categories, difficulty, count in specs:
            per_cat = max(1, count // len(categories))
            for cat in categories:
                prompt    = _build_prompt("full_test", cat, difficulty, per_cat)
                questions = _gemini_generate(prompt)
                total_inserted += _insert_questions_to_db(questions, "full_test", test_number)
                time.sleep(0.5)
        return jsonify({"inserted": total_inserted, "test_number": test_number})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/full_test/review")
def full_test_review():
    if not logged_in():
        return redirect(url_for("home"))
    if "ft_results" not in session:
        return redirect(url_for("home"))

    results = []
    for i, r in enumerate(session["ft_results"]):
        q = get_question_by_id(r["question_id"])
        results.append({
            "question":       q["question"],
            "choice_a":       q.get("choice_a", ""),
            "choice_b":       q.get("choice_b", ""),
            "choice_c":       q.get("choice_c", ""),
            "choice_d":       q.get("choice_d", ""),
            "correct_answer": q["answer"],
            "chosen_answer":  session.get("ft_answers_final", {}).get(str(i), ""),
            "correct":        r["correct"],
            "skipped":        r["skipped"],
            "explanation":    q.get("explanation", ""),
        })

    scores = session.get("ft_module_scores", [0,0,0,0])
    return render_template(
        "full_test_review.html",
        username=current_user(),
        test_number=session.get("ft_test_number", 1),
        results=results,
        sat_score = estimate_sat_score(
            scores[0], scores[1] if len(scores)>1 else 0,
            scores[2] if len(scores)>2 else 0, scores[3] if len(scores)>3 else 0,
            rw_m2_diff=session.get("ft_rw_m2_difficulty", "hard"),
            math_m2_diff=session.get("ft_math_m2_difficulty", "hard")
        ),
        rw_m1_total=27,
        rw_m2_total=27,
        math_m1_total=27,
        math_m2_total=27,
    )


@app.route("/ai_tutor")
def ai_tutor():
    if not logged_in():
        return redirect(url_for("home"))
    if "ft_results" not in session:
        return redirect(url_for("home"))

    q_index          = request.args.get("q", None)
    question_context = None
    correct_answer   = None

    if q_index is not None:
        idx = int(q_index)
        if 0 <= idx < len(session["ft_results"]):
            r = session["ft_results"][idx]
            q = get_question_by_id(r["question_id"])
            question_context = q["question"]
            correct_answer   = q["answer"]
            chosen = session.get("ft_answers_final", {}).get(str(idx), "")
            system_context = f"""The student is asking about this specific question:
Question: {q['question']}
A) {q.get('choice_a','')}
B) {q.get('choice_b','')}
C) {q.get('choice_c','')}
D) {q.get('choice_d','')}
Correct answer: {q['answer']}
Student's answer: {chosen if chosen else 'Skipped'}
{'Explanation: ' + q['explanation'] if q.get('explanation') else ''}"""
    else:
        scores     = session.get("ft_module_scores", [0,0,0,0])
        rw_score   = (scores[0] if len(scores)>0 else 0) + (scores[1] if len(scores)>1 else 0)
        math_score = (scores[2] if len(scores)>2 else 0) + (scores[3] if len(scores)>3 else 0)
        total      = len(session["ft_results"])
        correct    = sum(1 for r in session["ft_results"] if r["correct"])

        from collections import defaultdict
        cat_correct = defaultdict(int)
        cat_total   = defaultdict(int)
        for r in session["ft_results"]:
            q = get_question_by_id(r["question_id"])
            cat = q.get("category", "General")
            cat_total[cat]   += 1
            cat_correct[cat] += 1 if r["correct"] else 0

        cat_summary = ", ".join(
            f"{cat}: {cat_correct[cat]}/{cat_total[cat]}"
            for cat in cat_total
        )

        system_context = f"""The student just completed Practice Test {session.get('ft_test_number',1)}.
Results: {correct}/{total} correct. RW: {rw_score}/54. Math: {math_score}/54.
Estimated SAT score: {estimate_sat_score(
    scores[0], scores[1] if len(scores)>1 else 0,
    scores[2] if len(scores)>2 else 0, scores[3] if len(scores)>3 else 0,
    rw_m2_diff=session.get("ft_rw_m2_difficulty", "hard"),
    math_m2_diff=session.get("ft_math_m2_difficulty", "hard")
)}.
Category breakdown: {cat_summary}.
Help them understand their performance and how to improve."""

    scores     = session.get("ft_module_scores", [0,0,0,0])
    rw_score   = (scores[0] if len(scores)>0 else 0) + (scores[1] if len(scores)>1 else 0)
    math_score = (scores[2] if len(scores)>2 else 0) + (scores[3] if len(scores)>3 else 0)
    total      = len(session["ft_results"])
    correct    = sum(1 for r in session["ft_results"] if r["correct"])

    return render_template(
        "ai_tutor.html",
        username=current_user(),
        test_number=session.get("ft_test_number", 1),
        question_context=question_context,
        correct_answer=correct_answer,
        system_context=system_context,
        groq_key=GROQ_API_KEY,
        correct=correct,
        total=total,
        rw_score=rw_score,
        rw_total=54,
        math_score=math_score,
        math_total=54,
        sat_score=estimate_sat_score(
            scores[0], scores[1] if len(scores)>1 else 0,
            scores[2] if len(scores)>2 else 0, scores[3] if len(scores)>3 else 0,
            rw_m2_diff=session.get("ft_rw_m2_difficulty", "hard"),
            math_m2_diff=session.get("ft_math_m2_difficulty", "hard")
        ),
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
