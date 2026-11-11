"""Streamlit screens; all saved data and business rules live behind the API."""

import os
from typing import Any

import httpx
import streamlit as st

DEFAULT_API_URL = "http://127.0.0.1:8000"
TIMEOUT = httpx.Timeout(90, connect=5)


# API communication helpers
class APIError(RuntimeError):
    pass


def api_url() -> str:
    return os.getenv("API_BASE_URL", DEFAULT_API_URL).rstrip("/")


def api_request(method: str, path: str, *, authenticated: bool = True, **kwargs: Any) -> Any:
    headers = kwargs.pop("headers", {})
    if authenticated:
        # Send the saved login token on routes that require an account.
        token = st.session_state.get("access_token")
        if not token:
            raise APIError("Please sign in again.")
        headers["Authorization"] = f"Bearer {token}"
    try:
        response = httpx.request(
            method,
            f"{api_url()}{path}",
            headers=headers,
            timeout=TIMEOUT,
            **kwargs,
        )
    except httpx.TimeoutException as exc:
        raise APIError("The request timed out. Check the service and try again.") from exc
    except httpx.RequestError as exc:
        raise APIError(f"Cannot connect to the API at {api_url()}.") from exc
    if not response.is_success:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise APIError(f"HTTP {response.status_code}: {detail}")
    # DELETE endpoints return no JSON body; all other successful routes do.
    if response.status_code == 204:
        return None
    try:
        return response.json()
    except ValueError as exc:
        raise APIError("The API returned invalid JSON.") from exc


def show_error(action) -> Any:
    try:
        return action()
    except APIError as exc:
        st.error(str(exc))
        return None


# Login and account creation
def login_view() -> None:
    st.title("🥗 Recipe Assistant")
    st.caption("Safe, personalized cooking ideas from your pantry.")
    login_tab, register_tab = st.tabs(["Sign in", "Create account"])
    with login_tab:
        with st.form("login"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", type="primary")
        if submitted:
            try:
                token = api_request(
                    "POST",
                    "/auth/login",
                    authenticated=False,
                    json={"email": email, "password": password},
                )
                st.session_state.access_token = token["access_token"]
                st.session_state.user = api_request("GET", "/auth/me")
                st.rerun()
            except APIError as exc:
                st.error(str(exc))
    with register_tab:
        with st.form("register"):
            name = st.text_input("Your name")
            register_email = st.text_input("Email address")
            register_password = st.text_input(
                "Password (at least 10 characters)", type="password"
            )
            submitted = st.form_submit_button("Create account")
        if submitted:
            try:
                api_request(
                    "POST",
                    "/auth/register",
                    authenticated=False,
                    json={
                        "email": register_email,
                        "full_name": name,
                        "password": register_password,
                    },
                )
                st.success("Account created. Sign in to continue.")
            except APIError as exc:
                st.error(str(exc))


# Shared recipe card used in the catalog, chat, and cookbook.
def render_recipe(recipe: dict, key: str) -> None:
    with st.container(border=True):
        st.subheader(recipe["title"])
        st.caption(
            f"{recipe['cuisine']} · {recipe['meal_type']} · "
            f"{recipe['total_time_min']} min · {recipe['servings']} servings"
        )
        st.write(recipe["description"])
        st.progress(float(recipe.get("pantry_match", 0)), text="Pantry match")
        if recipe.get("allergens"):
            st.caption("Detected allergens: " + ", ".join(recipe["allergens"]))
        st.markdown("**Ingredients**")
        for ingredient in recipe["ingredients"]:
            st.write(
                f"- {ingredient['quantity']} {ingredient['unit']} {ingredient['name']}"
            )
        st.markdown("**Steps**")
        for index, step in enumerate(recipe["steps"], start=1):
            st.write(f"{index}. {step}")
        if recipe.get("missing_ingredients"):
            st.caption("Not in your pantry: " + ", ".join(recipe["missing_ingredients"]))
        if recipe.get("source") == "ai_generated":
            st.warning(
                "AI-generated and not catalog-verified. Check every ingredient and "
                "label carefully, especially if you have an allergy."
            )
        if recipe.get("id"):
            save_col, shopping_col = st.columns(2)
            if save_col.button("Save to cookbook", key=f"save-{key}-{recipe['id']}"):
                result = show_error(
                    lambda: api_request(
                        "POST",
                        f"/cookbook/{recipe['id']}",
                        json={"confirmed": True},
                    )
                )
                if result:
                    st.success("Saved to your cookbook.")
            if shopping_col.button(
                "Confirm shopping list",
                key=f"shop-{key}-{recipe['id']}",
            ):
                result = show_error(
                    lambda: api_request(
                        "POST",
                        "/shopping-lists",
                        json={"recipe_id": recipe["id"], "confirmed": True},
                    )
                )
                if result:
                    st.success("Shopping list saved.")
                    for item in result["items"]:
                        st.write(f"- {item['quantity']} {item['unit']} {item['name']}")


# Each chat page load refreshes persisted sessions and messages from the API.
def chat_page() -> None:
    st.header("Recipe chat")
    profile = show_error(lambda: api_request("GET", "/profile"))
    if profile is not None and not profile["allergies"]:
        st.warning("Set your allergies in Profile to get safer recipe suggestions.")
    sessions = show_error(lambda: api_request("GET", "/chat/sessions")) or []
    session_options = {item["id"]: item["title"] for item in sessions}
    if "chat_id" not in st.session_state:
        st.session_state.chat_id = ""
    labels = ["New conversation"] + [
        f"{title} · {session_id[:8]}" for session_id, title in session_options.items()
    ]
    selected = st.selectbox("Conversation", labels)
    if selected == "New conversation":
        if st.button("Start a conversation") or not st.session_state.chat_id:
            chat = show_error(lambda: api_request("POST", "/chat/sessions"))
            if chat:
                st.session_state.chat_id = chat["id"]
                st.rerun()
    else:
        selected_id = next(
            session_id
            for session_id, title in session_options.items()
            if selected == f"{title} · {session_id[:8]}"
        )
        st.session_state.chat_id = selected_id

    chat_id = st.session_state.chat_id
    if chat_id:
        messages = show_error(
            lambda: api_request("GET", f"/chat/sessions/{chat_id}/messages")
        ) or []
        for message in messages:
            with st.chat_message(message["role"]):
                st.write(message["content"])
                for index, recipe in enumerate(message.get("recipes", [])):
                    render_recipe(recipe, f"history-{message['id']}-{index}")
        prompt = st.chat_input("What would you like to cook?")
        if prompt:
            response = show_error(
                lambda: api_request(
                    "POST",
                    f"/chat/sessions/{chat_id}/messages",
                    json={"content": prompt},
                )
            )
            if response:
                st.rerun()


# User settings that the backend applies to every recipe search.
def profile_page() -> None:
    st.header("Dietary profile")
    profile = show_error(lambda: api_request("GET", "/profile"))
    if profile is None:
        return
    with st.form("profile"):
        allergies = st.multiselect(
            "Allergies",
            ["dairy", "nuts", "gluten", "eggs", "fish", "shellfish", "soy", "sesame", "mustard"],
            default=profile["allergies"],
        )
        diet = st.selectbox(
            "Diet",
            ["none", "vegetarian", "vegan", "gluten_free", "dairy_free"],
            index=["none", "vegetarian", "vegan", "gluten_free", "dairy_free"].index(
                profile["diet"]
            ),
        )
        dislikes = st.text_input(
            "Ingredients to avoid (comma separated)",
            value=", ".join(profile["disliked_ingredients"]),
        )
        servings = st.number_input(
            "Default servings", min_value=1, max_value=20, value=profile["default_servings"]
        )
        submitted = st.form_submit_button("Save profile", type="primary")
    if submitted:
        result = show_error(
            lambda: api_request(
                "PUT",
                "/profile",
                json={
                    "allergies": allergies,
                    "diet": diet,
                    "disliked_ingredients": [item.strip() for item in dislikes.split(",") if item.strip()],
                    "default_servings": servings,
                },
            )
        )
        if result:
            st.success("Profile updated.")


# Pantry items are saved by the API, then the page reruns to show the update.
def pantry_page() -> None:
    st.header("My pantry")
    with st.form("pantry-item"):
        name = st.text_input("Ingredient")
        quantity_col, unit_col = st.columns(2)
        quantity = quantity_col.number_input("Quantity (optional)", min_value=0.0, value=0.0)
        unit = unit_col.text_input("Unit (optional)")
        submitted = st.form_submit_button("Add or update")
    if submitted:
        result = show_error(
            lambda: api_request(
                "POST",
                "/pantry",
                json={
                    "name": name,
                    "quantity": quantity if quantity > 0 else None,
                    "unit": unit or None,
                },
            )
        )
        if result:
            st.success(f"Added {result['name']}.")
            st.rerun()
    items = show_error(lambda: api_request("GET", "/pantry")) or []
    for item in items:
        columns = st.columns([4, 1])
        label = item["name"]
        if item["quantity"] is not None:
            label += f" · {item['quantity']:g} {item['unit'] or ''}"
        columns[0].write(label)
        if columns[1].button("Remove", key=f"remove-{item['id']}"):
            try:
                api_request("DELETE", f"/pantry/{item['id']}")
                st.rerun()
            except APIError as exc:
                st.error(str(exc))


# Catalog filters are sent as query parameters for server-side filtering.
def catalog_page() -> None:
    st.header("Recipe catalog")
    search_col, cuisine_col, meal_col, time_col = st.columns([2, 1, 1, 1])
    search = search_col.text_input("Search by dish or ingredient", max_chars=100)
    cuisine = cuisine_col.text_input("Cuisine", max_chars=50)
    meal_type = meal_col.selectbox(
        "Meal type",
        ["Any", "breakfast", "lunch", "dinner", "snack", "dessert"],
    )
    max_time = time_col.number_input(
        "Max time (minutes)",
        min_value=1,
        max_value=480,
        value=480,
        step=5,
    )
    params = {"size": 100}
    if search.strip():
        params["search"] = search.strip()
    if cuisine.strip():
        params["cuisine"] = cuisine.strip()
    if meal_type != "Any":
        params["meal_type"] = meal_type
    if max_time < 480:
        params["max_time"] = max_time
    recipes = show_error(
        lambda: api_request(
            "GET",
            "/recipes",
            params=params,
        )
    ) or []
    st.caption(f"{len(recipes)} recipes match your filters and profile.")
    if not recipes:
        st.info("No recipes match those filters. Try broadening your search.")
    for index, recipe in enumerate(recipes):
        render_recipe(recipe, f"catalog-{index}")


# Saved recipes belong to the signed-in user.
def cookbook_page() -> None:
    st.header("My cookbook")
    recipes = show_error(lambda: api_request("GET", "/cookbook")) or []
    if not recipes:
        st.info("Save a recipe from chat or the catalog to get started.")
    for index, recipe in enumerate(recipes):
        render_recipe(recipe, f"cookbook-{index}")
        if recipe.get("id") and st.button(
            "Remove from cookbook", key=f"remove-cookbook-{recipe['id']}"
        ):
            try:
                api_request("DELETE", f"/cookbook/{recipe['id']}")
                st.rerun()
            except APIError as exc:
                st.error(str(exc))


# Checkbox changes are persisted immediately so the list survives a refresh.
def shopping_page() -> None:
    st.header("Shopping lists")
    lists = show_error(lambda: api_request("GET", "/shopping-lists")) or []
    if not lists:
        st.info("Confirm a shopping list from a recipe to see it here.")
    for shopping_list in lists:
        with st.expander(shopping_list["title"]):
            for index, item in enumerate(shopping_list["items"]):
                bought = st.checkbox(
                    f"{item['quantity']} {item['unit']} {item['name']}",
                    value=item["is_bought"],
                    key=f"shopping-{shopping_list['id']}-{index}",
                )
                if bought != item["is_bought"]:
                    result = show_error(
                        lambda list_id=shopping_list["id"], item_index=index, value=bought: api_request(
                            "PATCH",
                            f"/shopping-lists/{list_id}/items/{item_index}",
                            json={"is_bought": value},
                        )
                    )
                    if result:
                        st.rerun()
            if st.button("Delete list", key=f"delete-list-{shopping_list['id']}"):
                try:
                    api_request("DELETE", f"/shopping-lists/{shopping_list['id']}")
                    st.rerun()
                except APIError as exc:
                    st.error(str(exc))


def main() -> None:
    st.set_page_config(page_title="Recipe Assistant", page_icon="🥗", layout="wide")
    # Streamlit reruns this function after interactions; session_state keeps login data.
    if not st.session_state.get("access_token"):
        login_view()
        return
    if not st.session_state.get("user"):
        st.session_state.user = show_error(lambda: api_request("GET", "/auth/me"))
        if not st.session_state.user:
            st.session_state.pop("access_token", None)
            return

    user = st.session_state.user
    with st.sidebar:
        st.title("🥗 Recipe Assistant")
        st.caption(f"{user['full_name']} · {user['role']}")
        page = st.radio(
            "Navigate",
            ["Chat", "Pantry", "Profile", "Catalog", "Cookbook", "Shopping lists"],
        )
        st.caption(f"API: {api_url()}")
        if user["role"] == "admin":
            st.caption("Admin access is enabled for your account.")
        if st.button("Sign out"):
            st.session_state.clear()
            st.rerun()
    pages = {
        "Chat": chat_page,
        "Pantry": pantry_page,
        "Profile": profile_page,
        "Catalog": catalog_page,
        "Cookbook": cookbook_page,
        "Shopping lists": shopping_page,
    }
    pages[page]()


if __name__ == "__main__":
    main()
