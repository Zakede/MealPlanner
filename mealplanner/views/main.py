from flask import Blueprint, render_template

from .. import store

bp = Blueprint("main", __name__)


@bp.route("/")
def home():
    s = store.settings()
    return render_template(
        "home.html",
        settings=s,
        targets=store.targets(s),
        needs_profile=not store.profile_complete(s),
    )
