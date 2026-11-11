# Recipe Assistant — Demo Day Guide

## Short introduction

“This is a recipe assistant. Users can create an account, set their allergies,
add ingredients to their pantry, and search for recipes or ask for ideas in
chat. The Streamlit interface talks to a FastAPI backend, which stores data
with SQLAlchemy in SQLite or PostgreSQL. Gemini can help understand natural
language requests, but Python code performs the final allergy and diet checks.”

## Where to find each part

| Part | File | What to show |
|---|---|---|
| App launcher | [`main.py`](./main.py) | Starts FastAPI and Streamlit, finds available ports, and stops both processes |
| Screens | [`app/streamlit_app.py`](./app/streamlit_app.py) | Registration, chat, profile, pantry, catalog filters, and saved recipes |
| API setup | [`app/api.py`](./app/api.py) | Creates the FastAPI app, initializes services, and registers route groups |
| API routes | [`app/routes/`](./app/routes/) | Separate account, pantry, recipe, cookbook, chat, and analytics endpoints |
| Shared API helpers | [`app/api_common.py`](./app/api_common.py) | Token checks, recipe formatting/safety, and request limits shared by routes |
| Database tables | [`app/models.py`](./app/models.py) | SQLAlchemy classes such as `User`, `Recipe`, `PantryItem`, and `ChatSession` |
| Database connection | [`app/database.py`](./app/database.py) | Async SQLAlchemy engine and sessions, table creation, and initial catalog data |
| API data shapes | [`app/schemas.py`](./app/schemas.py) | Pydantic request and response validation |
| Passwords and JWT | [`app/security.py`](./app/security.py) | Password hashing, JWT signing, verification, and expiration checks |
| Recipe safety rules | [`app/safety.py`](./app/safety.py) | Allergen detection, diet and disliked-ingredient filtering, and serving scaling |
| Chat workflow | [`app/graph.py`](./app/graph.py) | Request understanding, recipe search, safety filtering, optional AI drafting, and response |
| Similarity calculation | [`app/retrieval.py`](./app/retrieval.py) | Gemini embeddings and cosine similarity |
| Starter recipes | [`app/catalog.py`](./app/catalog.py), [`scripts/seed_recipes.py`](./scripts/seed_recipes.py) | Demo catalog and loading recipes into the database |
| Tests | [`tests/`](./tests/) | Automated API, graph, and safety checks |
| Docker | [`Dockerfile`](./Dockerfile), [`docker-compose.yml`](./docker-compose.yml) | Python image and API/UI/PostgreSQL services |

Routes are grouped by topic under `app/routes/`: health and account/profile,
pantry, recipes, cookbook/shopping lists, chat sessions, and admin analytics.

## How one chat request flows through the app

```text
Streamlit chat_input
        │ httpx + JWT
        ▼
POST /chat/sessions/{id}/messages      app/routes/chat.py
        │ profile + pantry + history
        ▼
LangGraph: understand → search → safety → compose
                     │
                     └─ if no suitable catalog result and Gemini is enabled:
                        generate → safety → compose
        │
        ▼
SQLAlchemy stores the message and the recipes shown
        │
        ▼
Streamlit displays the response and recipe actions
```

The user’s message is stored before it is processed. An AI-generated recipe is
not automatically considered safe; it goes through the `safety` step too.
Without a Gemini API key, the app still works with the catalog and its
rule-based fallback.

In [`app/graph.py`](./app/graph.py), each workflow step is a separate function.
`build_graph()` connects the functions with start, end, and conditional edges,
following the same basic structure as the LangGraph lesson examples. `partial`
passes the model to the steps that need it.

## A simple live demo

1. Start the app using the instructions in the README and open the Streamlit URL.
2. Create an account and sign in.
3. In `Profile`, add an allergy such as dairy. In `Pantry`, add a few ingredients.
4. In `Catalog`, demonstrate the search, cuisine, meal type, and maximum-time
   filters. They are sent to the API's `GET /recipes` route as query parameters.
5. In `Chat`, ask for a recipe using ingredients you have and point out the
   pantry-match score.
6. Show that a recipe containing dairy should not appear when the profile has a
   dairy allergy. The rule is implemented in [`app/safety.py`](./app/safety.py),
   not only in the model prompt.
7. Optionally save a catalog recipe to the cookbook or confirm a shopping list,
   then show the corresponding page.
8. Run the tests with `pytest -q`.

Do not show secrets from `.env` during the demo, and avoid using real personal
data. A Gemini key is not required for the basic demo.

## Course topics used in this project

| Topic | Where it appears |
|---|---|
| Python types, loops, functions, and collections | Filtering and recipe processing in `app/safety.py` and `app/graph.py` |
| Classes and objects | SQLAlchemy tables in `app/models.py`; request/response models in `app/schemas.py` |
| Async/await | API endpoints and database operations in `app/api.py` and `app/database.py` |
| HTTP API communication | Streamlit uses `httpx` to call FastAPI in `app/streamlit_app.py` |
| Project structure and Git | Modules, tests, and configuration across the project |
| Streamlit | User interface in `app/streamlit_app.py` |
| PostgreSQL/SQL and CRUD | Models and queries in `app/models.py` and `app/api.py`; PostgreSQL in Docker Compose |
| ORM | SQLAlchemy models, `select`, and sessions in `app/models.py` and `app/database.py` |
| FastAPI, routing, Pydantic, and dependency injection | Routes and `Depends(...)` in `app/routes/`; validation in `app/schemas.py` |
| JWT and RBAC | Bearer-token authentication and admin-only routes in `app/security.py`, `app/api_common.py`, and `app/routes/` |
| RAG / similarity search | Recipes are searched as whole records, not chunks; ranking combines text and optional embeddings in `app/graph.py` and `app/retrieval.py` |
| LLM API / LangChain | Google Gemini and LangChain structured output in `app/graph.py` |
| LangGraph | Request state and conditional routing in `app/graph.py` |
| Docker | Image and services in `Dockerfile` and `docker-compose.yml` |

## Be clear about what this project does not include

- The interface is built with Streamlit; this project does not have a separate
  HTML/CSS/JavaScript frontend.
- The integrated LLM provider is Gemini. OpenAI and Anthropic are not configured.
- Gemini function/tool calling is not used. The request moves through graph
  steps, and the model returns validated structured data.
- This is one staged LangGraph workflow, not a multi-agent system with several
  independent agents.
- Recipes are not split into chunks: each recipe is searched as one record.
  Embeddings are optional; regular text search also works.
- Nginx and GitHub Actions CI/CD are not configured. Docker Compose is used for
  local services.

## Possible demo questions

**Why check allergies in Python instead of relying only on AI?**  
AI helps understand requests and suggest ideas, but ordinary code checks the
safety rules too. Generated recipes go through the same filter.

**What happens without a Gemini API key?**  
Registration, profiles, the catalog, pantry, and rule-based request handling
still work. Only AI request analysis and new AI recipe drafting are disabled.

**Why use `async`?**  
The API waits for database operations and sometimes an external AI service.
`async/await` lets the server work on other requests while waiting.

**Where is the data stored?**  
Local runs use SQLite by default. Compose uses PostgreSQL. `DATABASE_URL`
selects the connection. Passwords are stored as hashes in the database; a JWT
is a separate authentication token.
