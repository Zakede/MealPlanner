import os
import secrets
from datetime import date, timedelta
from pathlib import Path

from flask import Flask, current_app

from . import db


def today():
    """Today's date, overridable with the TODAY config value (used in tests)."""
    override = current_app.config.get("TODAY")
    return date.fromisoformat(override) if override else date.today()


def secret_key(instance_path):
    """A random key kept in the instance folder, so logins survive restarts."""
    env = os.environ.get("MEALPLANNER_SECRET")
    if env:
        return env
    path = Path(instance_path) / "secret.key"
    if not path.exists():
        path.write_text(secrets.token_hex(32), encoding="utf-8")
    return path.read_text(encoding="utf-8").strip()


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    app.config.update(
        SECRET_KEY=secret_key(app.instance_path),
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_HTTPONLY=True,
        DATABASE=os.environ.get("MEALPLANNER_DB", str(Path(app.instance_path) / "mealplanner.db")),
        TODAY=os.environ.get("MEALPLANNER_TODAY"),
        NOW=os.environ.get("MEALPLANNER_NOW"),
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,
    )
    if config:
        app.config.update(config)
    if os.environ.get("MEALPLANNER_BEHIND_PROXY"):
        # online behind Caddy: trust its forwarded address and https, and only send cookies over https
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
        app.config["SESSION_COOKIE_SECURE"] = True

    with app.app_context():
        conn = db.connect(app.config["DATABASE"])
        db.init_db(conn)
        conn.close()
        from .profiles import migrate_all
        migrate_all()
    app.teardown_appcontext(db.close_db)
    from . import budget, store
    budget.week_start_of = store.week_start

    from .views import auth, cook, foodlog, people, extras, main, pantry, plan, receipts, recipes, schedule, settings, setup, taste, track
    for module in (main, settings, pantry, recipes, schedule, plan, cook, taste, extras, setup, receipts, track, auth, people, foodlog):
        app.register_blueprint(module.bp)

    app.before_request(auth.require_login)
    from . import units
    units.register(app)
    from . import cuisines as _cz
    app.add_template_global(_cz.everything, "cuisine_list")
    app.add_template_global(_cz.ratings, "cuisine_ratings")
    from .store import settings as _settings
    app.add_template_global(_settings, "settings_now")

    @app.context_processor
    def nav():
        from .pricing import currency, in_japan
        from .profiles import all_profiles, current
        from .diet import hidden_by
        from .store import settings
        s = settings()
        return {
            "me": current(),
            "people": all_profiles(),
            "cur": currency(s),
            "in_japan": in_japan(s),
            "has_endpoint": lambda name: name in app.view_functions,
            "diet_hides": hidden_by,
            "ui": {"theme": "shokken", "mode": s.get("mode") or "dark"},
        }

    return app
