"""Show amounts in the viewer's units. Everything is stored metric; imperial is only for display (and input)."""
import re

from .nutrition import kg_to_lb, lb_to_kg

_CELSIUS = re.compile(r"(\d{2,3})\s?°C")


def imperial(s=None):
    if s is None:
        from .store import settings
        try:
            s = settings()
        except Exception:
            return False
    return (s or {}).get("units") == "imperial"


def body(kg, digits=1):
    """A body weight as a number in the viewer's unit (no label)."""
    if kg is None:
        return None
    return round(kg_to_lb(kg) if imperial() else kg, digits)


def body_unit():
    return "lb" if imperial() else "kg"


def body_in(value):
    """A typed body weight back to kg."""
    return lb_to_kg(value) if imperial() else value


def temps(text):
    """'Air fry at 200 °C' -> 'Air fry at 390 °F' for imperial viewers, rounded to the nearest 5."""
    if not text or not imperial():
        return text
    return _CELSIUS.sub(lambda m: f"{round((int(m.group(1)) * 9 / 5 + 32) / 5) * 5} °F", text)


def amount(grams):
    """Ingredient amount: '150 g', or '5.3 oz' for imperial viewers."""
    if grams is None:
        return ""
    if not imperial():
        return f"{grams:g} g" if isinstance(grams, float) else f"{grams} g"
    oz = grams / 28.3495
    return f"{oz:.1f} oz" if oz < 10 else f"{round(oz)} oz"


def register(app):
    app.add_template_filter(temps, "temps")
    app.add_template_filter(amount, "amount")
    app.add_template_filter(body, "body")
    app.add_template_global(body_unit, "body_unit")
    app.add_template_global(imperial, "is_imperial")
