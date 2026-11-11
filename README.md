# Recipe Assistant

A local-first recipe assistant built as a separate Desktop repository. It uses
the FastAPI, LangGraph, LangChain, PostgreSQL, and Streamlit patterns explored
in the `tumana/PP-39-master` lessons without changing those lesson files.

For an English file-by-file walkthrough and demo script, see
[DEMO_GUIDE.md](./DEMO_GUIDE.md).

## Run locally

From a terminal:

```bash
cd ~/Desktop/recipe-assistant
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
[ -f .env ] || cp .env.example .env
python main.py
```

For app-only local use, install `requirements.txt` instead. It uses SQLite by
default. If you configure a local PostgreSQL `DATABASE_URL`, install the
additional drivers with `python -m pip install -r requirements-postgres.txt`.

Open the Streamlit URL printed in the terminal (normally
`http://127.0.0.1:8501`). Create an account in the app. `main.py` starts the
API and UI together, chooses free ports if the defaults are already occupied,
waits for the API health check, and stops both processes on Ctrl+C.

If `GOOGLE_API_KEY` is available in this repository's `.env`, or in the
existing shared `python_homeworks/python_homeworks-main/.env`, Gemini analyzes
natural-language requests and can draft a recipe when the safe catalog search
finds no match. The key is read locally and is never copied into this project.
Without a key, the catalog, pantry, profile, and rule-based request flow still
work for local demonstrations.

## PostgreSQL / Docker

Docker Compose runs FastAPI, Streamlit, and PostgreSQL with the pgvector
extension:

```bash
[ -f .env ] || cp .env.example .env
docker compose up --build
```

The Docker image installs `requirements-postgres.txt`; local SQLite runs do not
need the PostgreSQL drivers or PostgreSQL checkpoint package.

The Compose database URL is set for the app container and does not expose the
database port outside the local machine. The regular local launcher defaults
to SQLite; `DATABASE_URL` can point it at PostgreSQL instead.

## What is implemented

- Registration, login, signed JWTs, user/admin roles, per-user profile and
  pantry data, persisted chat history, saved recipes, and shopping lists.
- The recipe catalog supports dish/ingredient search, cuisine, meal type, and
  maximum cooking-time filters.
- LangGraph request analysis, catalog retrieval, code-enforced safety
  filtering, grounded recipe responses, and optional structured Gemini recipe
  drafting. The seeded catalog contains 31 varied recipes.
- PostgreSQL schema includes a pgvector embedding column; SQLite stores
  embeddings as JSON for development. Catalog search combines strict
  constraints, text matching, optional Gemini semantic similarity, and a
  deterministic pantry-match score. Embeddings are opt-in because they use
  the Gemini API; run `python -m scripts.seed_recipes --embeddings` once with
  a configured key to enable semantic ranking.
- The LangGraph conversation checkpoint is stored in PostgreSQL when using
  Postgres and in a local SQLite checkpoint file in development. Chat
  messages are also stored in the application database, independently.
- Persistent actions (cookbook saves and shopping lists) require an explicit
  confirmation request; shopping-list quantities and missing ingredients are
  calculated by the server, not the language model.
- Allergy and diet restrictions are not relaxed. Allergens are recalculated
  from ingredient names in Python, including for generated recipes; the
  model's own allergen claims are not trusted. Ingredient-label and
  cross-contamination checks remain important for real-world allergies.
- LangSmith tracing is opt-in. When enabled, traces can contain the user's
  request, pantry, and dietary preferences. Avoid enabling it for sensitive
  personal data unless that data handling is acceptable.

## Admin account

To create the first admin account at startup, set both `ADMIN_EMAIL` and
`ADMIN_PASSWORD` in `.env`; the password must have at least 10 characters.
Public registration always creates a regular user. Admin-only catalog
management and analytics are checked on the API, not just hidden in the UI.

## API and tests

- Interactive API documentation: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`
- Focused tests: `pytest`
- Initialize / seed the starter catalog explicitly: `python -m scripts.seed_recipes`

The API persists the message before invoking Gemini, so an LLM/provider error
does not silently discard the user's message. Allergy settings are loaded
from the authenticated account and cannot be changed through chat prompts.
