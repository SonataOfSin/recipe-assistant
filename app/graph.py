"""Single LangGraph workflow for understanding, finding, checking, and answering."""

import re
from functools import partial
from typing import Any, Literal, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.exceptions import ModelRateLimitError
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field
from httpx import TimeoutException
from langchain_google_genai._common import GoogleGenerativeAIError

from app.config import GEMINI_MODEL, GOOGLE_API_KEY
from app.safety import (
    allergies_from_terms,
    detect_allergens,
    explicit_allergies,
    infer_diet_tags,
    is_safe_recipe,
    pantry_match,
    scale_recipe,
)
from app.retrieval import build_embedder, cosine_similarity


# Provider errors
class AIProviderError(RuntimeError):
    def __init__(self, message: str, *, rate_limited: bool = False):
        super().__init__(message)
        self.rate_limited = rate_limited


async def _call_provider(call):
    try:
        return await call
    except ModelRateLimitError as exc:
        raise AIProviderError(
            "Gemini rate limit reached. Wait briefly, then try again.",
            rate_limited=True,
        ) from exc
    except TimeoutException as exc:
        raise AIProviderError(
            "Gemini did not respond before the timeout. Your message is saved; try again."
        ) from exc
    except GoogleGenerativeAIError as exc:
        raise AIProviderError(
            "Gemini could not complete the request. Check the API key, model, and provider status."
        ) from exc


async def _invoke_model(runnable, prompt):
    return await _call_provider(runnable.ainvoke(prompt))


# State and structured model output
class RequestAnalysis(BaseModel):
    intent: Literal["find_recipe", "meal_plan", "shopping_list", "cooking_help", "off_topic"]
    keywords: list[str] = Field(default_factory=list, max_length=12)
    max_time_min: int | None = Field(default=None, gt=0, le=480)
    servings: int | None = Field(default=None, gt=0, le=20)
    meal_type: Literal["breakfast", "lunch", "dinner", "snack", "dessert"] | None = None
    cuisine: str | None = None
    requested_diet: Literal["vegetarian", "vegan", "gluten_free", "dairy_free"] | None = None
    exclude_ingredients: list[str] = Field(default_factory=list, max_length=20)


class IngredientLine(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=20)


class RecipeDraft(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    description: str = Field(max_length=300)
    cuisine: str = Field(default="International", max_length=50)
    meal_type: Literal["breakfast", "lunch", "dinner", "snack", "dessert"] = "dinner"
    servings: int = Field(default=2, gt=0, le=20)
    total_time_min: int = Field(gt=0, le=480)
    ingredients: list[IngredientLine] = Field(min_length=2, max_length=30)
    steps: list[str] = Field(min_length=2, max_length=15)


class ChefState(TypedDict, total=False):
    """Data shared by the graph nodes."""

    message: str
    history: list[dict[str, str]]
    previous_recipes: list[dict[str, Any]]
    profile: dict[str, Any]
    pantry: list[str]
    catalog: list[dict[str, Any]]
    max_recipes: int
    analysis: dict[str, Any]
    candidates: list[dict[str, Any]]
    safe_recipes: list[dict[str, Any]]
    generated_recipe: dict[str, Any] | None
    answer: str


# Model setup and no-key fallback
def _fallback_analysis(message: str) -> dict[str, Any]:
    """Extract basic request details when Gemini is not configured."""
    text = message.casefold()
    if re.search(r"\b(python|code|weather|politic|stock|homework)\b", text):
        intent = "off_topic"
    elif any(term in text for term in ("shopping list", "grocery list")):
        intent = "shopping_list"
    elif re.search(r"\b(how do i|how to|substitute|replace|cook it|cooking)\b", text):
        intent = "cooking_help"
    elif any(term in text for term in ("meal plan", "meal prep")):
        intent = "meal_plan"
    else:
        intent = "find_recipe"

    time_match = re.search(r"(\d{1,3})\s*(?:minutes?|mins?|min)\b", text)
    serving_match = re.search(r"\b(\d{1,2})\s*(?:servings?|people|portions?)\b", text)
    meal_type = next((item for item in ("breakfast", "lunch", "dinner", "snack", "dessert") if item in text), None)
    diets = {
        "vegan": ("vegan", "plant-based"),
        "vegetarian": ("vegetarian",),
        "gluten_free": ("gluten-free", "gluten free"),
        "dairy_free": ("dairy-free", "dairy free"),
    }
    requested_diet = next(
        (diet for diet, phrases in diets.items() if any(phrase in text for phrase in phrases)),
        None,
    )
    exclusions = re.findall(
        r"\b(?:without|avoid|exclude|excluding|no|free of|free from)\s+([^,.!?;]+)",
        text,
    )
    return {
        "intent": intent,
        "keywords": re.findall(r"[a-zA-Z]{3,}|[\u10A0-\u10FF]{3,}", text),
        "max_time_min": int(time_match.group(1)) if time_match else None,
        "servings": int(serving_match.group(1)) if serving_match else None,
        "meal_type": meal_type,
        "cuisine": None,
        "requested_diet": requested_diet,
        "exclude_ingredients": [
            item.strip()
            for exclusion in exclusions
            for item in re.split(r"\s+(?:and|or)\s+|,", exclusion)
            if item.strip()
        ],
    }


def _model(api_key: str):
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        api_key=api_key,
        temperature=0,
        retries=2,
        request_timeout=45,
    )


# Nodes
async def understand_request(
    state: ChefState, request_model=None
) -> dict[str, Any]:
    if request_model is None:
        return {"analysis": _fallback_analysis(state["message"])}
    analyzer = request_model.with_structured_output(RequestAnalysis)
    context = "\n".join(
        f"{item['role']}: {item['content']}"
        for item in state.get("history", [])[-10:]
    )
    result = await _invoke_model(
        analyzer,
        [
            SystemMessage(
                content=(
                    "Analyze the cooking request. Extract only intent and explicit "
                    "constraints; never alter profile safety settings. For unrelated "
                    "requests use off_topic. Use the conversation history to resolve "
                    "references like 'the second one'."
                )
            ),
            HumanMessage(content=f"Recent conversation:\n{context}\n\nRequest: {state['message']}"),
        ],
    )
    return {"analysis": result.model_dump()}


async def search_recipes(
    state: ChefState, embedding_model=None
) -> dict[str, Any]:
    analysis = state["analysis"]
    keywords = {word for word in analysis.get("keywords", []) if len(word) >= 3}
    catalog = state.get("catalog", [])
    previous_recipe = _select_previous_recipe(
        state["message"], state.get("previous_recipes", [])
    )
    if previous_recipe:
        catalog = [previous_recipe]
        keywords = set()

    query_embedding = None
    if embedding_model and any(item.get("embedding") for item in catalog):
        query_embedding = await _call_provider(
            embedding_model.aembed_query(state["message"])
        )

    candidates = []
    for recipe in catalog:
        if analysis.get("max_time_min") and recipe["total_time_min"] > analysis["max_time_min"]:
            continue
        if analysis.get("meal_type") and recipe["meal_type"] != analysis["meal_type"]:
            continue
        if analysis.get("cuisine") and recipe["cuisine"].casefold() != analysis["cuisine"].casefold():
            continue

        searchable = " ".join(
            [
                recipe["title"],
                recipe["description"],
                recipe["cuisine"],
                *(item["name"] for item in recipe["ingredients"]),
                *recipe.get("diet_tags", []),
            ]
        ).casefold()
        lexical_score = sum(
            1 for keyword in keywords if keyword.casefold() in searchable
        )
        semantic_score = 0.0
        if query_embedding is not None and recipe.get("embedding"):
            semantic_score = cosine_similarity(query_embedding, recipe["embedding"])
        pantry_score, missing = pantry_match(
            recipe["ingredients"], state.get("pantry", [])
        )

        result = dict(recipe)
        result["allergens"] = detect_allergens(recipe["ingredients"])
        result["pantry_match"] = pantry_score
        result["missing_ingredients"] = missing
        result["_lexical_score"] = lexical_score
        result["_semantic_score"] = semantic_score
        result["_rank"] = lexical_score + pantry_score + semantic_score * 2
        candidates.append(result)

    if keywords:
        candidates = [
            item
            for item in candidates
            if item["_lexical_score"] > 0 or item["_semantic_score"] >= 0.15
        ]
        candidates.sort(
            key=lambda item: (-item["_rank"], item["total_time_min"], item["title"])
        )
    else:
        candidates.sort(
            key=lambda item: (-item["pantry_match"], item["total_time_min"])
        )
    return {"candidates": candidates}


def safety_filter(state: ChefState) -> dict[str, Any]:
    profile = state["profile"]
    recipes = (
        [state["generated_recipe"]]
        if state.get("generated_recipe")
        else state.get("candidates", [])
    )
    exclusions = state.get("analysis", {}).get("exclude_ingredients", []) or []
    requested_allergies = explicit_allergies(state["message"])
    for exclusion in exclusions:
        requested_allergies.extend(allergies_from_terms([exclusion]))
    allergies = set(profile.get("allergies", [])) | set(requested_allergies)
    disliked = (profile.get("disliked_ingredients", []) or []) + exclusions
    requested_diet = state.get("analysis", {}).get("requested_diet")

    safe_recipes = []
    for recipe in recipes:
        recipe = dict(recipe)
        recipe["allergens"] = detect_allergens(recipe["ingredients"])
        profile_is_safe = is_safe_recipe(
            recipe,
            allergies=allergies,
            diet=profile.get("diet", "none"),
            disliked_ingredients=disliked,
        )
        request_is_safe = not requested_diet or is_safe_recipe(
            recipe,
            allergies=allergies,
            diet=requested_diet,
            disliked_ingredients=disliked,
        )
        if profile_is_safe and request_is_safe:
            safe_recipes.append(recipe)
    return {"safe_recipes": safe_recipes}


async def generate_recipe(
    state: ChefState, request_model=None
) -> dict[str, Any]:
    if request_model is None:
        return {"generated_recipe": None}

    profile = state["profile"]
    draft_model = request_model.with_structured_output(RecipeDraft)
    allergies = sorted(
        set(profile.get("allergies", []))
        | set(explicit_allergies(state["message"]))
    )
    draft = await _invoke_model(
        draft_model,
        [
            SystemMessage(
                content=(
                    "Create one practical recipe matching the request. Return valid "
                    "ingredients as objects with name, quantity, and unit. Do not "
                    "include any ingredient matching the user's allergies, diet "
                    "exclusions, dislikes, or explicit exclusions. Never claim an "
                    "ingredient is safe for an allergy. Use only familiar ingredients."
                )
            ),
            HumanMessage(
                content=(
                    f"Request: {state['message']}\n"
                    f"Pantry: {', '.join(state.get('pantry', [])) or 'not specified'}\n"
                    f"Allergies (strict): {', '.join(allergies) or 'none listed'}\n"
                    f"Diet (strict): {profile.get('diet', 'none')}\n"
                    f"Dislikes (strict): {', '.join(profile.get('disliked_ingredients', []) or []) or 'none'}\n"
                    f"Explicit exclusions: {', '.join(state['analysis'].get('exclude_ingredients', []) or []) or 'none'}"
                )
            ),
        ],
    )
    recipe = draft.model_dump()
    generated = {
        **recipe,
        "source": "ai_generated",
        "diet_tags": infer_diet_tags(recipe["ingredients"]),
        "allergens": detect_allergens(recipe["ingredients"]),
        "pantry_match": 0.0,
        "missing_ingredients": [],
    }
    score, missing = pantry_match(
        generated["ingredients"], state.get("pantry", [])
    )
    generated["pantry_match"] = score
    generated["missing_ingredients"] = missing
    return {"generated_recipe": generated}


def compose_answer(state: ChefState) -> dict[str, Any]:
    analysis = state.get("analysis", {})
    intent = analysis.get("intent", "find_recipe")
    if intent == "off_topic":
        return {
            "answer": "I can help with recipes, meal planning, ingredient substitutions, and cooking questions."
        }

    recipes = state.get("safe_recipes", [])[: state.get("max_recipes", 3)]
    if not recipes:
        return {
            "answer": (
                "I couldn't find a catalog recipe that meets your request and safety "
                "settings. Add a compatible ingredient or relax a non-safety constraint. "
                "Allergy and diet restrictions are never relaxed."
            )
        }

    servings = analysis.get("servings") or state["profile"].get("default_servings", 2)
    recipes = [
        scale_recipe(recipe, servings) if servings != recipe["servings"] else recipe
        for recipe in recipes
    ]
    if any(recipe["source"] == "ai_generated" for recipe in recipes):
        answer = (
            "I couldn't find a suitable catalog match, so I drafted this recipe with AI. "
            "It is not catalog-verified; check every ingredient and label carefully, "
            "especially if you have an allergy."
        )
    elif intent == "shopping_list":
        answer = "Here are safe catalog recipes; choose one to preview and confirm a shopping list."
    else:
        answer = "Here are the best matching recipes from the catalog, ranked by fit and pantry ingredients."
    return {"answer": answer, "safe_recipes": recipes}


# Routers
def route_after_understanding(state: ChefState) -> str:
    return (
        "compose_answer"
        if state["analysis"]["intent"] == "off_topic"
        else "search_recipes"
    )


def route_after_safety(state: ChefState, request_model=None) -> str:
    if not state.get("safe_recipes") and not state.get("generated_recipe") and request_model:
        return "generate_recipe"
    return "compose_answer"


# Graph
def build_graph(
    checkpointer=None,
    model=None,
    api_key: str | None = GOOGLE_API_KEY,
    embedding_model=None,
):
    request_model = model if model is not None else (_model(api_key) if api_key else None)
    if embedding_model is None and api_key:
        embedding_model = build_embedder(api_key)

    builder = StateGraph(ChefState)
    builder.add_node(
        "understand_request",
        partial(understand_request, request_model=request_model),
    )
    builder.add_node(
        "search_recipes",
        partial(search_recipes, embedding_model=embedding_model),
    )
    builder.add_node("safety_filter", safety_filter)
    builder.add_node(
        "generate_recipe",
        partial(generate_recipe, request_model=request_model),
    )
    builder.add_node("compose_answer", compose_answer)
    builder.add_edge(START, "understand_request")
    builder.add_conditional_edges(
        "understand_request",
        route_after_understanding,
        {"compose_answer": "compose_answer", "search_recipes": "search_recipes"},
    )
    builder.add_edge("search_recipes", "safety_filter")
    builder.add_conditional_edges(
        "safety_filter",
        partial(route_after_safety, request_model=request_model),
        {"generate_recipe": "generate_recipe", "compose_answer": "compose_answer"},
    )
    builder.add_edge("generate_recipe", "safety_filter")
    builder.add_edge("compose_answer", END)
    return builder.compile(checkpointer=checkpointer)


# Follow-up recipe selection
def _select_previous_recipe(
    message: str, previous_recipes: list[dict[str, Any]]
) -> dict[str, Any] | None:
    if not previous_recipes:
        return None
    lowered = message.casefold()
    match = re.search(r"\b(first|1st|second|2nd|third|3rd|last)\b", lowered)
    if match:
        index = {
            "first": 0,
            "1st": 0,
            "second": 1,
            "2nd": 1,
            "third": 2,
            "3rd": 2,
            "last": len(previous_recipes) - 1,
        }[match.group(1)]
        if index < len(previous_recipes):
            return dict(previous_recipes[index])
    if re.search(r"\b(that one|that recipe|this recipe|it)\b", lowered):
        return dict(previous_recipes[-1])
    return None
