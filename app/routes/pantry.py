"""Pantry API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api_common import current_user
from app.database import get_session
from app.models import PantryItem, User
from app.safety import normalize
from app.schemas import PantryCreate, PantryResponse

router = APIRouter()


# Pantry CRUD routes
@router.get("/pantry", response_model=list[PantryResponse])
async def list_pantry(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.scalars(
        select(PantryItem).where(PantryItem.user_id == user.id).order_by(PantryItem.name)
    )
    return list(result.all())


@router.post("/pantry", response_model=PantryResponse, status_code=201)
async def add_pantry_item(
    payload: PantryCreate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    name = normalize(payload.name)
    item = await session.scalar(
        select(PantryItem).where(PantryItem.user_id == user.id, PantryItem.name == name)
    )
    if item is not None:
        if item.unit != payload.unit and item.quantity is not None and payload.quantity is not None:
            raise HTTPException(status_code=409, detail="Use the same unit to update an existing pantry item.")
        if item.quantity is None or payload.quantity is None:
            item.quantity = payload.quantity
        else:
            item.quantity += payload.quantity
        item.unit = payload.unit or item.unit
    else:
        item = PantryItem(
            user_id=user.id,
            name=name,
            quantity=payload.quantity,
            unit=payload.unit,
        )
        session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


@router.delete("/pantry/{item_id}", status_code=204)
async def delete_pantry_item(
    item_id: int,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    item = await session.scalar(
        select(PantryItem).where(PantryItem.id == item_id, PantryItem.user_id == user.id)
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Pantry item not found.")
    await session.delete(item)
    await session.commit()


@router.put("/pantry/{item_id}", response_model=PantryResponse)
async def update_pantry_item(
    item_id: int,
    payload: PantryCreate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    item = await session.scalar(
        select(PantryItem).where(PantryItem.id == item_id, PantryItem.user_id == user.id)
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Pantry item not found.")
    name = normalize(payload.name)
    duplicate = await session.scalar(
        select(PantryItem).where(
            PantryItem.user_id == user.id,
            PantryItem.name == name,
            PantryItem.id != item_id,
        )
    )
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="That ingredient is already in your pantry.")
    item.name = name
    item.quantity = payload.quantity
    item.unit = payload.unit
    await session.commit()
    await session.refresh(item)
    return item
