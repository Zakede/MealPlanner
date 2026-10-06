"""Where you live and shop changes what food costs. Built-in prices are Japanese supermarket
prices in yen; these factors turn them into estimates for the user's country, area and shop.
Prices the user actually paid (receipts, pantry) always win over estimates."""

# code: (name, currency symbol, currency code, local units per yen, food price level vs Japan)
COUNTRIES = {
    "JP": ("Japan", "¥", "JPY", 1.0, 1.0),
    "KR": ("South Korea", "₩", "KRW", 9.2, 1.25),
    "TW": ("Taiwan", "NT$", "TWD", 0.21, 0.85),
    "US": ("United States", "$", "USD", 0.0067, 1.45),
    "CA": ("Canada", "C$", "CAD", 0.0092, 1.4),
    "GB": ("United Kingdom", "£", "GBP", 0.0052, 1.3),
    "DE": ("Germany", "€", "EUR", 0.0062, 1.2),
    "AU": ("Australia", "A$", "AUD", 0.0102, 1.45),
    "IN": ("India", "₹", "INR", 0.56, 0.45),
}

# Japan only for now: rough price differences by area and by type of shop.
AREAS = {
    "tokyo": ("Central Tokyo", 1.08),
    "big_city": ("Big city (Yokohama, Osaka, Nagoya…)", 1.03),
    "city": ("Regional city", 1.0),
    "rural": ("Countryside", 0.95),
}
SHOPS = {
    "gyomu": ("Gyomu Super / bulk", 0.82),
    "discount": ("Discount (OK, Trial, Lopia)", 0.88),
    "chain": ("Aeon, Seiyu, Ito-Yokado", 0.95),
    "supermarket": ("Regular supermarket", 1.0),
    "premium": ("Premium (Seijo Ishii, Kinokuniya)", 1.35),
    "konbini": ("Mostly konbini", 1.3),
}


def factor(s):
    """Multiplier from built-in yen prices to the user's local estimate."""
    country = COUNTRIES.get(s.get("country") or "JP", COUNTRIES["JP"])
    f = country[3] * country[4]
    if (s.get("country") or "JP") == "JP":
        f *= AREAS.get(s.get("area"), AREAS["city"])[1] * SHOPS.get(s.get("shop"), SHOPS["supermarket"])[1]
    else:
        f *= SHOPS.get(s.get("shop"), SHOPS["supermarket"])[1]
    return f


def currency(s):
    return COUNTRIES.get(s.get("country") or "JP", COUNTRIES["JP"])[1]


def in_japan(s):
    return (s.get("country") or "JP") == "JP"
