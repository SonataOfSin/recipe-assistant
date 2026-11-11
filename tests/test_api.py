def register_and_login(client, email="cook@example.com"):
    created = client.post(
        "/auth/register",
        json={"email": email, "full_name": "Test Cook", "password": "secure-password-123"},
    )
    assert created.status_code == 201
    response = client.post(
        "/auth/login",
        json={"email": email, "password": "secure-password-123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_registration_profile_safe_search_and_confirmations(client):
    headers = register_and_login(client)
    profile = client.put(
        "/profile",
        headers=headers,
        json={
            "allergies": ["dairy"],
            "diet": "none",
            "disliked_ingredients": [],
            "default_servings": 2,
        },
    )
    assert profile.status_code == 200

    recipes = client.get("/recipes", headers=headers)
    assert recipes.status_code == 200
    assert all("dairy" not in recipe["allergens"] for recipe in recipes.json())
    assert not any(recipe["title"] == "Spinach Mushroom Pasta" for recipe in recipes.json())

    lentil = next(
        recipe for recipe in recipes.json() if recipe["title"] == "Red Lentil Soup"
    )
    refused = client.post(
        "/shopping-lists",
        headers=headers,
        json={"recipe_id": lentil["id"], "confirmed": False},
    )
    assert refused.status_code == 400
    confirmed = client.post(
        "/shopping-lists",
        headers=headers,
        json={"recipe_id": lentil["id"], "confirmed": True},
    )
    assert confirmed.status_code == 201


def test_recipe_catalog_filters(client):
    headers = register_and_login(client)
    catalog = client.get("/recipes", headers=headers, params={"size": 100})
    assert catalog.status_code == 200
    target = catalog.json()[0]

    filtered = client.get(
        "/recipes",
        headers=headers,
        params={
            "search": target["title"],
            "cuisine": target["cuisine"],
            "meal_type": target["meal_type"],
            "max_time": target["total_time_min"],
            "size": 100,
        },
    )

    assert filtered.status_code == 200
    assert target["id"] in [recipe["id"] for recipe in filtered.json()]
    assert all(
        recipe["meal_type"] == target["meal_type"]
        and recipe["total_time_min"] <= target["total_time_min"]
        for recipe in filtered.json()
    )


def test_chat_is_persisted_and_other_users_cannot_read_it(client):
    headers = register_and_login(client)
    created = client.post("/chat/sessions", headers=headers)
    assert created.status_code == 201
    session_id = created.json()["id"]
    message = client.post(
        f"/chat/sessions/{session_id}/messages",
        headers=headers,
        json={"content": "I want a quick dinner with chickpeas"},
    )
    assert message.status_code == 200
    assert message.json()["role"] == "assistant"
    first_recipe = message.json()["recipes"][0]
    followup = client.post(
        f"/chat/sessions/{session_id}/messages",
        headers=headers,
        json={"content": "scale the first one to 4 servings"},
    )
    assert followup.status_code == 200
    assert followup.json()["recipes"][0]["title"] == first_recipe["title"]
    assert followup.json()["recipes"][0]["servings"] == 4

    other_headers = register_and_login(client, "other@example.com")
    hidden = client.get(
        f"/chat/sessions/{session_id}/messages",
        headers=other_headers,
    )
    assert hidden.status_code == 404


def test_users_cannot_create_catalog_recipes(client):
    headers = register_and_login(client)
    response = client.post(
        "/recipes",
        headers=headers,
        json={
            "title": "Forbidden Recipe",
            "description": "Not for regular users.",
            "meal_type": "dinner",
            "total_time_min": 20,
            "ingredients": [
                {"name": "rice", "quantity": 100, "unit": "g"},
                {"name": "water", "quantity": 200, "unit": "ml"},
            ],
            "steps": ["Cook the rice.", "Serve."],
        },
    )
    assert response.status_code == 403


def test_allergy_stated_in_chat_is_enforced_by_code(client):
    headers = register_and_login(client)
    response = client.post(
        "/recipes/recommend",
        headers=headers,
        json={"message": "I have a dairy allergy; show me a cheese omelet"},
    )
    assert response.status_code == 200
    assert all("dairy" not in recipe["allergens"] for recipe in response.json()["recipes"])
