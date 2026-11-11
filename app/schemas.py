"""Pydantic models validate incoming API data and shape outgoing responses."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Allergen = Literal[
    "dairy", "nuts", "gluten", "eggs", "fish", "shellfish", "soy", "sesame", "mustard"
]
Diet = Literal["none", "vegetarian", "vegan", "gluten_free", "dairy_free"]

# Account and profile payloads
class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=10, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: Literal["user", "admin"]

    model_config = ConfigDict(from_attributes=True)


class ProfileUpdate(BaseModel):
    allergies: list[Allergen] = Field(default_factory=list, max_length=9)
    diet: Diet = "none"
    disliked_ingredients: list[str] = Field(default_factory=list, max_length=50)
    default_servings: int = Field(default=2, ge=1, le=20)


class ProfileResponse(ProfileUpdate):
    pass


# Pantry payloads
class PantryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    quantity: float | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, max_length=20)


class ShoppingItemUpdate(BaseModel):
    is_bought: bool


class PantryResponse(PantryCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)


# Recipe payloads
class RecipeIngredientInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=20)


class RecipeResponse(BaseModel):
    id: int | None = None
    title: str
    description: str
    cuisine: str
    meal_type: str
    servings: int
    total_time_min: int
    ingredients: list[RecipeIngredientInput]
    steps: list[str]
    diet_tags: list[str]
    allergens: list[str]
    source: Literal["catalog", "ai_generated"] = "catalog"
    pantry_match: float = 0
    missing_ingredients: list[str] = Field(default_factory=list)


class RecipeRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    max_recipes: int = Field(default=3, ge=1, le=5)


class RecipeCreate(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    description: str = Field(min_length=1, max_length=2000)
    cuisine: str = Field(default="International", max_length=50)
    meal_type: Literal["breakfast", "lunch", "dinner", "snack", "dessert"]
    servings: int = Field(default=2, ge=1, le=20)
    total_time_min: int = Field(gt=0, le=480)
    ingredients: list[RecipeIngredientInput] = Field(min_length=2, max_length=40)
    steps: list[str] = Field(min_length=2, max_length=30)
    diet_tags: list[str] = Field(default_factory=list)


class RecipeRecommendation(BaseModel):
    intent: str
    answer: str
    recipes: list[RecipeResponse]


# Saved recipes, shopping lists, and chat payloads
class ShoppingListCreate(BaseModel):
    recipe_id: int
    confirmed: bool


class CookbookSaveRequest(BaseModel):
    confirmed: bool
    note: str | None = Field(default=None, max_length=1000)


class ShoppingListItemResponse(BaseModel):
    name: str
    quantity: float
    unit: str
    is_bought: bool = False


class ShoppingListResponse(BaseModel):
    id: int
    title: str
    items: list[ShoppingListItemResponse]


class ChatSessionResponse(BaseModel):
    id: str
    title: str


class ChatMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=1000)


class ChatMessageResponse(BaseModel):
    id: int
    role: Literal["user", "assistant"]
    content: str
    recipes: list[RecipeResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
