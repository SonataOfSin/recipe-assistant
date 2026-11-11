"""Chat API routes."""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api_common import current_user, _present_recipe, _record_message_rate, _recipe_data
from app.database import get_session
from app.models import ChatMessage, ChatSession, PantryItem, Recipe, RecipeView, User
from app.schemas import ChatMessageRequest, ChatMessageResponse, ChatSessionResponse

router = APIRouter()


# Persistent chat sessions
@router.post("/chat/sessions", response_model=ChatSessionResponse, status_code=201)
async def create_chat_session(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    chat = ChatSession(id=str(uuid4()), user_id=user.id)
    session.add(chat)
    await session.commit()
    return ChatSessionResponse(id=chat.id, title=chat.title)


@router.get("/chat/sessions", response_model=list[ChatSessionResponse])
async def list_chat_sessions(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    rows = await session.scalars(
        select(ChatSession)
        .where(ChatSession.user_id == user.id)
        .order_by(ChatSession.created_at.desc())
    )
    return [ChatSessionResponse(id=row.id, title=row.title) for row in rows.all()]


@router.get(
    "/chat/sessions/{session_id}/messages",
    response_model=list[ChatMessageResponse],
)
async def read_chat_messages(
    session_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    chat = await session.scalar(
        select(ChatSession).where(
            ChatSession.id == session_id, ChatSession.user_id == user.id
        )
    )
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    rows = await session.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    return list(rows.all())


@router.post(
    "/chat/sessions/{session_id}/messages",
    response_model=ChatMessageResponse,
)
async def send_chat_message(
    session_id: str,
    payload: ChatMessageRequest,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    # Verify ownership before reading or changing this conversation.
    _record_message_rate(user.id)
    chat = await session.scalar(
        select(ChatSession).where(
            ChatSession.id == session_id, ChatSession.user_id == user.id
        )
    )
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    history_rows = await session.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(10)
    )
    recent_messages = list(reversed(list(history_rows.all())))
    history = [
        {
            "role": message.role,
            "content": message.content
            + (
                "\nRecipes shown: "
                + "; ".join(
                    f"{index}. {recipe['title']}"
                    for index, recipe in enumerate(message.recipes, start=1)
                )
                if message.role == "assistant" and message.recipes
                else ""
            ),
        }
        for message in recent_messages
    ]
    previous_recipes = next(
        (
            message.recipes
            for message in reversed(recent_messages)
            if message.role == "assistant" and message.recipes
        ),
        [],
    )
    user_message = ChatMessage(
        session_id=session_id,
        role="user",
        content=payload.content.strip(),
        recipes=[],
    )
    session.add(user_message)
    if chat.title == "Recipe chat":
        chat.title = payload.content.strip()[:100]
    # Save the user's message before calling the model so provider errors don't lose it.
    await session.commit()

    catalog = await session.scalars(select(Recipe).order_by(Recipe.id))
    pantry_rows = await session.scalars(
        select(PantryItem.name).where(PantryItem.user_id == user.id)
    )
    pantry = list(pantry_rows.all())
    result = await request.app.state.graph.ainvoke(
        {
            "message": payload.content.strip(),
            "history": history,
            "profile": {
                "allergies": user.allergies or [],
                "diet": user.diet,
                "disliked_ingredients": user.disliked_ingredients or [],
                "default_servings": user.default_servings,
            },
            "previous_recipes": previous_recipes,
            "candidates": [],
            "safe_recipes": [],
            "generated_recipe": None,
            "pantry": pantry,
            "catalog": [_recipe_data(recipe) for recipe in catalog.all()],
            "max_recipes": 3,
        },
        config={
            "configurable": {"thread_id": f"chat-{session_id}"},
            "tags": ["recipe-assistant", "chat"],
            "metadata": {
                "session_id": session_id,
                "intent": "pending",
                "environment": "local",
            },
        },
    )
    answer_recipes = result.get("safe_recipes", [])
    response_recipes = [
        _present_recipe(recipe, pantry) for recipe in answer_recipes
    ]
    response = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=result["answer"],
        recipes=[recipe.model_dump() for recipe in response_recipes],
    )
    session.add(response)
    for recipe in response_recipes:
        if recipe.id:
            session.add(RecipeView(user_id=user.id, recipe_id=recipe.id))
    await session.commit()
    await session.refresh(response)
    return response


@router.delete("/chat/sessions/{session_id}", status_code=204)
async def delete_chat_session(
    session_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    chat = await session.scalar(
        select(ChatSession).where(
            ChatSession.id == session_id, ChatSession.user_id == user.id
        )
    )
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    await session.delete(chat)
    await session.commit()

