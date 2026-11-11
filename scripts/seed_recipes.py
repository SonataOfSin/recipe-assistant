import asyncio
import argparse

from sqlalchemy import func, select

from app.config import GOOGLE_API_KEY
from app.database import SessionFactory, close_database, initialize_database
from app.models import Recipe


def recipe_document(recipe: Recipe) -> str:
    ingredients = ", ".join(item["name"] for item in recipe.ingredients)
    tags = ", ".join(recipe.diet_tags or [])
    return (
        f"{recipe.title}. {recipe.description}. Ingredients: {ingredients}. "
        f"Cuisine: {recipe.cuisine}. Meal: {recipe.meal_type}. Tags: {tags}."
    )


async def main(with_embeddings: bool) -> None:
    await initialize_database()
    async with SessionFactory() as session:
        recipes = list((await session.scalars(select(Recipe).order_by(Recipe.id))).all())
        if with_embeddings:
            if not GOOGLE_API_KEY:
                raise RuntimeError(
                    "Set GOOGLE_API_KEY in .env or the shared homework environment before embedding."
                )
            from app.retrieval import build_embedder

            embedder = build_embedder(GOOGLE_API_KEY)
            vectors = await embedder.aembed_documents(
                [recipe_document(recipe) for recipe in recipes]
            )
            for recipe, vector in zip(recipes, vectors, strict=True):
                recipe.embedding = vector
            await session.commit()
        count = await session.scalar(select(func.count()).select_from(Recipe))
    print(
        f"Recipe catalog ready: {count} recipes"
        + (" with embeddings." if with_embeddings else ".")
    )
    await close_database()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize the recipe catalog.")
    parser.add_argument(
        "--embeddings",
        action="store_true",
        help="Generate and store Gemini embeddings for semantic retrieval.",
    )
    arguments = parser.parse_args()
    asyncio.run(main(with_embeddings=arguments.embeddings))
