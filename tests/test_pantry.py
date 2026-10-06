from mealplanner import store
from mealplanner.db import query


def item(**kw):
    data = {"name": "Chicken breast", "quantity": "500", "unit": "g", "price_paid": "398",
            "expiry": "2026-10-09", "location": "fridge",
            "kcal": "105", "protein": "23.3", "carbs": "0", "fat": "1.9", "piece_g": "", "allergens": ""}
    data.update(kw)
    return data


def test_add_item_records_price(app, client):
    resp = client.post("/pantry/new", data=item(), follow_redirects=True)
    assert b"Chicken breast" in resp.data
    with app.app_context():
        f = store.food_by_name("chicken breast")
        assert round(f["current_price"], 1) == 79.6
        items = store.pantry_items(store_today(app))
        assert items[0]["grams"] == 500 and items[0]["days_left"] == 2


def store_today(app):
    from datetime import date
    return date.fromisoformat(app.config["TODAY"])


def test_new_food_created_from_pantry_form(app, client):
    client.post("/pantry/new", data=item(name="Tempeh", kcal="192", protein="20", carbs="8", fat="11"))
    with app.app_context():
        assert store.food_by_name("tempeh")["protein"] == 20


def test_pieces_without_weight_rejected(app, client):
    resp = client.post("/pantry/new", data=item(name="Mystery", unit="pcs"), follow_redirects=True)
    assert b"piece weight unknown" in resp.data
    with app.app_context():
        assert query("SELECT COUNT(*) c FROM pantry_items", one=True)["c"] == 0


def test_pantry_form_keeps_allergens(app, client):
    data = item(name="Egg", unit="pcs", quantity="10", kcal="142", protein="12.2", carbs="0.4", fat="10.2")
    del data["allergens"]
    client.post("/pantry/new", data=data)
    with app.app_context():
        assert store.food_by_name("egg")["allergens"] == "egg"


def test_edit_and_delete(app, client):
    client.post("/pantry/new", data=item())
    client.post("/pantry/1/edit", data=item(quantity="250"))
    with app.app_context():
        assert query("SELECT quantity FROM pantry_items WHERE id = 1", one=True)["quantity"] == 250
    client.post("/pantry/1/delete")
    with app.app_context():
        assert query("SELECT COUNT(*) c FROM pantry_items", one=True)["c"] == 0


def test_pages_render(client):
    for url in ("/pantry/", "/pantry/new", "/pantry/foods", "/pantry/foods/1", "/pantry/api/foods"):
        assert client.get(url).status_code == 200
