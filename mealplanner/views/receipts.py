import os
import tempfile

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for

from .. import llm, receipts, store, today

bp = Blueprint("receipts", __name__, url_prefix="/receipts")
IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
MAX_UPLOAD = 12 * 1024 * 1024


def vision_model():
    return os.environ.get("MEALPLANNER_VISION_MODEL", llm.DEFAULT_VISION_MODEL)


@bp.route("/", methods=["GET", "POST"])
def upload():
    p = llm.provider()
    if request.method == "GET":
        return render_template("receipts/upload.html", available=p is not None)
    photo = request.files.get("photo")
    if not photo or not photo.filename:
        flash("Pick a photo of the receipt.", "error")
        return redirect(url_for("receipts.upload"))
    ext = os.path.splitext(photo.filename)[1].lower() or ".jpg"
    if ext not in IMAGE_TYPES:
        flash("That isn't a photo. Use JPG, PNG or WebP.", "error")
        return redirect(url_for("receipts.upload"))
    if p is None:
        flash("No model is set up for reading photos. Install opencode, or add items by hand.", "error")
        return redirect(url_for("receipts.upload"))
    data = photo.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        flash("That photo is over 12 MB. Try a smaller one.", "error")
        return redirect(url_for("receipts.upload"))
    with tempfile.TemporaryDirectory(prefix="mealplanner-receipt-") as work:
        path = os.path.join(work, "receipt" + ext)
        with open(path, "wb") as f:
            f.write(data)
        try:
            reply = p.complete(receipts.build_prompt(store.foods()), images=[path], model=vision_model())
            parsed = llm.extract_json(reply)
        except llm.LLMError as e:
            flash(f"Couldn't read the receipt: {e}. Try a sharper, flatter photo.", "error")
            return redirect(url_for("receipts.upload"))
    rows, header, warnings = receipts.rows_from_reply(parsed, today())
    return review(rows, header, warnings)


def review(rows, header, warnings):
    return render_template("receipts/review.html", rows=rows, header=header, warnings=warnings,
                           foods=store.foods())


@bp.route("/save", methods=["POST"])
def save():
    added, errors = receipts.save_rows(request.form, today())
    for e in errors:
        flash(e, "error")
    flash(f"Added {added} item{'s' if added != 1 else ''} to the pantry.", "ok")
    return redirect(url_for("pantry.index"))


@bp.route("/api", methods=["POST"])
def api():
    """For other apps (e.g. an OCR app) that already read the receipt.

    Body: {"store": "...", "date": "YYYY-MM-DD", "total_yen": 0,
           "items": [{"name_ja": "...", "price_yen": 0, "quantity": "...", "food": optional, "grams": optional}]}
    Items without "food" get matched by the text model. Returns review rows; nothing is saved.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        return jsonify({"error": "send JSON with an items list"}), 400
    unmatched = [i for i in data["items"] if isinstance(i, dict) and not i.get("food")]
    p = llm.provider()
    if unmatched and p is not None:
        try:
            matched = llm.extract_json(p.complete(receipts.build_match_prompt(unmatched, store.foods())))
            by_name = {m.get("name_ja"): m for m in matched.get("items", []) if isinstance(m, dict)}
            for item in unmatched:
                m = by_name.get(item.get("name_ja") or item.get("name"))
                if m:
                    item.setdefault("food", m.get("food"))
                    item.setdefault("grams", m.get("grams"))
        except llm.LLMError as e:
            current_app.logger.warning("receipt matching failed: %s", e)
    rows, header, warnings = receipts.rows_from_reply(data, today())
    return jsonify({"header": header, "rows": rows, "warnings": warnings})
