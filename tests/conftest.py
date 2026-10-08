import os

import pytest

# never call a real model from tests
os.environ["MEALPLANNER_LLM"] = "none"

from mealplanner import create_app
from mealplanner.db import execute


@pytest.fixture(autouse=True)
def no_real_ai_keys(monkeypatch):
    """Keys on the machine running the tests must never reach a real AI service."""
    for name in ("OPENROUTER_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def app(tmp_path):
    app = create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "test.db"),
        "TODAY": "2026-10-07",  # a Wednesday
        "SECRET_KEY": "test",
    })
    return app


@pytest.fixture
def client(app):
    """A browser that has already picked the first profile (a new one is asked who's eating)."""
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["profile"] = "main"
    return c


@pytest.fixture
def profile(app):
    """Fill in the fields that have no defaults."""
    with app.app_context():
        execute("UPDATE settings SET age = 25, sex = 'male', setup_done = 1 WHERE id = 1")
    return app
