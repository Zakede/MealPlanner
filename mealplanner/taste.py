"""Taste scoring from ratings and preferences. Returns 0..1 per recipe."""
PRIOR_STARS = 3.5
PRIOR_WEIGHT = 2
FAVORITE_STARS = 4.2


def bayes_stars(stars):
    """Average rating pulled toward a neutral prior so one rating doesn't dominate."""
    return (sum(stars) + PRIOR_STARS * PRIOR_WEIGHT) / (len(stars) + PRIOR_WEIGHT)


def is_favorite(stars):
    return len(stars) >= 2 and bayes_stars(stars) >= FAVORITE_STARS


def tag_affinity(ratings, recipe_tags):
    """How much each flavour tag is liked, learned from star ratings.

    ratings: list of (recipe_id, stars); recipe_tags: recipe_id -> list of tags.
    Returns tag -> value in roughly -1..1.
    """
    sums, counts = {}, {}
    for recipe_id, stars in ratings:
        for tag in recipe_tags.get(recipe_id, []):
            sums[tag] = sums.get(tag, 0) + (stars - 3) / 2
            counts[tag] = counts.get(tag, 0) + 1
    return {t: sums[t] / (counts[t] + 1) for t in sums}


def recipe_score(recipe, prefs):
    """prefs keys: stars (list), feedback_tags (list), flavor_likes, cuisines_liked, cuisines_tired,
    ingredient_scores (food_id -> like/dislike/small), affinity (tag -> -1..1)."""
    stars = prefs.get("stars", [])
    score = (bayes_stars(stars) - 1) / 4

    tags = set(recipe["tag_list"])
    score += 0.08 * min(2, len(tags & set(prefs.get("flavor_likes", []))))
    affinity = prefs.get("affinity", {})
    if tags:
        score += 0.1 * sum(affinity.get(t, 0) for t in tags) / len(tags)

    cuisine = recipe.get("cuisine") or ""
    if cuisine and cuisine in prefs.get("cuisines_liked", []):
        score += 0.08
    if cuisine and cuisine in prefs.get("cuisines_tired", []):
        score -= 0.15

    servings = max(1, recipe["servings"])
    for ing in recipe["ingredients"]:
        pref = prefs.get("ingredient_scores", {}).get(ing["id"])
        if pref == "like":
            score += 0.05
        elif pref == "dislike":
            score -= 0.25
        elif pref == "small" and ing["grams"] / servings > 30:
            score -= 0.1

    feedback = prefs.get("feedback_tags", [])
    if "too spicy" in feedback:
        score -= 0.2
    if "too bland" in feedback:
        score -= 0.05
    if "loved it" in feedback:
        score += 0.05
    return max(0.0, min(1.0, score))
