"""Weekly meal planner.

Pure planning logic: everything comes in through a context dict and the result is
a list of meal dicts. Loading and saving live in plans.py.

Order of decisions per slot:
1. slots already taken (kept meals, batch leftovers reserved earlier, eat-out reservations)
2. leftovers already in the fridge
3. recipes that pass the hard filters, ranked by score
4. a konbini combo, only when nothing else fits (away lunch with no packable option)
"""
from datetime import timedelta

from . import diet
from .costing import MACROS
from .nutrition import day_targets
from .schedule import busy, hhmm, minutes, slot_limits

MEAL_SLOTS = ("breakfast", "lunch", "dinner")
SLOT_SHARE = {"breakfast": 0.25, "lunch": 0.35, "dinner": 0.40}
PORTIONS = (0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0)
EXPIRING_DAYS = 2
COOLDOWN_DAYS = 4
FAVORITE_COOLDOWN_DAYS = 2
MAX_BATCH_MEALS = 4
EAT_OUT_PROTEIN_GUESS = 30
PACKABLE_MAX_ACTIVE = 10

# taste comes first: a plan you won't eat saves nothing
W_TASTE, W_PROTEIN, W_BUDGET, W_EXPIRY, W_PANTRY = 0.40, 0.22, 0.13, 0.15, 0.10
FAVORITE_BONUS, TRY_BONUS = 0.2, 0.1


class PantrySim:
    """Tracks pantry grams per food while meals are planned, oldest expiry first."""

    def __init__(self, lots):
        # lots: iterable of (food_id, grams, expiry_date or None)
        self.lots = {}
        for food_id, grams, expiry in lots:
            if grams and grams > 0:
                self.lots.setdefault(food_id, []).append([grams, expiry])
        for food_lots in self.lots.values():
            food_lots.sort(key=lambda lot: (lot[1] is None, lot[1]))

    def _usable(self, food_id, on):
        return [lot for lot in self.lots.get(food_id, []) if lot[1] is None or lot[1] >= on]

    def check(self, food_id, grams, on):
        """Return (grams from pantry, grams missing, grams that were expiring soon). No changes made."""
        have = expiring = 0.0
        need = grams
        for lot_grams, expiry in self._usable(food_id, on):
            if need <= 0:
                break
            take = min(lot_grams, need)
            have += take
            need -= take
            if expiry is not None and (expiry - on).days <= EXPIRING_DAYS:
                expiring += take
        return have, max(0.0, need), expiring

    def take(self, food_id, grams, on):
        need = grams
        for lot in self._usable(food_id, on):
            if need <= 0:
                break
            used = min(lot[0], need)
            lot[0] -= used
            need -= used
        self.lots[food_id] = [lot for lot in self.lots.get(food_id, []) if lot[0] > 1e-9]
        return max(0.0, need)


def scaled_ingredients(recipe, cook_portions):
    factor = cook_portions / max(1, recipe["servings"])
    return [(ing, ing["grams"] * factor) for ing in recipe["ingredients"]]


def purchase_check(recipe, cook_portions, pantry, on):
    """Cost to buy what's missing, plus pantry usage stats for scoring."""
    buy = 0.0
    total = from_pantry = expiring = 0.0
    for ing, grams in scaled_ingredients(recipe, cook_portions):
        have, missing, exp = pantry.check(ing["id"], grams, on)
        total += grams
        from_pantry += have
        expiring += exp
        buy += missing / 100 * (ing.get("price_per_100g") or 0)
    return {"buy": buy, "pantry_share": from_pantry / total if total else 0, "expiring_g": expiring}


def best_portion(kcal_per_serving, target):
    if kcal_per_serving <= 0:
        return 1.0
    return min(PORTIONS, key=lambda p: abs(p * kcal_per_serving - target))


def blocked(recipe, ctx):
    """Hard filters that never change during a plan: allergies, dislikes, spice, diet, "never again"."""
    if ctx.get("prefs", {}).get(recipe["id"]) == "never":
        return True
    if not diet.allowed(recipe, ctx.get("diet", "any"), ctx.get("avoid", [])):
        return True
    allergies = ctx["allergies"]
    names = [ing["name"].lower() for ing in recipe["ingredients"]]
    for word in allergies:
        if word in recipe["allergens"] or any(word in n for n in names):
            return True
    for word in ctx["dislikes"]:
        if any(word in n for n in names):
            return True
    return recipe["spice_level"] > ctx["spice_tolerance"]


def fits_slot(recipe, slot, limits, date, today):
    if slot not in recipe["type_list"]:
        return False
    lim = limits[slot]
    if lim["away"]:
        # packed from home in the morning
        return bool(recipe["portable"]) and recipe["active_min"] <= PACKABLE_MAX_ACTIVE \
            and recipe["thaw_hours"] == 0
    if recipe["active_min"] > lim["max_active"] or recipe["total_min"] > max(lim["max_total"], 5):
        return False
    if recipe["thaw_hours"] and date <= today:
        return False  # no time to thaw
    return True


def recently_eaten(recipe_id, date, ctx, chosen):
    """Days since this recipe was last eaten or planned, or None."""
    dates = list(ctx["history"].get(recipe_id, [])) + [m["date"] for m in chosen if m.get("recipe_id") == recipe_id
                                                      and m["kind"] in ("cook", "nocook", "snack")]
    gaps = [abs((date - d).days) for d in dates]
    return min(gaps) if gaps else None


def score(recipe, portion, target, check, ctx, date, chosen, gym, budget_left, meals_left, protein_gap):
    s = recipe["per_serving"]
    kcal = s["kcal"] * portion
    protein = s["protein"] * portion
    taste = ctx["taste"].get(recipe["id"], 0.6)

    protein_share = protein * 4 / kcal if kcal else 0
    protein_weight = W_PROTEIN + (0.1 if gym else 0) + min(0.15, max(0, protein_gap) / 400)
    per_meal_budget = budget_left / max(1, meals_left)

    total = W_TASTE * taste
    pref = ctx.get("prefs", {}).get(recipe["id"])
    total += FAVORITE_BONUS if pref == "favorite" else TRY_BONUS if pref == "try" else 0
    total += diet.bonus(recipe, ctx.get("diet", "any"))
    total += protein_weight * min(1.0, protein_share / 0.40)
    total += W_BUDGET * (1 - min(1.0, check["buy"] / max(1.0, per_meal_budget)))
    total += W_EXPIRY * min(1.0, check["expiring_g"] / 150)
    total += W_PANTRY * check["pantry_share"]
    total -= 0.4 * abs(kcal - target) / max(1, target)

    gap = recently_eaten(recipe["id"], date, ctx, chosen)
    favorite = recipe["id"] in ctx["favorites"] or pref == "favorite"
    cooldown = FAVORITE_COOLDOWN_DAYS if favorite else COOLDOWN_DAYS
    if gap is not None and gap < cooldown:
        total -= 0.35 * (cooldown - gap) / cooldown + 0.1
    uses = sum(1 for m in chosen if m.get("recipe_id") == recipe["id"] and m["kind"] != "leftover")
    total -= 0.12 * uses
    return total


def macros_for(recipe, portion):
    return {m: recipe["per_serving"][m] * portion for m in MACROS}


def konbini_combo(picks, kcal_target, budget_left):
    """Greedy pick of konbini items with the most protein per kcal, up to the target."""
    chosen, kcal, protein, yen = [], 0, 0.0, 0
    options = sorted((p for p in picks if p["chain"] != "McDonald's"),
                     key=lambda p: p["protein"] / max(1, p["kcal"]), reverse=True)
    for p in options:
        if kcal + p["kcal"] > kcal_target * 1.1 or yen + p["yen"] > budget_left:
            continue
        chosen.append(p)
        kcal += p["kcal"]
        protein += p["protein"]
        yen += p["yen"]
        if kcal >= kcal_target * 0.8:
            break
    return {"items": chosen, "kcal": kcal, "protein": protein, "yen": yen}


def pick_booster(recipe, ctx, kcal_room):
    """A flavour booster for meals rated bland or cheap-and-plain."""
    feedback = ctx["feedback"].get(recipe["id"], [])
    plain = recipe["per_serving"]["cost"] < 200 and ctx["taste"].get(recipe["id"], 0.6) < 0.6
    if "too bland" not in feedback and not plain:
        return None
    likes = set(ctx["flavor_likes"])
    options = [b for b in ctx["boosters"] if b["kcal"] <= max(10, kcal_room)
               and not any(a in b["allergens"] for a in ctx["allergies"])
               and b["food_id"] not in {i["id"] for i in recipe["ingredients"]}]
    if not options:
        return None
    return max(options, key=lambda b: (len(likes & set(b["tag_list"])), -b["kcal"]))


def eat_time(day, slot):
    if slot == "snack":
        return hhmm((minutes(day["lunch_time"]) + minutes(day["dinner_time"])) // 2)
    return day[f"{slot}_time"]


def reserve_eat_out(ctx, dates, taken):
    """Place reserved eat-out slots: away days first, then the latest dinners."""
    count = ctx["eat_out_slots_left"]
    if count <= 0:
        return []
    candidates = []
    for d in dates:
        day = ctx["schedule"][d.weekday()]
        lim = slot_limits(day)
        for slot in ("dinner", "lunch"):
            if (d, slot) in taken or (d, slot) in ctx["skip"]:
                continue
            rank = 0 if lim[slot]["away"] else (1 if slot == "dinner" else 2)
            candidates.append((rank, -d.toordinal(), d, slot))
    candidates.sort()
    return [(d, slot) for _, _, d, slot in candidates[:count]]


def plan(ctx, dates):
    """Fill every empty slot for the given dates.

    ctx keys used: today, recipes, settings, targets, schedule (weekday -> dict), pantry_lots,
    fridge_leftovers, history, taste, favorites, feedback, boosters, quick_picks, allergies,
    dislikes, spice_tolerance, flavor_likes, budget_cap, eat_out_slots_left, existing (list of meals),
    exclude ({(date, slot): {recipe ids}}), skip (set of (date, slot) not to fill).
    """
    s = ctx["settings"]
    today = ctx["today"]
    pantry = PantrySim(ctx["pantry_lots"])
    leftovers = [dict(lo) for lo in ctx["fridge_leftovers"]]
    recipes = [r for r in ctx["recipes"] if r["ingredients"] and not blocked(r, ctx)]
    gym_days = sum(1 for d in ctx["schedule"].values() if d["gym"])

    chosen = []
    taken = {}
    budget_left = ctx["budget_cap"]
    for m in sorted(ctx["existing"], key=lambda m: m["date"]):
        taken.setdefault((m["date"], m["slot"]), []).append(m)
        if m["status"] not in ("draft", "approved"):
            continue
        if m["kind"] in ("cook", "nocook", "snack") and m.get("recipe"):
            # what kept meals still need to buy, given the pantry as it is now
            for ing, grams in scaled_ingredients(m["recipe"], m["cook_portions"]):
                missing = pantry.take(ing["id"], grams, m["date"])
                budget_left -= missing / 100 * (ing.get("price_per_100g") or 0)
        elif m["kind"] == "konbini":
            budget_left -= m.get("buy_cost", 0)
        if m["kind"] == "leftover" and m.get("leftover_id"):
            for lo in leftovers:
                if lo["id"] == m["leftover_id"]:
                    lo["portions"] -= m["portion"]
    reserved = {}
    for d, slot in reserve_eat_out(ctx, dates, taken):
        reserved[(d, slot)] = {
            "date": d, "slot": slot, "kind": "eat_out", "recipe_id": None, "portion": 1, "cook_portions": 0,
            "title": "Eat out", "kcal": s["eat_out_kcal"], "protein": EAT_OUT_PROTEIN_GUESS,
            "carbs": 0, "fat": 0, "cost": s["eat_out_budget_yen"], "buy_cost": 0,
            "note": f"Reserved: up to {s['eat_out_kcal']} kcal and ¥{s['eat_out_budget_yen']}",
        }

    meals_left = sum(1 for d in dates for slot in MEAL_SLOTS if (d, slot) not in taken)
    next_key = 0

    for d in dates:
        day = ctx["schedule"][d.weekday()]
        limits = slot_limits(day)
        kcal_target, protein_target = day_targets(ctx["targets"], day["gym"], gym_days, s["sex"])
        snack_kcal = min(s["snack_kcal"], kcal_target // 5)
        day_meals = [m for (md, _), ms in taken.items() if md == d for m in ms]
        day_kcal = sum(m["kcal"] for m in day_meals)
        day_protein = sum(m["protein"] for m in day_meals)
        open_slots = [slot for slot in MEAL_SLOTS if (d, slot) not in taken and (d, slot) not in ctx["skip"]]
        # skipped slots (already past, or left empty on purpose) still count as their usual share,
        # so a plan made in the evening doesn't put the whole day into dinner
        for slot in MEAL_SLOTS:
            if (d, slot) in ctx["skip"] and (d, slot) not in taken:
                day_kcal += (kcal_target - snack_kcal) * SLOT_SHARE[slot]
                day_protein += protein_target * SLOT_SHARE[slot]

        for slot in MEAL_SLOTS:
            if slot not in open_slots:
                continue
            meals_left -= 1
            remaining_share = sum(SLOT_SHARE[x] for x in open_slots[open_slots.index(slot):])
            target = max(150, (kcal_target - snack_kcal - day_kcal) * SLOT_SHARE[slot] / remaining_share)
            protein_gap = protein_target - day_protein
            meal = None

            if (d, slot) in reserved:
                meal = reserved.pop((d, slot))

            # leftovers already cooked and in the fridge
            if meal is None and slot != "breakfast":
                usable = [lo for lo in leftovers if lo["portions"] >= 0.5 and lo["safe_until"] >= d
                          and (not limits[slot]["away"] or lo.get("portable", True))]
                if usable:
                    lo = min(usable, key=lambda x: x["safe_until"])
                    portion = min(1.0, lo["portions"])
                    lo["portions"] -= portion
                    meal = {"date": d, "slot": slot, "kind": "leftover", "recipe_id": lo.get("recipe_id"),
                            "leftover_id": lo["id"], "portion": portion, "cook_portions": 0,
                            "title": lo["title"], "cost": 0, "buy_cost": 0,
                            "note": f"Leftover, eat by {lo['safe_until'].isoformat()}",
                            **{m: lo[m] * portion for m in MACROS}}

            if meal is None:
                best = None
                excluded = ctx["exclude"].get((d, slot), set())
                for r in recipes:
                    if r["id"] in excluded or not fits_slot(r, slot, limits, d, today):
                        continue
                    portion = best_portion(r["per_serving"]["kcal"], target)
                    batch = (r["batch_ok"] and slot != "breakfast" and not busy(day)
                             and not limits[slot]["away"])
                    cook_portions = portion
                    slots_for_batch = []
                    if batch:
                        slots_for_batch = batch_slots(ctx, dates, d, r, taken, reserved, chosen)
                        cook_portions = portion * (1 + len(slots_for_batch))
                    check = purchase_check(r, cook_portions, pantry, d)
                    if check["buy"] > budget_left:
                        continue
                    sc = score(r, portion, target, check, ctx, d, chosen, day["gym"], budget_left,
                               meals_left + 1, protein_gap)
                    if slots_for_batch:
                        sc += 0.1
                    if best is None or sc > best[0]:
                        best = (sc, r, portion, cook_portions, check, slots_for_batch)

                if best:
                    _, r, portion, cook_portions, check, slots_for_batch = best
                    key = f"g{next_key}"
                    next_key += 1
                    for ing, grams in scaled_ingredients(r, cook_portions):
                        pantry.take(ing["id"], grams, d)
                    budget_left -= check["buy"]
                    kind = "cook" if r["active_min"] > 0 else "nocook"
                    full_cost = r["per_serving"]["cost"] * cook_portions
                    meal = {"date": d, "slot": slot, "kind": kind, "recipe_id": r["id"], "recipe": r,
                            "portion": portion, "cook_portions": cook_portions, "cook_key": key,
                            "title": r["name"], "cost": full_cost, "buy_cost": check["buy"],
                            "note": "", **macros_for(r, portion)}
                    if r["thaw_hours"]:
                        meal["note"] = f"Thaw {r['thaw_hours']} h ahead: move to the fridge the night before"
                    if len(slots_for_batch):
                        meal["note"] = (meal["note"] + " · " if meal["note"] else "") + \
                            f"Batch cook {cook_portions:g} portions"
                    booster = pick_booster(r, ctx, target - meal["kcal"])
                    if booster:
                        meal["booster_id"] = booster["id"]
                        meal["kcal"] += booster["kcal"]
                        meal["protein"] += booster["protein"]
                        meal["note"] = (meal["note"] + " · " if meal["note"] else "") + f"Add {booster['name']}"
                    for ld, lslot in slots_for_batch:
                        lmeal = {"date": ld, "slot": lslot, "kind": "leftover", "recipe_id": r["id"],
                                 "recipe": r, "portion": portion, "cook_portions": 0, "cook_key": key,
                                 "title": r["name"], "cost": 0, "buy_cost": 0,
                                 "note": f"From the {d.strftime('%a')} batch", **macros_for(r, portion)}
                        reserved[(ld, lslot)] = lmeal

            if meal is None and limits[slot]["away"]:
                combo = konbini_combo(ctx["quick_picks"], target, budget_left)
                if combo["items"]:
                    budget_left -= combo["yen"]
                    meal = {"date": d, "slot": slot, "kind": "konbini", "recipe_id": None, "portion": 1,
                            "cook_portions": 0, "title": " + ".join(p["item"] for p in combo["items"]),
                            "kcal": combo["kcal"], "protein": combo["protein"], "carbs": 0, "fat": 0,
                            "cost": combo["yen"], "buy_cost": combo["yen"],
                            "note": "Konbini fallback: no packable meal fit this slot"}

            if meal is None:
                meal = {"date": d, "slot": slot, "kind": "empty", "recipe_id": None, "portion": 0,
                        "cook_portions": 0, "title": "Nothing fits", "kcal": 0, "protein": 0, "carbs": 0,
                        "fat": 0, "cost": 0, "buy_cost": 0,
                        "note": "No recipe fits the time, budget and filters. Add a recipe or loosen settings."}

            meal["eat_time"] = eat_time(day, slot)
            meal.setdefault("status", "draft")
            chosen.append(meal)
            taken.setdefault((d, slot), []).append(meal)
            day_kcal += meal["kcal"]
            day_protein += meal["protein"]

        # snack: fill what's left of the allowance, protein first if the day is short
        if (d, "snack") not in taken and (d, "snack") not in ctx["skip"]:
            room = min(snack_kcal, kcal_target - day_kcal)
            snack = pick_snack(recipes, ctx, d, room, protein_target - day_protein, pantry, budget_left, chosen)
            if snack:
                r, portion, check = snack
                for ing, grams in scaled_ingredients(r, portion):
                    pantry.take(ing["id"], grams, d)
                budget_left -= check["buy"]
                meal = {"date": d, "slot": "snack", "kind": "snack", "recipe_id": r["id"], "recipe": r,
                        "portion": portion, "cook_portions": portion, "title": r["name"],
                        "cost": r["per_serving"]["cost"] * portion, "buy_cost": check["buy"], "note": "",
                        "eat_time": eat_time(day, "snack"), "status": "draft", **macros_for(r, portion)}
                chosen.append(meal)
                taken.setdefault((d, "snack"), []).append(meal)

    return chosen


def batch_slots(ctx, dates, cook_date, recipe, taken, reserved, chosen):
    """Later slots a batch cook can cover, within the recipe's fridge life."""
    out = []
    for d in dates:
        if d <= cook_date or (d - cook_date).days > recipe["fridge_days"]:
            continue
        day = ctx["schedule"][d.weekday()]
        lim = slot_limits(day)
        for slot in ("lunch", "dinner"):
            if (d, slot) in taken or (d, slot) in reserved or (d, slot) in ctx["skip"]:
                continue
            if slot == "dinner" and not busy(day):
                continue  # free evenings get a fresh cook
            if lim[slot]["away"] and not recipe["portable"]:
                continue
            if day["away"]:
                continue
            out.append((d, slot))
            if len(out) >= MAX_BATCH_MEALS - 1:
                return out
    return out


def pick_snack(recipes, ctx, d, room, protein_gap, pantry, budget_left, chosen):
    if room < 60:
        return None
    best = None
    for r in recipes:
        if "snack" not in r["type_list"]:
            continue
        kcal = r["per_serving"]["kcal"]
        portion = max((p for p in PORTIONS if p * kcal <= room), default=None)
        if portion is None:
            continue
        check = purchase_check(r, portion, pantry, d)
        if check["buy"] > budget_left:
            continue
        protein = r["per_serving"]["protein"] * portion
        sc = ctx["taste"].get(r["id"], 0.6) * 0.4 + check["pantry_share"] * 0.2
        sc += min(1.0, protein * 4 / max(1, kcal * portion) / 0.4) * (0.4 if protein_gap > 0 else 0.15)
        sc -= 0.15 * sum(1 for m in chosen if m.get("recipe_id") == r["id"])
        if best is None or sc > best[0]:
            best = (sc, r, portion, check)
    return best[1:] if best else None


def thaw_reminders(meals, recipes_by_id, on):
    """Meals tomorrow that need thawing tonight."""
    tomorrow = on + timedelta(days=1)
    out = []
    for m in meals:
        r = recipes_by_id.get(m["recipe_id"])
        if r and r["thaw_hours"] and m["kind"] == "cook" and m["date"] == tomorrow:
            out.append({"meal": m, "recipe": r, "at": "21:00"})
    return out


def start_cooking_at(meal, recipe):
    if not meal.get("eat_time") or not recipe:
        return None
    return hhmm(minutes(meal["eat_time"]) - recipe["total_min"])
