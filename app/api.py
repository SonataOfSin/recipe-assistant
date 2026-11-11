"""FastAPI application setup and shared service lifecycle."""

import logging
import os
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.config import DATABASE_URL, GOOGLE_API_KEY, PROJECT_ROOT
from app.database import SessionFactory, close_database, initialize_database
from app.graph import AIProviderError, build_graph
from app.models import User
from app.routes import (
    accounts_router,
    analytics_router,
    chat_router,
    library_router,
    pantry_router,
    recipes_router,
)
from app.security import hash_password

logger = logging.getLogger("recipe_assistant")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Prepare the app database and LangGraph's persistent conversation checkpoint.
    await initialize_database()
    await _ensure_admin_user()
    async with AsyncExitStack() as stack:
        if DATABASE_URL.startswith("postgresql"):
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            from psycopg.rows import dict_row
            from psycopg_pool import AsyncConnectionPool

            connection_url = DATABASE_URL.replace("+asyncpg", "")
            pool = AsyncConnectionPool(
                conninfo=connection_url,
                min_size=1,
                max_size=5,
                kwargs={
                    "autocommit": True,
                    "prepare_threshold": 0,
                    "row_factory": dict_row,
                },
                open=False,
            )
            await pool.open(wait=True)
            stack.push_async_callback(pool.close)
            checkpointer = AsyncPostgresSaver(pool)
            await checkpointer.setup()
        else:
            from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

            checkpoint_path = PROJECT_ROOT / "data" / "langgraph-checkpoints.sqlite"
            checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            checkpointer = await stack.enter_async_context(
                AsyncSqliteSaver.from_conn_string(str(checkpoint_path))
            )
            await checkpointer.setup()

        app.state.graph = build_graph(checkpointer=checkpointer)
        try:
            yield
        finally:
            await close_database()


app = FastAPI(
    title="Recipe Assistant",
    description="A personalized cooking assistant with deterministic allergy safeguards.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(AIProviderError)
async def ai_provider_error_handler(_: Request, exc: AIProviderError):
    logger.warning("Gemini request failed: %s", exc)
    code = 429 if exc.rate_limited else 503
    return JSONResponse(status_code=code, content={"detail": str(exc)})


async def _ensure_admin_user() -> None:
    email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("ADMIN_PASSWORD", "")
    if not email and not password:
        return
    if not email or len(password) < 10:
        raise RuntimeError("Set both ADMIN_EMAIL and an ADMIN_PASSWORD of at least 10 characters.")
    async with SessionFactory() as session:
        user = await session.scalar(select(User).where(User.email == email))
        if user is None:
            session.add(
                User(
                    email=email,
                    full_name="Recipe Assistant Admin",
                    hashed_password=hash_password(password),
                    role="admin",
                )
            )
            await session.commit()

for route_group in (
    accounts_router,
    pantry_router,
    recipes_router,
    library_router,
    chat_router,
    analytics_router,
):
    app.include_router(route_group)
