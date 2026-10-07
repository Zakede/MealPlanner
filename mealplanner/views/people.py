from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from .. import profiles
from ..db import close_db

bp = Blueprint("people", __name__, url_prefix="/people")


@bp.route("/")
def pick():
    return render_template("people.html", everyone=profiles.all_profiles(), chosen=session.get("profile"))


@bp.route("/<pid>/use", methods=["POST"])
def use(pid):
    if not profiles.find(pid):
        flash("That profile doesn't exist any more.", "error")
        return redirect(url_for("people.pick"))
    session["profile"] = pid
    session.permanent = True
    return redirect(url_for("main.home"))


@bp.route("/new", methods=["POST"])
def create():
    # anyone past the site password can add themselves, even on a phone last used by someone with a lock
    try:
        pid = profiles.create(request.form.get("name", ""))
    except ValueError as e:
        flash(str(e).capitalize() + ".", "error")
        return redirect(url_for("people.pick"))
    session["profile"] = pid
    session.permanent = True
    flash("Your own profile is ready. Let's set it up.", "ok")
    return redirect(url_for("setup.start"))


@bp.route("/<pid>/rename", methods=["POST"])
def rename(pid):
    if pid != profiles.current_id():
        flash("You can only rename the profile you're using.", "error")
    else:
        try:
            profiles.rename(pid, request.form.get("name", ""))
            flash("Renamed.", "ok")
        except ValueError as e:
            flash(str(e).capitalize() + ".", "error")
    return redirect(url_for("settings.edit"))


@bp.route("/<pid>/delete", methods=["POST"])
def delete(pid):
    if pid != profiles.current_id():
        flash("Open a profile to delete it.", "error")
        return redirect(url_for("people.pick"))
    if (request.form.get("confirm") or "").strip().upper() != "DELETE":
        flash("Type DELETE to confirm. Nothing was deleted.", "error")
        return redirect(url_for("settings.edit"))
    if pid == profiles.MAIN:
        flash("The first profile can't be deleted, but it can be reset.", "error")
        return redirect(url_for("settings.edit"))
    close_db()  # Windows won't delete a file that's still open
    try:
        profiles.delete(pid)
    except ValueError as e:
        flash(str(e).capitalize() + ".", "error")
        return redirect(url_for("settings.edit"))
    session.pop("profile", None)
    flash("Profile deleted.", "ok")
    return redirect(url_for("people.pick"))
