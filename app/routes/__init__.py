"""API route groups, split by the features they serve."""

from app.routes.accounts import router as accounts_router
from app.routes.analytics import router as analytics_router
from app.routes.chat import router as chat_router
from app.routes.library import router as library_router
from app.routes.pantry import router as pantry_router
from app.routes.recipes import router as recipes_router
