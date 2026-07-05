# Adaptive SAT Prep Tool

This is a SAT prep and quiz platform built to support both structured SAT practice and fast, low-pressure practice through Quick Quiz mode. It combines a realistic test-taking experience with modern UI, AI-assisted question generation, and analytics-driven review.

## Features

- Full SAT-style practice flow
- Quick Quiz mode for short practice sessions
- AI-generated questions and explanations
- MathJax rendering for math content
- SQLite-backed question storage
- User progress tracking and quiz history
- Designed for a modern, mobile-friendly study experience

## Tech Stack

- Python
- Flask
- SQLite
- JavaScript
- HTML/CSS
- Groq API for AI generation
- MathJax for math rendering

## Local Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_new_api_key_here
```

4. Make sure your app loads environment variables:

```python
from dotenv import load_dotenv
load_dotenv()
```

5. Run the app:

```bash
python proj.py
```

## GitHub Setup

If you want Git to stop uploading private files like `.env`, add a `.gitignore` file in the project root with:

```gitignore
.env
quiz.db
__pycache__/
*.pyc
```

If `.env` was already committed before, Git will keep tracking it until you remove it from the index once:

```bash
git rm --cached .env
git rm --cached quiz.db
```

Then commit the `.gitignore` and push again.

## Deployment

This app needs a Python host such as Railway, Render, or another Flask-compatible service. For deployment, set `GROQ_API_KEY` in the host's environment variables instead of uploading `.env` to GitHub.

## Notes

- Do not commit `.env`
- Do not commit your live database if it contains private data
- Keep secrets in environment variables
- If you move files into subfolders later, update any database paths that point to `quiz.db`

