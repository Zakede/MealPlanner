"""Best guesses for a food you add without knowing its numbers.

A built-in table covers common foods (per 100 g, JPY reference price). Anything else can be asked
of the AI helper. Prices left blank are filled by the price model from the food's category.
"""
import re

CATEGORIES = ("poultry", "meat", "fish", "seafood", "egg", "dairy", "soy", "legume", "grain",
              "veg", "fruit", "sauce", "fat", "snack")

# keywords, kcal, protein, carbs, fat, JPY per 100 g, category, allergens
GUESSES = [
    (("ground beef", "minced beef", "beef mince", "牛ひき肉", "牛ミンチ"), 251, 17.1, 0.3, 21.1, 250, "meat", ""),
    (("lean ground beef", "lean beef mince", "赤身ひき肉"), 170, 20.0, 0.3, 10.0, 300, "meat", ""),
    (("ground pork", "minced pork", "pork mince", "豚ひき肉"), 209, 17.7, 0.1, 15.1, 140, "meat", ""),
    (("mixed mince", "beef and pork mince", "合いびき", "合挽き"), 236, 17.3, 0.3, 18.4, 160, "meat", ""),
    (("ground chicken", "chicken mince", "鶏ひき肉"), 171, 17.5, 0, 12.0, 110, "poultry", ""),
    (("ground turkey", "turkey mince"), 150, 19.0, 0, 8.0, 300, "poultry", ""),
    (("chicken breast", "鶏むね"), 105, 23.3, 0, 1.9, 85, "poultry", ""),
    (("chicken thigh", "鶏もも"), 127, 19.0, 0, 5.0, 110, "poultry", ""),
    (("chicken tender", "sasami", "ささみ"), 98, 23.9, 0.1, 0.8, 120, "poultry", ""),
    (("chicken wing", "手羽"), 189, 17.5, 0, 13.0, 90, "poultry", ""),
    (("pork loin", "豚ロース"), 248, 19.3, 0.2, 19.2, 200, "meat", ""),
    (("pork tenderloin", "pork fillet", "豚ヒレ"), 118, 22.2, 0.3, 3.7, 250, "meat", ""),
    (("pork belly", "豚バラ"), 366, 14.4, 0.1, 35.4, 180, "meat", ""),
    (("pork shoulder", "豚肩"), 201, 18.5, 0.2, 14.6, 160, "meat", ""),
    (("beef steak", "sirloin", "サーロイン"), 260, 19.0, 0.4, 20.0, 600, "meat", ""),
    (("beef round", "beef thigh", "牛もも"), 140, 21.0, 0.4, 5.5, 300, "meat", ""),
    (("lamb", "ラム", "mutton"), 233, 17.0, 0.1, 19.0, 400, "meat", ""),
    (("bacon", "ベーコン"), 400, 12.9, 0.3, 39.1, 250, "meat", ""),
    (("ham", "ハム"), 115, 16.5, 1.2, 4.5, 250, "meat", ""),
    (("sausage", "ウインナー", "ソーセージ"), 319, 11.5, 3.3, 30.6, 200, "meat", "wheat"),
    (("salmon", "鮭", "サーモン"), 124, 22.3, 0.1, 4.1, 250, "fish", "fish"),
    (("mackerel", "saba", "サバ", "鯖"), 211, 20.6, 0.3, 16.8, 200, "fish", "fish"),
    (("sardine", "イワシ", "鰯"), 156, 19.2, 0.2, 9.2, 150, "fish", "fish"),
    (("cod", "タラ", "鱈"), 72, 17.6, 0.1, 0.2, 200, "fish", "fish"),
    (("tuna steak", "maguro", "マグロ"), 115, 26.4, 0.1, 1.4, 350, "fish", "fish"),
    (("canned tuna", "tuna can", "ツナ缶"), 70, 16.0, 0.2, 0.7, 150, "fish", "fish"),
    (("shrimp", "prawn", "エビ", "海老"), 82, 18.4, 0.3, 0.6, 250, "seafood", "shellfish"),
    (("squid", "イカ"), 76, 17.9, 0.1, 0.8, 200, "seafood", "shellfish"),
    (("scallop", "ホタテ"), 66, 13.5, 1.5, 0.9, 400, "seafood", "shellfish"),
    (("egg", "卵", "たまご"), 142, 12.2, 0.4, 10.2, 30, "egg", "egg"),
    (("firm tofu", "momen", "木綿"), 73, 7.0, 1.5, 4.9, 35, "soy", "soy"),
    (("silken tofu", "kinu", "絹"), 56, 5.3, 2.0, 3.5, 35, "soy", "soy"),
    (("tempeh",), 192, 20.0, 7.6, 11.0, 300, "soy", "soy"),
    (("natto", "納豆"), 190, 16.5, 12.1, 10.0, 80, "soy", "soy"),
    (("edamame", "枝豆"), 125, 11.7, 8.8, 6.2, 120, "soy", "soy"),
    (("chickpea", "ひよこ豆"), 149, 9.5, 27.4, 2.5, 100, "legume", ""),
    (("lentil", "レンズ豆"), 116, 9.0, 20.0, 0.4, 100, "legume", ""),
    (("greek yogurt", "ギリシャヨーグルト"), 92, 10.3, 4.0, 3.0, 120, "dairy", "dairy"),
    (("cottage cheese", "カッテージ"), 99, 13.3, 1.9, 4.5, 150, "dairy", "dairy"),
    (("mozzarella", "モッツァレラ"), 269, 18.4, 4.2, 19.9, 300, "dairy", "dairy"),
    (("cheddar", "cheese", "チーズ"), 390, 25.7, 1.4, 31.0, 250, "dairy", "dairy"),
    (("milk", "牛乳"), 61, 3.3, 4.8, 3.8, 25, "dairy", "dairy"),
    (("protein powder", "whey", "プロテイン"), 380, 75.0, 8.0, 6.0, 350, "dairy", "dairy"),
    (("oats", "oatmeal", "オートミール"), 350, 13.7, 69.1, 5.7, 70, "grain", ""),
    (("pasta", "spaghetti", "パスタ"), 347, 12.9, 73.1, 1.8, 50, "grain", "wheat"),
    (("bread", "パン", "食パン"), 248, 8.9, 46.4, 4.1, 60, "grain", "wheat"),
    (("rice", "ご飯", "米"), 156, 2.5, 37.1, 0.3, 40, "grain", ""),
    (("soba", "そば"), 130, 4.8, 26.0, 1.0, 80, "grain", "wheat, buckwheat"),
    (("potato", "じゃがいも"), 59, 1.8, 17.3, 0.1, 40, "veg", ""),
    (("sweet potato", "さつまいも"), 126, 1.2, 33.1, 0.2, 60, "veg", ""),
    (("broccoli", "ブロッコリー"), 37, 5.4, 6.6, 0.6, 80, "veg", ""),
    (("spinach", "ほうれん草"), 18, 2.2, 3.1, 0.4, 100, "veg", ""),
    (("mushroom", "きのこ", "しめじ", "えのき"), 22, 2.7, 4.8, 0.3, 80, "veg", ""),
    (("eggplant", "aubergine", "なす", "茄子"), 18, 1.1, 5.1, 0.1, 70, "veg", ""),
    (("tomato", "トマト"), 20, 0.7, 4.7, 0.1, 80, "veg", ""),
    (("avocado", "アボカド"), 178, 2.1, 7.9, 17.5, 150, "fruit", ""),
    (("banana", "バナナ"), 93, 1.1, 22.5, 0.2, 40, "fruit", ""),
    (("apple", "りんご"), 53, 0.1, 15.5, 0.2, 60, "fruit", ""),
    (("olive oil", "オリーブオイル"), 894, 0, 0, 100, 150, "fat", ""),
    (("peanut butter", "ピーナッツバター"), 599, 20.6, 20.6, 50.4, 200, "fat", "peanut"),
    (("almond", "アーモンド"), 609, 19.6, 20.9, 51.8, 250, "snack", "tree nuts"),
]


def _norm(text):
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def guess(name):
    """Numbers for a food name from the built-in table (longest keyword wins), or None."""
    n = _norm(name)
    if not n:
        return None
    best = None
    for keys, kcal, protein, carbs, fat, yen, category, allergens in GUESSES:
        for k in keys:
            if k in n and (best is None or len(k) > best[0]):
                best = (len(k), {"kcal": kcal, "protein": protein, "carbs": carbs, "fat": fat,
                                 "price_jpy": yen, "category": category, "allergens": allergens})
    return dict(best[1], source="table") if best else None


def ai_prompt(name, country):
    return (
        "You estimate nutrition and price for a food item for a meal planning app.\n"
        f"Food: {name}\nShopper's country: {country}\n"
        "Reply with JSON only: {\"kcal\": number, \"protein\": number, \"carbs\": number, \"fat\": number, "
        "\"price_jpy\": number, \"category\": one of " + ", ".join(CATEGORIES) + ", \"allergens\": comma list}.\n"
        "Nutrition is per 100 g as sold (raw for meat and fish). price_jpy is a typical supermarket price per 100 g "
        "converted to Japanese yen. Use common allergen words: egg, dairy, wheat, soy, fish, shellfish, peanut, "
        "tree nuts, sesame, buckwheat."
    )


def validate_ai(data):
    """Clean an AI answer into the same shape as guess(), or None if it doesn't add up."""
    try:
        out = {k: float(data[k]) for k in ("kcal", "protein", "carbs", "fat")}
    except (KeyError, TypeError, ValueError):
        return None
    if not (0 <= out["kcal"] <= 900) or any(not (0 <= out[k] <= 100) for k in ("protein", "carbs", "fat")):
        return None
    # energy from macros should roughly match the kcal given
    if out["kcal"] > 20 and abs(out["protein"] * 4 + out["carbs"] * 4 + out["fat"] * 9 - out["kcal"]) > out["kcal"] * 0.35 + 15:
        return None
    try:
        price = float(data.get("price_jpy"))
        out["price_jpy"] = round(price) if 0 < price < 20000 else None
    except (TypeError, ValueError):
        out["price_jpy"] = None
    out["category"] = data.get("category") if data.get("category") in CATEGORIES else ""
    out["allergens"] = str(data.get("allergens") or "")[:80]
    out["source"] = "ai"
    return out
