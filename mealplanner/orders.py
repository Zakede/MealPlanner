"""Food you ordered (delivery, takeout, a restaurant bill): receipt -> calorie estimates -> food log.

The model reads the receipt and guesses the nutrition of each dish; our code checks the numbers and
the user ticks, edits and says how much of it they ate before anything is logged.
"""
MAX_ITEMS = 30
SKIP_WORDS = ("delivery", "service fee", "tip", "tax", "bag", "discount", "coupon", "送料", "手数料", "配達", "税")


def build_prompt(cur, text=None):
    source = f'this order receipt text:\n"""\n{text[:4000]}\n"""' if text else "the attached order receipt or screenshot"
    return f"""Read {source}. It is food someone ordered: delivery (Uber Eats, Demae-can, Wolt...), takeout or a restaurant bill.

For every food or drink item (skip delivery fees, service fees, tips, tax, bags, discounts and totals):
- name: a short clear English name of the dish, with the shop if it helps (e.g. "Big Mac", "Large fries")
- qty: how many were ordered
- kcal, protein, carbs, fat: your estimate for ALL of that line (qty included), grams for macros.
  Use the chain's published numbers when you know them, otherwise typical restaurant portions. Be realistic, not optimistic.
- price: what that line cost in {cur}, 0 if not shown
- confidence: low, medium or high

Reply with ONE JSON object and nothing else:
{{"place": "shop name", "total": 0,
  "items": [{{"name": "...", "qty": 1, "kcal": 0, "protein": 0, "carbs": 0, "fat": 0, "price": 0, "confidence": "medium"}}]}}
"""


def _num(value, hi):
    try:
        return max(0.0, min(hi, float(str(value).replace(",", "").replace("¥", "").replace("$", ""))))
    except (TypeError, ValueError):
        return 0.0


def rows_from_reply(data):
    """Turn the model's reply into review rows. Returns (rows, header, warnings)."""
    if not isinstance(data, dict):
        return [], {}, ["That didn't look like an order."]
    rows, warnings = [], []
    for item in (data.get("items") or [])[:MAX_ITEMS]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()[:60]
        if not name or any(w in name.lower() for w in SKIP_WORDS):
            continue
        qty = max(1, min(20, round(_num(item.get("qty") or 1, 20)) or 1))
        kcal = round(_num(item.get("kcal"), 3000 * qty))
        row = {"name": name if qty == 1 else f"{name} ×{qty}", "kcal": kcal,
               "protein": round(_num(item.get("protein"), 200 * qty), 1),
               "carbs": round(_num(item.get("carbs"), 400 * qty), 1),
               "fat": round(_num(item.get("fat"), 200 * qty), 1),
               "price": round(_num(item.get("price"), 100000)),
               "confidence": item.get("confidence") if item.get("confidence") in ("low", "medium", "high") else "low"}
        # macros that add up to far more than the calories are a bad guess: keep the calories only
        if row["protein"] * 4 + row["carbs"] * 4 + row["fat"] * 9 > max(kcal, 1) * 1.4:
            row.update(protein=0, carbs=0, fat=0, confidence="low")
        row["include"] = kcal > 0
        rows.append(row)
    if not rows:
        warnings.append("No food found on it. Try a sharper photo, or type it in instead.")
    if any(not r["kcal"] for r in rows):
        warnings.append("Some lines have no calorie guess, so they're left unticked. Fill them in if you ate them.")
    total = round(_num(data.get("total"), 10 ** 6))
    header = {"place": str(data.get("place") or "")[:60], "total": total}
    return rows, header, warnings


def entries_from_form(form):
    """The ticked rows, scaled to how much of the order you ate. Returns (entries, errors)."""
    try:
        share = max(0.1, min(1.0, float(form.get("share") or 1)))
    except ValueError:
        share = 1.0
    try:
        count = max(0, min(MAX_ITEMS, int(form.get("count") or 0)))
    except ValueError:
        count = 0
    paid = 1.0 if form.get("paid_all") else share
    entries, errors = [], []
    for i in range(count):
        if not form.get(f"include_{i}"):
            continue
        name = (form.get(f"name_{i}") or "").strip()[:60]
        kcal = _num(form.get(f"kcal_{i}"), 6000)
        if not name or kcal <= 0:
            errors.append(f"Line {i + 1} needs a name and calories, so it wasn't logged.")
            continue
        entries.append({"name": name if share == 1 else f"{name} ({round(share * 100)}%)",
                        "kcal": round(kcal * share),
                        "protein": round(_num(form.get(f"protein_{i}"), 400) * share, 1),
                        "carbs": round(_num(form.get(f"carbs_{i}"), 800) * share, 1),
                        "fat": round(_num(form.get(f"fat_{i}"), 400) * share, 1),
                        "yen": round(_num(form.get(f"price_{i}"), 100000) * paid)})
    return entries, errors
