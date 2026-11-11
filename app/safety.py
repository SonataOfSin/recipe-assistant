"""Deterministic ingredient checks shared by search and AI-generated recipes."""

import re
import unicodedata
from collections.abc import Iterable
from typing import Any


# These ingredient-name rules run in Python; model-provided safety claims are ignored.
ALLERGEN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "dairy": (
        "milk", "butter", "cheese", "mozzarella", "parmesan", "feta", "gouda",
        "cheddar", "blue cheese", "cream", "yogurt", "yoghurt", "buttermilk",
        "ghee", "whey", "casein", "რძე", "ყველი", "კარაქი", "მაწონი", "არაჟანი",
    ),
    "nuts": (
        "almond", "almonds", "walnut", "walnuts", "hazelnut", "hazelnuts",
        "cashew", "cashews", "pistachio", "pistachios", "pecan", "pecans",
        "peanut", "peanuts", "nut", "nuts", "mixed nuts", "marzipan", "pesto",
        "ნიგოზი", "თხილი", "ნუში", "არაქისი",
    ),
    "gluten": (
        "wheat", "barley", "rye", "flour", "bread", "pasta", "couscous",
        "bulgur", "seitan", "soy sauce", "oats", "ფქვილი", "პური", "მაკარონი",
    ),
    "eggs": ("egg", "eggs", "mayonnaise", "კვერცხი"),
    "fish": ("fish", "salmon", "tuna", "anchovy", "თევზი"),
    "shellfish": (
        "shrimp", "prawn", "prawns", "crab", "crabs", "lobster", "oyster",
        "mussel", "clam", "scallop", "კრევეტი",
    ),
    "soy": ("soy", "soya", "tofu", "tempeh", "სოიო"),
    "sesame": ("sesame", "tahini", "ტაჰინი", "სეზამი"),
    "mustard": ("mustard", "მდოგვი"),
}

MEAT_KEYWORDS = (
    "beef", "pork", "chicken", "turkey", "lamb", "bacon", "ham", "sausage",
    "salami", "meatball", "meat", "gelatin", "chicken broth", "beef broth",
    "bone broth", "fish", "salmon", "tuna", "anchovy", "shrimp", "prawn",
    "crab", "lobster", "oyster", "mussel", "seafood", "cod", "trout",
    "sardine", "mackerel", "tilapia", "ქათამი", "ღორის",
    "საქონლის", "ხორცი", "ძეხვი", "თევზი", "კრევეტი",
)
NON_DAIRY_MILKS = ("almond milk", "oat milk", "soy milk", "coconut milk", "rice milk")
NON_DAIRY_BUTTERS = ("peanut butter", "almond butter", "coconut butter", "cocoa butter")
STAPLES = {"salt", "pepper", "water", "oil", "olive oil", "მარილი", "წყალი", "ზეთი"}


def normalize(value: str) -> str:
    # Normalize Unicode, casing, and whitespace before comparing user-entered names.
    value = unicodedata.normalize("NFKC", value).casefold().strip()
    return re.sub(r"\s+", " ", value)


def contains_term(text: str, term: str) -> bool:
    text = normalize(text)
    term = normalize(term)
    if not term:
        return False
    if re.search(r"[^\w]", term, flags=re.UNICODE):
        return term in text
    # Match whole words so, for example, "egg" does not match inside another word.
    return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, flags=re.UNICODE) is not None


def _ingredient_text(ingredients: Iterable[Any]) -> list[str]:
    result = []
    for ingredient in ingredients:
        if isinstance(ingredient, str):
            result.append(ingredient)
        else:
            result.append(str(ingredient.get("name", "")))
    return result


def detect_allergens(ingredients: Iterable[Any]) -> list[str]:
    names = _ingredient_text(ingredients)
    found = set()
    for name in names:
        for allergen, keywords in ALLERGEN_KEYWORDS.items():
            # "Oat milk" and nut butter contain these words but are not dairy.
            if allergen == "dairy" and any(
                contains_term(name, non_dairy_milk) for non_dairy_milk in NON_DAIRY_MILKS
            ):
                continue
            if allergen == "dairy" and any(
                contains_term(name, non_dairy_butter)
                for non_dairy_butter in NON_DAIRY_BUTTERS
            ):
                continue
            if any(contains_term(name, keyword) for keyword in keywords):
                found.add(allergen)
    return sorted(found)


def infer_diet_tags(ingredients: Iterable[Any]) -> list[str]:
    names = _ingredient_text(ingredients)
    allergens = set(detect_allergens(names))
    ingredient_text = " ".join(names)
    has_animal_ingredient = any(
        contains_term(ingredient_text, term)
        for term in (*MEAT_KEYWORDS, "honey", "თაფლი")
    )
    tags = []
    if not has_animal_ingredient:
        tags.append("vegetarian")
        if not allergens.intersection({"dairy", "eggs"}):
            tags.append("vegan")
    if "gluten" not in allergens:
        tags.append("gluten_free")
    if "dairy" not in allergens:
        tags.append("dairy_free")
    return tags


def allergies_from_terms(terms: Iterable[str]) -> list[str]:
    found = set()
    for term in terms:
        normalized = term.casefold().replace("-", " ").strip()
        for allergen, keywords in ALLERGEN_KEYWORDS.items():
            if contains_term(normalized, allergen) or any(
                contains_term(normalized, keyword) for keyword in keywords
            ):
                found.add(allergen)
        if re.search(r"\bnuts?\b", normalized):
            found.add("nuts")
    return sorted(found)


def explicit_allergies(message: str) -> list[str]:
    if not re.search(r"\b(allerg(?:y|ic|ies)|intoleran(?:t|ce))\b", message.casefold()):
        return []
    return allergies_from_terms([message])


def pantry_match(
    ingredients: Iterable[Any], pantry_names: Iterable[str]
) -> tuple[float, list[str]]:
    pantry = {normalize(name) for name in pantry_names}
    required = []
    missing = []
    for name in _ingredient_text(ingredients):
        normalized = normalize(name)
        # Everyday staples are not useful signals for pantry coverage.
        if normalized in STAPLES:
            continue
        required.append(name)
        if not any(
            normalized == item
            or contains_term(normalized, item)
            or contains_term(item, normalized)
            for item in pantry
        ):
            missing.append(name)
    score = 1.0 if not required else (len(required) - len(missing)) / len(required)
    return round(score, 3), missing


def is_safe_recipe(
    recipe: dict[str, Any],
    *,
    allergies: Iterable[str],
    diet: str,
    disliked_ingredients: Iterable[str],
) -> bool:
    ingredients = _ingredient_text(recipe.get("ingredients", []))
    allergens = set(detect_allergens(ingredients))
    # User allergies and dislikes always override recipe tags and search relevance.
    if allergens.intersection(allergies):
        return False

    if any(
        contains_term(ingredient, disliked)
        for ingredient in ingredients
        for disliked in disliked_ingredients
        if normalize(disliked)
    ):
        return False

    tags = set(recipe.get("diet_tags", []))
    ingredient_text = " ".join(ingredients)
    has_meat_or_fish = any(contains_term(ingredient_text, term) for term in MEAT_KEYWORDS)
    has_dairy_or_eggs = bool(allergens.intersection({"dairy", "eggs"}))
    has_honey = contains_term(ingredient_text, "honey") or contains_term(
        ingredient_text, "თაფლი"
    )
    if diet == "vegan" and (
        "vegan" not in tags or has_meat_or_fish or has_dairy_or_eggs or has_honey
    ):
        return False
    if diet == "vegetarian" and (
        not tags.intersection({"vegetarian", "vegan"}) or has_meat_or_fish
    ):
        return False
    if diet == "gluten_free" and "gluten" in allergens:
        return False
    if diet == "dairy_free" and "dairy" in allergens:
        return False
    return True


def scale_recipe(recipe: dict[str, Any], servings: int) -> dict[str, Any]:
    if servings < 1:
        raise ValueError("Servings must be at least one.")
    result = dict(recipe)
    original = int(recipe["servings"])
    # Return a copy so displaying a different serving count does not alter catalog data.
    result["ingredients"] = [
        {
            **ingredient,
            "quantity": round(float(ingredient["quantity"]) * servings / original, 2),
        }
        for ingredient in recipe["ingredients"]
    ]
    result["servings"] = servings
    return result


def relax_constraints(constraints: dict[str, Any], relax_attempts: int) -> dict[str, Any]:
    # Only non-safety preferences can be relaxed: first time, then cuisine.
    updated = dict(constraints)
    if relax_attempts == 0 and updated.get("max_time_min"):
        updated["max_time_min"] = min(480, int(updated["max_time_min"] * 1.5))
    elif relax_attempts == 1:
        updated["cuisine"] = None
    return updated
