"""Health, authentication, and profile API routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api_common import current_user
from app.config import GOOGLE_API_KEY
from app.database import get_session
from app.models import User
from app.schemas import LoginRequest, ProfileResponse, ProfileUpdate, RegisterRequest, TokenResponse, UserResponse
from app.security import create_access_token, hash_password, verify_password

router = APIRouter()


# Health checks and account/profile routes
@router.get("/")
async def root():
    return {"service": "Recipe Assistant", "status": "running", "ai_enabled": bool(GOOGLE_API_KEY)}


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/auth/register", response_model=UserResponse, status_code=201)
async def register(payload: RegisterRequest, session: AsyncSession = Depends(get_session)):
    email = str(payload.email).strip().lower()
    user = User(
        email=email,
        full_name=payload.full_name.strip(),
        hashed_password=hash_password(payload.password),
    )
    session.add(user)
    try:
        await session.commit()
        await session.refresh(user)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="An account with that email already exists.") from exc
    return user


@router.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_session)):
    email = str(payload.email).strip().lower()
    user = await session.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Email or password is incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/auth/me", response_model=UserResponse)
async def read_me(user: User = Depends(current_user)):
    return user


@router.get("/profile", response_model=ProfileResponse)
async def get_profile(user: User = Depends(current_user)):
    return ProfileResponse(
        allergies=user.allergies or [],
        diet=user.diet,
        disliked_ingredients=user.disliked_ingredients or [],
        default_servings=user.default_servings,
    )


@router.put("/profile", response_model=ProfileResponse)
async def update_profile(
    payload: ProfileUpdate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    user.allergies = sorted(set(payload.allergies))
    user.diet = payload.diet
    user.disliked_ingredients = sorted(
        {item.strip() for item in payload.disliked_ingredients if item.strip()}
    )
    user.default_servings = payload.default_servings
    await session.commit()
    return await get_profile(user)

