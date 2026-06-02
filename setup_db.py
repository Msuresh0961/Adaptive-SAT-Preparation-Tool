import sqlite3

con = sqlite3.connect("quiz.db")
cur = con.cursor()

# ── Users table ──────────────────────────────────────────────
# Stores registered users with hashed passwords
cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        username      TEXT    NOT NULL UNIQUE COLLATE NOCASE,
        password_hash TEXT    NOT NULL,
        created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
    )
""")

# ── Questions table ───────────────────────────────────────────
# test_number: NULL for practice questions, 1 or 2 for full test questions
cur.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        question      TEXT    NOT NULL,
        answer        TEXT    NOT NULL,
        category      TEXT    NOT NULL DEFAULT 'General',
        difficulty    TEXT    NOT NULL DEFAULT 'medium'
            CHECK(difficulty IN ('easy', 'medium', 'hard')),
        mode          TEXT    NOT NULL DEFAULT 'quick'
            CHECK(mode IN ('quick', 'sat', 'full_test')),
        question_type TEXT    NOT NULL DEFAULT 'text'
            CHECK(question_type IN ('text', 'multiple_choice')),
        choice_a      TEXT,
        choice_b      TEXT,
        choice_c      TEXT,
        choice_d      TEXT,
        test_number   INTEGER DEFAULT NULL  -- 1 or 2 for full test questions
    )
""")

# ── Game sessions table ───────────────────────────────────────
cur.execute("""
    CREATE TABLE IF NOT EXISTS game_sessions (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        username     TEXT    NOT NULL,
        score        INTEGER NOT NULL,
        total        INTEGER NOT NULL,
        skipped      INTEGER NOT NULL DEFAULT 0,
        mode         TEXT    NOT NULL DEFAULT 'quick',
        played_at    DATETIME DEFAULT CURRENT_TIMESTAMP
    )
""")

# ── Question results table ────────────────────────────────────
cur.execute("""
    CREATE TABLE IF NOT EXISTS question_results (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id  INTEGER NOT NULL REFERENCES game_sessions(id),
        question_id INTEGER NOT NULL REFERENCES questions(id),
        correct     INTEGER NOT NULL,
        skipped     INTEGER NOT NULL,
        timed_out   INTEGER NOT NULL,
        time_spent  REAL    NOT NULL DEFAULT 0
    )
""")

# ── Seed Quick Quiz Questions ─────────────────────────────────
cur.execute("SELECT COUNT(*) FROM questions")
count = cur.fetchone()[0]

if count == 0:
    seed_questions = [
        ("What is the capital of America?",               "Washington DC",      "Geography",  "easy",   "quick", "text", None, None, None, None),
        ("What is the largest planet in the solar system?","Jupiter",           "Science",    "easy",   "quick", "text", None, None, None, None),
        ("What is 2 + 2?",                                "4",                  "Math",       "easy",   "quick", "text", None, None, None, None),
        ("What is the chemical symbol for water?",        "H2O",                "Science",    "easy",   "quick", "text", None, None, None, None),
        ("Who wrote 'Romeo and Juliet'?",                 "William Shakespeare","Literature", "easy",   "quick", "text", None, None, None, None),
        ("What is the speed of light in vacuum?",         "299792458 m/s",      "Science",    "hard",   "quick", "text", None, None, None, None),
        ("What is the largest mammal?",                   "Blue Whale",         "Science",    "easy",   "quick", "text", None, None, None, None),
        ("What is the smallest prime number?",            "2",                  "Math",       "easy",   "quick", "text", None, None, None, None),
        ("Who painted the Mona Lisa?",                    "Leonardo da Vinci",  "Art",        "easy",   "quick", "text", None, None, None, None),
        ("What is the currency of Japan?",                "Yen",                "Geography",  "easy",   "quick", "text", None, None, None, None),
        ("What is the tallest mountain in the world?",    "Mount Everest",      "Geography",  "easy",   "quick", "text", None, None, None, None),
        ("What is the largest ocean on Earth?",           "Pacific Ocean",      "Geography",  "easy",   "quick", "text", None, None, None, None),
        ("Who is the author of 'Harry Potter'?",          "J.K. Rowling",       "Literature", "easy",   "quick", "text", None, None, None, None),
        ("What is the chemical symbol for gold?",         "Au",                 "Science",    "medium", "quick", "text", None, None, None, None),
        ("What is the largest desert in the world?",      "Sahara Desert",      "Geography",  "medium", "quick", "text", None, None, None, None),
        ("Who was the first person to walk on the moon?", "Neil Armstrong",     "History",    "easy",   "quick", "text", None, None, None, None),
        ("What is the smallest country in the world?",    "Vatican City",       "Geography",  "medium", "quick", "text", None, None, None, None),
        ("What is the longest river in the world?",       "Nile River",         "Geography",  "medium", "quick", "text", None, None, None, None),
        ("Who is known as the 'Father of Computers'?",   "Charles Babbage",    "History",    "medium", "quick", "text", None, None, None, None),
        ("What is the derivative of tan(x)?",             "sec^2(x)",           "Math",       "hard",   "quick", "text", None, None, None, None),
        ("What is the powerhouse of the cell?",            "Mitochondria",       "Science",    "easy",   "quick", "text", None, None, None, None),
        ("What is the largest continent on Earth?",         "Asia",               "Geography",  "easy",   "quick", "text", None, None, None, None),
        ("Who is the Greek god of the sea?",                 "Poseidon",           "Mythology", "easy",   "quick", "text", None, None, None, None),
        ("What is the chemical symbol for iron?",         "Fe",                 "Science",    "medium", "quick", "text", None, None, None, None),
        ("What is the largest island in the world?",       "Greenland",          "Geography",  "medium", "quick", "text", None, None, None, None),
        ("Who was the first president of the United States?", "George Washington","History",    "easy",   "quick", "text", None, None, None, None),
        ("What is the smallest bone in the human body?",    "Stapes",             "Science",    "medium", "quick", "text", None, None, None, None),
        ("What is the largest volcano in the world?",         "Mauna Loa",          "Geography",  "medium", "quick", "text", None, None, None, None),
        ("Who is the Roman god of war?",                     "Mars",               "Mythology", "easy",   "quick", "text", None, None, None, None),
        ("What is the chemical symbol for silver?",       "Ag",                 "Science",    "medium", "quick", "text", None, None, None, None),
        ("What is the largest lake in the world?",          "Caspian Sea",        "Geography",  "medium", "quick", "text", None, None, None, None),
        ("Who was the first woman to win a Nobel Prize?",                 "Marie Curie",        "History",    "medium", "quick", "text", None, None, None, None),
        ("What is the largest species of shark?",          "Whale Shark",        "Science",    "medium", "quick", "text", None, None, None, None),
        ("What is the chemical symbol for carbon?",       "C",                  "Science",    "easy",   "quick", "text", None, None, None, None),
        ("What is the largest city in the world by population?", "Tokyo",          "Geography",  "medium", "quick", "text", None, None, None, None),
        ("Who is the Norse god of thunder?",              "Thor",               "Mythology", "easy",   "quick", "text", None, None, None, None),
        ("What is the chemical symbol for sodium?",       "Na",                 "Science",    "medium", "quick", "text", None, None, None, None),
        ("What is the largest waterfall in the world?",     "Angel Falls",        "Geography",  "medium", "quick", "text", None, None, None, None),
        ("Who was the first person to circumnavigate the globe?",                 "Ferdinand Magellan","History",    "medium", "quick", "text", None, None, None, None),
        ("What is the largest species of bird?",           "Ostrich",            "Science",    "medium", "quick", "text", None, None, None, None),
        ("What is the chemical symbol for helium?",       "He",                 "Science",    "easy",   "quick", "text", None, None, None, None),
        ("What is the largest canyon in the world?",      "Grand Canyon",       "Geography",  "medium", "quick", "text", None, None, None, None),
        ("Who is the Egyptian god of the afterlife?",     "Osiris",             "Mythology", "easy",   "quick", "text", None, None, None, None),
        ("What is the chemical symbol for potassium?",    "K",                  "Science",    "medium", "quick", "text", None, None, None, None),
        ("What is the largest coral reef system in the world?",  "Great Barrier Reef","Geography","medium","quick","text",None,None,None,None),
        ("Who was the first person to discover penicillin?",                 "Alexander Fleming",  "History",    "medium", "quick", "text", None, None, None, None),
        ("What is the largest species of fish?",           "Whale Shark",        "Science",    "medium", "quick", "text", None, None, None, None),
        ("What is the chemical symbol for nitrogen?",     "N",                  "Science",    "easy",   "quick", "text", None, None, None, None),
        ("What is the largest desert in the world?",      "Sahara Desert",      "Geography",  "medium", "quick", "text", None, None, None, None),
        ("Who is the Greek goddess of wisdom?",           "Athena",             "Mythology", "easy",   "quick", "text", None, None, None, None),
        ("What is the chemical symbol for oxygen?",       "O",                  "Science",    "easy",   "quick", "text", None, None, None, None),
        ("What is the largest glacier in the world?",      "Lambert Glacier",    "Geography",  "medium", "quick", "text", None, None, None, None),
        ("Who was the first person to reach the South Pole?",                 "Roald Amundsen",     "History",    "medium", "quick", "text", None, None, None, None),
        ("What is the largest species of reptile?",        "Saltwater Crocodile","Science",   "medium", "quick", "text", None, None, None, None),
        ("What is the chemical symbol for phosphorus?",   "P",                  "Science",    "medium", "quick", "text", None, None, None, None),
        ("What is the largest bay in the world?",         "Bay of Bengal",      "Geography",  "medium", "quick", "text", None, None, None, None),
        ("Who is the Hindu god of destruction?",          "Shiva",              "Mythology", "easy",   "quick", "text", None, None, None, None),
        ("What is the chemical symbol for calcium?",      "Ca",                 "Science",    "medium", "quick", "text", None, None, None, None),
        ("What is the largest peninsula in the world?",   "Arabian Peninsula",  "Geography",  "medium", "quick", "text", None, None, None, None),
        ("Who was the first person to fly across the Atlantic Ocean?",                 "Charles Lindbergh",  "History",    "medium", "quick", "text", None, None, None, None),
        ("What is the largest species of amphibian?",      "Chinese Giant Salamander","Science","medium","quick","text",None,None,None,None),
        ("What is the chemical symbol for magnesium?",    "Mg",                 "Science",    "medium", "quick", "text", None, None, None, None),
        ("What is the largest river in South America?",   "Amazon River",       "Geography",  "medium", "quick", "text", None, None, None, None),
        ("Who is the Japanese god of the sun?",           "Amaterasu",          "Mythology", "easy",   "quick", "text", None, None, None, None),
        ("What is the chemical symbol for zinc?",       "Zn",                 "Science",    "medium", "quick", "text", None, None, None, None),
        ("What is the largest canyon in the world?",      "Yarlung Tsangpo Grand Canyon", "Geography", "medium", "quick", "text", None, None, None, None),
        ("Who was the first person to discover America?",                 "Christopher Columbus","History",    "medium", "quick", "text", None, None, None, None),
        ("What is the largest species of insect?",        "Giant Weta",         "Science",    "medium", "quick", "text", None, None, None, None),
        ("What is the chemical symbol for copper?",       "Cu",                 "Science",    "medium", "quick", "text", None, None, None, None),
        ("What is the largest island in the Mediterranean Sea?", "Sicily",       "Geography",  "medium", "quick", "text", None, None, None, None),
        ("Who is the Aztec god of the sun?",              "Huitzilopochtli",    "Mythology", "easy",   "quick", "text", None, None, None, None),
        ("What is the chemical symbol for lead?",         "Pb",                 "Science",    "medium", "quick", "text", None, None, None, None),
        ("What is the largest glacier in the world?",      "Hubbard Glacier",    "Geography",  "medium", "quick", "text", None, None, None, None),
        ("Who was the first person to climb Mount Everest?",                 "Edmund Hillary and Tenzing Norgay","History","medium","quick","text",None,None,None,None),
        ("What is the largest species of arachnid?",       "Goliath Birdeater",  "Science",    "medium", "quick", "text", None, None, None, None),
        ("What is the chemical symbol for silver?",       "Ag",                 "Science",    "medium", "quick", "text", None, None, None, None),
        ("What is the largest lake in Africa?",           "Lake Victoria",      "Geography",  "medium", "quick", "text", None, None, None, None),
        ("Who is the Incan god of the sun?",              "Inti",               "Mythology", "easy",   "quick", "text", None, None, None, None),
        ("What is the chemical symbol for mercury?",      "Hg",                 "Science",    "medium", "quick", "text", None, None, None, None),
        ("What is the largest canyon in the world?",      "Grand Canyon",       "Geography",  "medium", "quick", "text", None, None, None, None),
        ("Who was the first person to invent the telephone?",                 "Alexander Graham Bell","History",    "medium", "quick", "text", None, None, None, None),
        ("What is the largest species of mollusk?",       "Giant Squid",        "Science",    "medium", "quick", "text", None, None, None, None),
        ("What is the chemical symbol for aluminum?",     "Al",                 "Science",    "medium", "quick", "text", None, None, None, None),
        ("What is the largest island in the Caribbean?",  "Cuba",               "Geography",  "medium", "quick", "text", None, None, None, None),
        ("Who is the Mayan god of the sun?",              "Kinich Ahau",        "Mythology", "easy",   "quick", "text", None, None, None, None),
        ("What is the chemical symbol for tin?",          "Sn",                 "Science",    "medium", "quick", "text", None, None, None, None),
        ("What is the largest glacier in Antarctica?",    "Lambert Glacier",    "Geography",  "medium", "quick", "text", None, None, None, None),
        ("Who was the first person to invent the light bulb?",                 "Thomas Edison","History",    "medium", "quick", "text", None, None, None, None),
        ("What is the largest species of crustacean?",     "Japanese Spider Crab","Science","medium","quick","text",None,None,None,None),
        ("What is the chemical symbol for uranium?",      "U",                  "Science",    "medium", "quick", "text", None, None, None, None),
        ("What is the largest river in North America?",   "Mississippi River",  "Geography",  "medium", "quick", "text", None, None, None, None),
        ("Who is the Celtic god of the sun?",             "Lugh",               "Mythology", "easy",   "quick", "text", None, None, None, None),
        ("What is the chemical symbol for tungsten?",     "W",                  "Science",    "medium", "quick", "text", None, None, None, None),
        ("What is the largest canyon in Asia?",           "Yarlung Tsangpo Grand Canyon", "Geography", "medium", "quick", "text", None, None, None, None),
        ("Who was the first person to invent the printing press?",                 "Johannes Gutenberg","History",    "medium", "quick", "text", None, None, None, None),
        ("What is the largest species of mammal?",       "Blue Whale",         "Science",    "medium", "quick", "text", None, None, None, None),
        ("What is the chemical symbol for platinum?",     "Pt",                 "Science",    "medium", "quick", "text", None, None, None, None),
        ("What is the largest island in the world?",      "Greenland",          "Geography",  "medium", "quick", "text", None, None, None, None),
        ("Who is the Sumerian god of the sun?",           "Utu",                "Mythology", "easy",   "quick", "text", None, None, None, None),
    ]
    cur.executemany(
        """INSERT INTO questions
           (question, answer, category, difficulty, mode, question_type,
            choice_a, choice_b, choice_c, choice_d)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        seed_questions
    )
    print(f"Seeded {len(seed_questions)} quick quiz questions.")
else:
    print(f"Database already has {count} questions — skipping seed.")

con.commit()
con.close()
print("Database setup complete.")