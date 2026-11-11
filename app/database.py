"""Create the async database engine, sessions, and starter recipe data."""

from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy import event, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.catalog import get_catalog
from app.config import DATABASE_URL
from app.models import Base, Recipe
from app.safety import detect_allergens

if DATABASE_URL.startswith("sqlite"):
    database_path = make_url(DATABASE_URL).database
    if database_path and database_path != ":memory:":
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)

if engine.dialect.name == "sqlite":
    # SQLite does not enforce foreign keys unless this is enabled per connection.
    @event.listens_for(engine.sync_engine, "connect")
    def enable_sqlite_foreign_keys(connection, _record) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


async def initialize_database() -> None:
    async with engine.begin() as connection:
        if connection.dialect.name == "postgresql":
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await connection.run_sync(Base.metadata.create_all)

    # Keep the built-in catalog available on first run, and refresh derived allergens.
    async with SessionFactory() as session:
        recipes = list((await session.scalars(select(Recipe))).all())
        existing = set()
        for recipe in recipes:
            existing.add(recipe.title)
            allergens = detect_allergens(recipe.ingredients)
            if recipe.allergens != allergens:
                recipe.allergens = allergens
        for item in get_catalog():
            if item["title"] in existing:
                continue
            session.add(
                Recipe(
                    **item,
                    allergens=detect_allergens(item["ingredients"]),
                )
            )
        await session.commit()


async def get_session() -> AsyncIterator[AsyncSession]:
    # FastAPI dependencies use one session per request and close it afterward.
    async with SessionFactory() as session:
        yield session


async def close_database() -> None:
    await engine.dispose()
