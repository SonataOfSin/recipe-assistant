import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.catalog import get_catalog
from app.graph import RecipeDraft, RequestAnalysis, _fallback_analysis, build_graph


def test_fallback_analysis_reads_common_recipe_constraints():
    result = _fallback_analysis("quick vegan dinner in 20 minutes for 4 servings")

    assert result["intent"] == "find_recipe"
    assert result["max_time_min"] == 20
    assert result["servings"] == 4
    assert result["meal_type"] == "dinner"
    assert result["requested_diet"] == "vegan"


class FakeStructuredModel:
    def with_structured_output(self, schema):
        return FakeRunnable(schema)


class FakeRunnable:
    def __init__(self, schema):
        self.schema = schema

    async def ainvoke(self, _prompt):
        if self.schema is RequestAnalysis:
            return RequestAnalysis(intent="find_recipe", keywords=["rare-dish"])
        if self.schema is RecipeDraft:
            return RecipeDraft(
                title="Walnut Rice",
                description="A generated recipe with a hidden allergen claim omitted.",
                cuisine="International",
                meal_type="dinner",
                servings=2,
                total_time_min=20,
                ingredients=[
                    {"name": "walnuts", "quantity": 20, "unit": "g"},
                    {"name": "rice", "quantity": 100, "unit": "g"},
                ],
                steps=["Cook the rice.", "Top it with walnuts."],
            )
        raise AssertionError(f"Unexpected structured schema: {self.schema}")


@pytest.mark.asyncio
async def test_generated_recipe_with_allergen_is_blocked_by_python():
    graph = build_graph(
        checkpointer=InMemorySaver(),
        model=FakeStructuredModel(),
        api_key=None,
    )
    result = await graph.ainvoke(
        {
            "message": "Invent an unusual rare dish.",
            "history": [],
            "previous_recipes": [],
            "profile": {
                "allergies": ["nuts"],
                "diet": "none",
                "disliked_ingredients": [],
                "default_servings": 2,
            },
            "pantry": [],
            "catalog": get_catalog(),
            "max_recipes": 3,
            "candidates": [],
            "safe_recipes": [],
            "generated_recipe": None,
        },
        config={"configurable": {"thread_id": "generated-allergen-test"}},
    )
    assert result["safe_recipes"] == []
    assert "couldn't find" in result["answer"]
