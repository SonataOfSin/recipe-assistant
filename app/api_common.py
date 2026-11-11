"""Shared authentication and recipe helpers used by API routers."""

import time

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import Recipe, User
from app.safety import detect_allergens, is_safe_recipe, pantry_match, scale_recipe
from app.schemas import RecipeResponse
from app.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)
_message_timestamps: dict[int, list[float]] = {}


async def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    # Decode the bearer token, then load the account it identifies.
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_id = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The account for this token no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def admin_user(user: User = Depends(current_user)) -> User:
    # Authentication proves who the user is; this check enforces their role.
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access is required.")
    return user


def _recipe_data(recipe: Recipe) -> dict:
    # Derive allergens from ingredients instead of trusting stored/model claims.
    return {
        "id": recipe.id,
        "title": recipe.title,
        "description": recipe.description,
        "cuisine": recipe.cuisine,
        "meal_type": recipe.meal_type,
        "servings": recipe.servings,
        "total_time_min": recipe.total_time_min,
        "ingredients": recipe.ingredients,
        "steps": recipe.steps,
        "diet_tags": recipe.diet_tags,
        "allergens": detect_allergens(recipe.ingredients),
        "source": recipe.source,
        "embedding": recipe.embedding,
    }


def _present_recipe(recipe: dict, pantry: list[str], servings: int | None = None) -> RecipeResponse:
    score, missing = pantry_match(recipe["ingredients"], pantry)
    scaled = scale_recipe(recipe, servings) if servings and servings != recipe["servings"] else recipe
    return RecipeResponse(
        **{
            key: value
            for key, value in scaled.items()
            if key in RecipeResponse.model_fields
            and key not in {"allergens", "pantry_match", "missing_ingredients"}
        },
        allergens=detect_allergens(scaled["ingredients"]),
        pantry_match=score,
        missing_ingredients=missing,
    )


def _check_recipe_safety(recipe: dict, user: User) -> None:
    if not is_safe_recipe(
        recipe,
        allergies=user.allergies or [],
        diet=user.diet,
        disliked_ingredients=user.disliked_ingredients or [],
    ):
        raise HTTPException(
            status_code=409,
            detail="This recipe does not meet your current allergy, diet, or dislike settings.",
        )


def _record_message_rate(user_id: int) -> None:
    now = time.time()
    recent = [item for item in _message_timestamps.get(user_id, []) if now - item < 3600]
    if len(recent) >= 30:
        raise HTTPException(status_code=429, detail="Message limit reached: 30 per hour.")
    recent.append(now)
    _message_timestamps[user_id] = recent

