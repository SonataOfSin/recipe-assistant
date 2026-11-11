"""Load local settings and expose the values shared by the app modules."""

import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_settings() -> None:
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    # Reuse an existing local Gemini key for development without copying it here.
    shared_env = (
        PROJECT_ROOT.parent
        / "python_homeworks"
        / "python_homeworks-main"
        / ".env"
    )
    if shared_env.is_file():
        values = dotenv_values(shared_env)
        for key in ("GOOGLE_API_KEY", "GEMINI_API_KEY"):
            if values.get(key) and not os.getenv(key):
                os.environ[key] = str(values[key])


load_settings()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite+aiosqlite:///{PROJECT_ROOT / 'data' / 'recipe_assistant.db'}",
)
# SQLAlchemy's async engine needs the asyncpg driver in PostgreSQL URLs.
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://", "postgresql+asyncpg://", 1
    )

JWT_SECRET = os.getenv("JWT_SECRET", "local-development-secret-change-me")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "recipe-assistant")
