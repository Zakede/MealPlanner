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

GENERIC_AREAS = {
    "big_city": ("Big city", 1.05),
    "city": ("Town or smaller city", 1.0),
    "rural": ("Countryside", 0.95),
}
AREAS_BY_COUNTRY = {
    "JP": {
        "tokyo": ("Central Tokyo", 1.08),
        "big_city": ("Big city (Yokohama, Osaka, Nagoya…)", 1.03),
        "city": ("Regional city", 1.0),
        "rural": ("Countryside", 0.95),
    },
}

GENERIC_SHOPS = {
    "discount": ("Discount / bulk", 0.85),
    "supermarket": ("Regular supermarket", 1.0),
    "premium": ("Premium / organic", 1.3),
    "convenience": ("Mostly convenience stores", 1.35),
}
SHOPS_BY_COUNTRY = {
    "JP": {
        "gyomu": ("Gyomu Super / bulk", 0.82),
        "discount": ("Discount (OK, Trial, Lopia)", 0.88),
        "chain": ("Aeon, Seiyu, Ito-Yokado", 0.95),
        "supermarket": ("Regular supermarket", 1.0),
        "premium": ("Premium (Seijo Ishii, Kinokuniya)", 1.35),
        "convenience": ("Mostly konbini", 1.3),
    },
    "US": {
        "discount": ("Costco, Aldi, Walmart", 0.85),
        "supermarket": ("Kroger, Safeway, Target", 1.0),
        "premium": ("Whole Foods, Trader Joe's", 1.25),
        "convenience": ("Mostly convenience stores", 1.4),
    },
    "GB": {
        "discount": ("Aldi, Lidl", 0.85),
        "supermarket": ("Tesco, Sainsbury's, Asda", 1.0),
        "premium": ("Waitrose, M&S", 1.3),
        "convenience": ("Mostly corner shops", 1.3),
    },
    "DE": {
        "discount": ("Aldi, Lidl, Penny", 0.85),
        "supermarket": ("Rewe, Edeka", 1.0),
        "premium": ("Bio shops", 1.3),
        "convenience": ("Kiosk / Späti", 1.35),
    },
    "AU": {
        "discount": ("Aldi", 0.85),
        "supermarket": ("Woolworths, Coles", 1.0),
        "premium": ("Harris Farm, delis", 1.3),
        "convenience": ("Mostly convenience stores", 1.4),
    },
    "KR": {
        "discount": ("Traders, Costco", 0.85),
        "supermarket": ("E-mart, Lotte Mart", 1.0),
        "premium": ("Department store food halls", 1.35),
        "convenience": ("Mostly convenience stores", 1.3),
    },
}


def areas(country):
    return AREAS_BY_COUNTRY.get(country, GENERIC_AREAS)


def shops(country):
    return SHOPS_BY_COUNTRY.get(country, GENERIC_SHOPS)


def country_code(s):
    code = s.get("country") or "JP"
    return code if code in COUNTRIES else "JP"


def factor(s):
    """Multiplier from built-in yen prices to the user's local estimate."""
    code = country_code(s)
    _, _, _, rate, level = COUNTRIES[code]
    area = areas(code).get(s.get("area"), (None, 1.0))[1]
    shop = shops(code).get(s.get("shop"), (None, 1.0))[1]
    return rate * level * area * shop


def currency(s):
    return COUNTRIES[country_code(s)][1]


def in_japan(s):
    return country_code(s) == "JP"


def options_json():
    """Everything the settings pages need to switch countries without a reload."""
    return {
        code: {
            "symbol": c[1],
            "money": c[3] * c[4],   # how a yen-based budget scales into this country
            "areas": [[k, v[0]] for k, v in areas(code).items()],
            "shops": [[k, v[0]] for k, v in shops(code).items()],
        }
        for code, c in COUNTRIES.items()
    }


# kept for older imports
AREAS = AREAS_BY_COUNTRY["JP"]
SHOPS = SHOPS_BY_COUNTRY["JP"]
ALL_AREAS = {k for c in [GENERIC_AREAS, *AREAS_BY_COUNTRY.values()] for k in c}
ALL_SHOPS = {k for c in [GENERIC_SHOPS, *SHOPS_BY_COUNTRY.values()] for k in c}
