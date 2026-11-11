"""Recipes API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api_common import admin_user, current_user, _check_recipe_safety, _present_recipe, _record_message_rate, _recipe_data
from app.database import get_session
from app.models import PantryItem, Recipe, RecipeView, User
from app.safety import detect_allergens, is_safe_recipe
from app.schemas import RecipeCreate, RecipeRecommendation, RecipeRequest, RecipeResponse

router = APIRouter()


# Recipe catalog and recommendations
@router.get("/recipes", response_model=list[RecipeResponse])
async def list_recipes(
    search: str | None = Query(default=None, max_length=100),
    cuisine: str | None = Query(default=None, max_length=50),
    meal_type: str | None = Query(default=None, max_length=20),
    max_time: int | None = Query(default=None, ge=1, le=480),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    # Apply database filters first; personal safety rules are checked on each match.
    statement = select(Recipe).order_by(Recipe.title)
    if cuisine:
        statement = statement.where(Recipe.cuisine.ilike(f"%{cuisine}%"))
    if meal_type:
        statement = statement.where(Recipe.meal_type == meal_type)
    if max_time:
        statement = statement.where(Recipe.total_time_min <= max_time)
    result = await session.scalars(statement)
    pantry_items = await session.scalars(
        select(PantryItem.name).where(PantryItem.user_id == user.id)
    )
    pantry = list(pantry_items.all())
    search_term = search.casefold() if search else None
    visible = []
    for recipe in result.all():
        data = _recipe_data(recipe)
        if search_term and search_term not in (
            data["title"] + " " + data["description"] + " " + " ".join(
                item["name"] for item in data["ingredients"]
            )
        ).casefold():
            continue
        if not is_safe_recipe(
            data,
            allergies=user.allergies or [],
            diet=user.diet,
            disliked_ingredients=user.disliked_ingredients or [],
        ):
            continue
        visible.append(_present_recipe(data, pantry))
    # Slice after safety filtering so pages contain only recipes the user may see.
    start = (page - 1) * size
    return visible[start : start + size]


@router.get("/recipes/{recipe_id}", response_model=RecipeResponse)
async def get_recipe(
    recipe_id: int,
    servings: int | None = Query(default=None, ge=1, le=20),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    recipe = await session.get(Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found.")
    data = _recipe_data(recipe)
    _check_recipe_safety(data, user)
    pantry_rows = await session.scalars(
        select(PantryItem.name).where(PantryItem.user_id == user.id)
    )
    pantry = list(pantry_rows.all())
    await session.execute(
        RecipeView.__table__.insert().values(user_id=user.id, recipe_id=recipe.id)
    )
    await session.commit()
    return _present_recipe(data, pantry, servings)


@router.post("/recipes/recommend", response_model=RecipeRecommendation)
async def recommend_recipes(
    payload: RecipeRequest,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    _record_message_rate(user.id)
    catalog = await session.scalars(select(Recipe).order_by(Recipe.id))
    pantry_result = await session.scalars(
        select(PantryItem.name).where(PantryItem.user_id == user.id)
    )
    pantry = list(pantry_result.all())
    result = await request.app.state.graph.ainvoke(
        {
            "message": payload.message,
            "history": [],
            "profile": {
                "allergies": user.allergies or [],
                "diet": user.diet,
                "disliked_ingredients": user.disliked_ingredients or [],
                "default_servings": user.default_servings,
            },
            "previous_recipes": [],
            "candidates": [],
            "safe_recipes": [],
            "generated_recipe": None,
            "pantry": pantry,
            "catalog": [_recipe_data(recipe) for recipe in catalog.all()],
            "max_recipes": payload.max_recipes,
        },
        config={
            "configurable": {"thread_id": f"recommend-{user.id}"},
            "tags": ["recipe-assistant", "recommendation"],
            "metadata": {"session_id": "recommendation", "environment": "local"},
        },
    )
    recipes = [
        _present_recipe(recipe, pantry)
        for recipe in result.get("safe_recipes", [])
    ]
    for recipe in recipes:
        if recipe.id:
            session.add(RecipeView(user_id=user.id, recipe_id=recipe.id))
    await session.commit()
    return RecipeRecommendation(
        intent=result.get("analysis", {}).get("intent", "find_recipe"),
        answer=result["answer"],
        recipes=recipes,
    )


@router.post("/recipes", response_model=RecipeResponse, status_code=201)
async def create_recipe(
    payload: RecipeCreate,
    user: User = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
):
    recipe = Recipe(
        **payload.model_dump(),
        allergens=detect_allergens(payload.ingredients),
        source="catalog",
    )
    session.add(recipe)
    try:
        await session.commit()
        await session.refresh(recipe)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="A recipe with that title already exists.") from exc
    return _present_recipe(_recipe_data(recipe), [])


@router.delete("/recipes/{recipe_id}", status_code=204)
async def delete_recipe(
    recipe_id: int,
    user: User = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
):
    recipe = await session.get(Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found.")
    await session.delete(recipe)
    await session.commit()


@router.put("/recipes/{recipe_id}", response_model=RecipeResponse)
async def update_recipe(
    recipe_id: int,
    payload: RecipeCreate,
    user: User = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
):
    recipe = await session.get(Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found.")
    for key, value in payload.model_dump().items():
        setattr(recipe, key, value)
    recipe.allergens = detect_allergens(payload.ingredients)
    recipe.embedding = None
    try:
        await session.commit()
        await session.refresh(recipe)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="A recipe with that title already exists.") from exc
    return _present_recipe(_recipe_data(recipe), [])

