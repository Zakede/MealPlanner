import os
from datetime import date
from pathlib import Path

from flask import Flask, current_app

from . import db


def today():
    """Today's date, overridable with the TODAY config value (used in tests)."""
    override = current_app.config.get("TODAY")
    return date.fromisoformat(override) if override else date.today()


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    app.config.update(
        SECRET_KEY=os.environ.get("MEALPLANNER_SECRET", "dev-only-change-me"),
        DATABASE=os.environ.get("MEALPLANNER_DB", str(Path(app.instance_path) / "mealplanner.db")),
        TODAY=os.environ.get("MEALPLANNER_TODAY"),
        NOW=os.environ.get("MEALPLANNER_NOW"),
    )
    if config:
        app.config.update(config)

    with app.app_context():
        conn = db.connect(app.config["DATABASE"])
        db.init_db(conn)
        conn.close()
    app.teardown_appcontext(db.close_db)

    from .views import cook, extras, main, pantry, plan, recipes, schedule, settings, taste
    for module in (main, settings, pantry, recipes, schedule, plan, cook, taste, extras):
        app.register_blueprint(module.bp)

    @app.context_processor
    def nav():
        from .store import settings
        s = settings()
        return {
            "has_endpoint": lambda name: name in app.view_functions,
            "ui": {"theme": s.get("theme") or "apothecary", "mode": s.get("mode") or "dark"},
        }

    return app
