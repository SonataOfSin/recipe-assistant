from app.catalog import get_catalog
from app.safety import (
    allergies_from_terms,
    detect_allergens,
    explicit_allergies,
    infer_diet_tags,
    is_safe_recipe,
    pantry_match,
    relax_constraints,
    scale_recipe,
)


def test_safety_filter_blocks_allergen():
    recipe = {"ingredients": [{"name": "mozzarella", "quantity": 100, "unit": "g"}]}
    assert detect_allergens(recipe["ingredients"]) == ["dairy"]
    assert not is_safe_recipe(
        recipe,
        allergies=["dairy"],
        diet="none",
        disliked_ingredients=[],
    )


def test_safety_filter_enforces_diet():
    recipe = {
        "ingredients": [{"name": "egg", "quantity": 2, "unit": "pcs"}],
        "diet_tags": ["vegetarian"],
    }
    assert not is_safe_recipe(
        recipe,
        allergies=[],
        diet="vegan",
        disliked_ingredients=[],
    )


def test_generated_recipe_allergens_are_derived_from_ingredients():
    draft = {
        "ingredients": [
            {"name": "oat milk", "quantity": 200, "unit": "ml"},
            {"name": "walnuts", "quantity": 10, "unit": "g"},
        ],
        "allergens": [],
    }
    assert detect_allergens(draft["ingredients"]) == ["nuts"]


def test_generated_recipe_diet_tags_come_from_ingredients():
    ingredients = [{"name": "rice"}, {"name": "tomato"}]
    assert infer_diet_tags(ingredients) == [
        "vegetarian",
        "vegan",
        "gluten_free",
        "dairy_free",
    ]


def test_allergies_can_be_found_in_request_and_exclusions():
    assert explicit_allergies("I have a peanut allergy") == ["nuts"]
    assert allergies_from_terms(["peanuts"]) == ["nuts"]


def test_pantry_match_score_ignores_staples():
    ingredients = [
        {"name": "chicken", "quantity": 200, "unit": "g"},
        {"name": "rice", "quantity": 100, "unit": "g"},
        {"name": "salt", "quantity": 1, "unit": "tsp"},
    ]
    assert pantry_match(ingredients, ["chicken"]) == (0.5, ["rice"])


def test_relaxation_does_not_change_profile_safety_settings():
    constraints = {"max_time_min": 20, "cuisine": "Georgian"}
    first = relax_constraints(constraints, 0)
    second = relax_constraints(first, 1)
    profile = {"allergies": ["dairy"], "diet": "vegan"}
    assert first["max_time_min"] == 30
    assert second["cuisine"] is None
    assert profile == {"allergies": ["dairy"], "diet": "vegan"}


def test_scale_recipe_scales_quantities():
    recipe = {
        "servings": 2,
        "ingredients": [{"name": "rice", "quantity": 100, "unit": "g"}],
    }
    scaled = scale_recipe(recipe, 6)
    assert scaled["ingredients"][0]["quantity"] == 300
    assert scaled["servings"] == 6


def test_catalog_has_thirty_seeded_recipes():
    assert len(get_catalog()) >= 30
