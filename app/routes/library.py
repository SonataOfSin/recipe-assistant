"""Library API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api_common import current_user, _check_recipe_safety, _present_recipe, _recipe_data
from app.database import get_session
from app.models import PantryItem, Recipe, SavedRecipe, ShoppingList, User
from app.safety import is_safe_recipe, normalize
from app.schemas import CookbookSaveRequest, RecipeResponse, ShoppingItemUpdate, ShoppingListCreate, ShoppingListResponse

router = APIRouter()


# Saved recipes and shopping lists
@router.post("/cookbook/{recipe_id}", status_code=201)
async def save_recipe(
    recipe_id: int,
    payload: CookbookSaveRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    # Saving changes account data, so require a separate explicit confirmation.
    if not payload.confirmed:
        raise HTTPException(status_code=400, detail="Explicit confirmation is required to save a recipe.")
    recipe = await session.get(Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found.")
    _check_recipe_safety(_recipe_data(recipe), user)
    saved = await session.scalar(
        select(SavedRecipe).where(
            SavedRecipe.user_id == user.id, SavedRecipe.recipe_id == recipe_id
        )
    )
    if saved is None:
        session.add(
            SavedRecipe(user_id=user.id, recipe_id=recipe_id, note=payload.note)
        )
        await session.commit()
    return {"saved": True, "recipe_id": recipe_id}


@router.delete("/cookbook/{recipe_id}", status_code=204)
async def remove_saved_recipe(
    recipe_id: int,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    saved = await session.scalar(
        select(SavedRecipe).where(
            SavedRecipe.user_id == user.id, SavedRecipe.recipe_id == recipe_id
        )
    )
    if saved is None:
        raise HTTPException(status_code=404, detail="Saved recipe not found.")
    await session.delete(saved)
    await session.commit()


@router.get("/cookbook", response_model=list[RecipeResponse])
async def list_cookbook(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    statement = (
        select(Recipe)
        .join(SavedRecipe, SavedRecipe.recipe_id == Recipe.id)
        .where(SavedRecipe.user_id == user.id)
        .order_by(SavedRecipe.saved_at.desc())
    )
    recipes = await session.scalars(statement)
    result = []
    for recipe in recipes.all():
        data = _recipe_data(recipe)
        if is_safe_recipe(
            data,
            allergies=user.allergies or [],
            diet=user.diet,
            disliked_ingredients=user.disliked_ingredients or [],
        ):
            result.append(_present_recipe(data, []))
    return result


@router.post("/shopping-lists", response_model=ShoppingListResponse, status_code=201)
async def create_shopping_list(
    payload: ShoppingListCreate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    # Build the list on the server from the safe recipe and the user's pantry.
    if not payload.confirmed:
        raise HTTPException(status_code=400, detail="Explicit confirmation is required to save a shopping list.")
    recipe = await session.get(Recipe, payload.recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found.")
    data = _recipe_data(recipe)
    _check_recipe_safety(data, user)
    pantry_rows = await session.scalars(
        select(PantryItem.name).where(PantryItem.user_id == user.id)
    )
    pantry = set(normalize(name) for name in pantry_rows.all())
    items = [
        {
            "name": item["name"],
            "quantity": item["quantity"],
            "unit": item["unit"],
            "is_bought": False,
        }
        for item in data["ingredients"]
        if normalize(item["name"]) not in pantry
        and normalize(item["name"]) not in {"salt", "pepper", "water", "oil", "olive oil", "მარილი", "წყალი", "ზეთი"}
    ]
    shopping_list = ShoppingList(
        user_id=user.id,
        title=f"Ingredients for {recipe.title}",
        items=items,
    )
    session.add(shopping_list)
    await session.commit()
    await session.refresh(shopping_list)
    return ShoppingListResponse(id=shopping_list.id, title=shopping_list.title, items=items)


@router.get("/shopping-lists", response_model=list[ShoppingListResponse])
async def list_shopping_lists(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    rows = await session.scalars(
        select(ShoppingList)
        .where(ShoppingList.user_id == user.id)
        .order_by(ShoppingList.created_at.desc())
    )
    return [
        ShoppingListResponse(id=row.id, title=row.title, items=row.items)
        for row in rows.all()
    ]


@router.patch("/shopping-lists/{list_id}/items/{item_index}")
async def update_shopping_item(
    list_id: int,
    item_index: int,
    payload: ShoppingItemUpdate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    shopping_list = await session.scalar(
        select(ShoppingList).where(
            ShoppingList.id == list_id, ShoppingList.user_id == user.id
        )
    )
    if shopping_list is None:
        raise HTTPException(status_code=404, detail="Shopping list not found.")
    items = list(shopping_list.items)
    if item_index < 0 or item_index >= len(items):
        raise HTTPException(status_code=404, detail="Shopping list item not found.")
    items[item_index]["is_bought"] = payload.is_bought
    shopping_list.items = items
    await session.commit()
    return {"updated": True}


@router.delete("/shopping-lists/{list_id}", status_code=204)
async def delete_shopping_list(
    list_id: int,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    shopping_list = await session.scalar(
        select(ShoppingList).where(
            ShoppingList.id == list_id, ShoppingList.user_id == user.id
        )
    )
    if shopping_list is None:
        raise HTTPException(status_code=404, detail="Shopping list not found.")
    await session.delete(shopping_list)
    await session.commit()
