"""Optional password lock. Off until a password is set in Settings (or MEALPLANNER_PASSWORD)."""
import os
import time

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .. import store
from ..db import execute

bp = Blueprint("auth", __name__)
OPEN_ENDPOINTS = {"auth.login", "static"}


def password_hash():
    env = os.environ.get("MEALPLANNER_PASSWORD")
    if env:
        return generate_password_hash(env)
    return store.settings().get("password_hash") or ""


def check(password):
    env = os.environ.get("MEALPLANNER_PASSWORD")
    if env:
        return password == env
    stored = store.settings().get("password_hash") or ""
    return bool(stored) and check_password_hash(stored, password)


def lock_enabled():
    return bool(os.environ.get("MEALPLANNER_PASSWORD") or store.settings().get("password_hash"))


def require_login():
    if request.endpoint in OPEN_ENDPOINTS or request.endpoint is None:
        return None
    if not lock_enabled() or session.get("ok"):
        return None
    return redirect(url_for("auth.login", next=request.full_path if request.method == "GET" else None))


def set_password(new):
    execute("UPDATE settings SET password_hash = ? WHERE id = 1", (generate_password_hash(new) if new else "",))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if check(request.form.get("password", "")):
            session.clear()
            session["ok"] = True
            session.permanent = True
            nxt = request.args.get("next") or ""
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("main.home"))
        time.sleep(1)  # slows down guessing
        flash("Wrong password.", "error")
    return render_template("login.html")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@bp.route("/lock", methods=["POST"])
def lock():
    if request.form.get("off"):
        set_password("")
        flash("App lock turned off.", "ok")
        return redirect(url_for("settings.edit"))
    new, again = request.form.get("password", ""), request.form.get("again", "")
    if len(new) < 6:
        flash("Use at least 6 characters.", "error")
    elif new != again:
        flash("The two passwords don't match.", "error")
    else:
        set_password(new)
        session["ok"] = True
        session.permanent = True
        flash("App lock is on. Your phone stays logged in for 30 days.", "ok")
    return redirect(url_for("settings.edit") + "#lock")
