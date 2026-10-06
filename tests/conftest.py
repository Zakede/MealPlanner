import os

import pytest

# never call a real model from tests
os.environ["MEALPLANNER_LLM"] = "none"

from mealplanner import create_app
from mealplanner.db import execute


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
    return app.test_client()


@pytest.fixture
def profile(app):
    """Fill in the fields that have no defaults."""
    with app.app_context():
        execute("UPDATE settings SET age = 25, sex = 'male', setup_done = 1 WHERE id = 1")
    return app
