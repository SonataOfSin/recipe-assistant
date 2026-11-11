import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient

from app.graph import build_graph


@pytest.fixture
def client(monkeypatch):
    import app.api

    monkeypatch.setattr(
        app.api,
        "build_graph",
        lambda checkpointer=None: build_graph(checkpointer=checkpointer, api_key=None),
    )
    with TestClient(app.api.app) as test_client:
        yield test_client
