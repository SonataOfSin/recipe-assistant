"""Analytics API routes."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api_common import admin_user
from app.database import get_session
from app.models import Recipe, RecipeView

router = APIRouter()


# Admin analytics
@router.get("/analytics/popular-recipes")
async def popular_recipes(
    _: User = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
):
    rows = await session.execute(
        select(Recipe.title, func.count(RecipeView.id).label("views"))
        .outerjoin(RecipeView, RecipeView.recipe_id == Recipe.id)
        .group_by(Recipe.id)
        .order_by(func.count(RecipeView.id).desc(), Recipe.title)
        .limit(10)
    )
    return [{"title": title, "views": views} for title, views in rows.all()]
