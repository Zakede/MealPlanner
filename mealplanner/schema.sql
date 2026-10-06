-- Meal planner schema. All quantities are metric (grams, cm, kg); money is integer JPY.

CREATE TABLE IF NOT EXISTS settings (
    id                 INTEGER PRIMARY KEY CHECK (id = 1),
    height_cm          REAL    NOT NULL DEFAULT 190,
    weight_kg          REAL    NOT NULL DEFAULT 85,
    goal_weight_kg     REAL    NOT NULL DEFAULT 78,
    age                INTEGER,
    sex                TEXT    CHECK (sex IN ('male', 'female')),
    activity           TEXT    NOT NULL DEFAULT 'light',
    pace_kg_week       REAL    NOT NULL DEFAULT 0.5,
    weekly_budget_yen  INTEGER NOT NULL DEFAULT 10000,
    eat_out_slots      INTEGER NOT NULL DEFAULT 1,
    eat_out_budget_yen INTEGER NOT NULL DEFAULT 1200,
    eat_out_kcal       INTEGER NOT NULL DEFAULT 800,
    snack_kcal         INTEGER NOT NULL DEFAULT 200,
    allergies          TEXT    NOT NULL DEFAULT '',
    dislikes           TEXT    NOT NULL DEFAULT '',
    units              TEXT    NOT NULL DEFAULT 'metric',
    spice_tolerance    INTEGER NOT NULL DEFAULT 4,
    flavor_likes       TEXT    NOT NULL DEFAULT '',
    cuisines_liked     TEXT    NOT NULL DEFAULT '',
    cuisines_tired     TEXT    NOT NULL DEFAULT '',
    theme              TEXT    NOT NULL DEFAULT 'apothecary',
    mode               TEXT    NOT NULL DEFAULT 'dark',
    job                TEXT    NOT NULL DEFAULT 'desk',
    training_days      INTEGER NOT NULL DEFAULT 3,
    training_intensity TEXT    NOT NULL DEFAULT 'moderate',
    diet               TEXT    NOT NULL DEFAULT 'any',
    avoid              TEXT    NOT NULL DEFAULT '',
    setup_done         INTEGER NOT NULL DEFAULT 0,
    schedule_mode      TEXT    NOT NULL DEFAULT 'fixed',
    prep_days          INTEGER NOT NULL DEFAULT 2,
    appliances         TEXT    NOT NULL DEFAULT 'stove,microwave,rice_cooker,freezer',
    about_me           TEXT    NOT NULL DEFAULT '',
    gemini_key         TEXT    NOT NULL DEFAULT '',
    country            TEXT    NOT NULL DEFAULT 'JP',
    area               TEXT    NOT NULL DEFAULT 'city',
    shop               TEXT    NOT NULL DEFAULT 'supermarket'
);

-- One row per weekday (0 = Monday).
CREATE TABLE IF NOT EXISTS schedule_days (
    weekday        INTEGER PRIMARY KEY CHECK (weekday BETWEEN 0 AND 6),
    wake           TEXT    NOT NULL DEFAULT '07:00',
    work_start     TEXT,
    work_end       TEXT,
    commute_min    INTEGER NOT NULL DEFAULT 0,
    gym            INTEGER NOT NULL DEFAULT 0,
    breakfast_time TEXT    NOT NULL DEFAULT '07:30',
    lunch_time     TEXT    NOT NULL DEFAULT '12:30',
    dinner_time    TEXT    NOT NULL DEFAULT '19:00',
    effort         TEXT    NOT NULL DEFAULT 'low' CHECK (effort IN ('none', 'low', 'full')),
    away           INTEGER NOT NULL DEFAULT 0
);

-- Food catalogue: macros and reference price per 100 g. Pantry items and recipe
-- ingredients both point here.
CREATE TABLE IF NOT EXISTS foods (
    id             INTEGER PRIMARY KEY,
    name           TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    kcal           REAL    NOT NULL DEFAULT 0,
    protein        REAL    NOT NULL DEFAULT 0,
    carbs          REAL    NOT NULL DEFAULT 0,
    fat            REAL    NOT NULL DEFAULT 0,
    price_per_100g REAL,
    piece_g        REAL,
    allergens      TEXT    NOT NULL DEFAULT '',
    category       TEXT    NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS pantry_items (
    id         INTEGER PRIMARY KEY,
    food_id    INTEGER NOT NULL REFERENCES foods(id) ON DELETE CASCADE,
    quantity   REAL    NOT NULL,
    unit       TEXT    NOT NULL DEFAULT 'g' CHECK (unit IN ('g', 'ml', 'pcs')),
    expiry     TEXT,
    price_paid INTEGER,
    location   TEXT    NOT NULL DEFAULT 'fridge' CHECK (location IN ('fridge', 'freezer', 'shelf')),
    added_on   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS price_history (
    id             INTEGER PRIMARY KEY,
    food_id        INTEGER NOT NULL REFERENCES foods(id) ON DELETE CASCADE,
    price_per_100g REAL    NOT NULL,
    recorded_on    TEXT    NOT NULL,
    source         TEXT    NOT NULL DEFAULT 'manual'
);

CREATE TABLE IF NOT EXISTS recipes (
    id           INTEGER PRIMARY KEY,
    name         TEXT    NOT NULL UNIQUE,
    steps        TEXT    NOT NULL DEFAULT '',
    active_min   INTEGER NOT NULL DEFAULT 10,
    total_min    INTEGER NOT NULL DEFAULT 15,
    servings     INTEGER NOT NULL DEFAULT 1,
    tags         TEXT    NOT NULL DEFAULT '',
    spice_level  INTEGER NOT NULL DEFAULT 0,
    thaw_hours   INTEGER NOT NULL DEFAULT 0,
    meal_types   TEXT    NOT NULL DEFAULT 'lunch,dinner',
    cuisine      TEXT    NOT NULL DEFAULT '',
    batch_ok     INTEGER NOT NULL DEFAULT 0,
    portable     INTEGER NOT NULL DEFAULT 0,
    fridge_days  INTEGER NOT NULL DEFAULT 3,
    builtin      INTEGER NOT NULL DEFAULT 0,
    equipment    TEXT    NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS recipe_ingredients (
    id        INTEGER PRIMARY KEY,
    recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    food_id   INTEGER NOT NULL REFERENCES foods(id),
    grams     REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS flavor_boosters (
    id      INTEGER PRIMARY KEY,
    food_id INTEGER NOT NULL REFERENCES foods(id) ON DELETE CASCADE,
    grams   REAL    NOT NULL,
    tags    TEXT    NOT NULL DEFAULT '',
    note    TEXT    NOT NULL DEFAULT ''
);

-- Ingredient preferences: like / dislike / small (only in small amounts).
CREATE TABLE IF NOT EXISTS taste_scores (
    food_id INTEGER PRIMARY KEY REFERENCES foods(id) ON DELETE CASCADE,
    score   TEXT    NOT NULL CHECK (score IN ('like', 'dislike', 'small'))
);

CREATE TABLE IF NOT EXISTS ratings (
    id           INTEGER PRIMARY KEY,
    recipe_id    INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    plan_meal_id INTEGER,
    stars        INTEGER NOT NULL CHECK (stars BETWEEN 1 AND 5),
    tags         TEXT    NOT NULL DEFAULT '',
    rated_on     TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS plan_days (
    date           TEXT    PRIMARY KEY,
    kcal_target    INTEGER NOT NULL,
    protein_target INTEGER NOT NULL,
    gym            INTEGER NOT NULL DEFAULT 0,
    effort         TEXT    NOT NULL DEFAULT 'low',
    away           INTEGER NOT NULL DEFAULT 0
);

-- kind: cook | leftover | nocook | snack | eat_out | konbini | empty
-- status: draft | approved | cooked | eaten | skipped | eaten_out
CREATE TABLE IF NOT EXISTS plan_meals (
    id            INTEGER PRIMARY KEY,
    date          TEXT    NOT NULL,
    slot          TEXT    NOT NULL CHECK (slot IN ('breakfast', 'lunch', 'dinner', 'snack')),
    kind          TEXT    NOT NULL,
    recipe_id     INTEGER REFERENCES recipes(id) ON DELETE SET NULL,
    portion       REAL    NOT NULL DEFAULT 1,
    cook_portions REAL    NOT NULL DEFAULT 0,
    cook_group    INTEGER,
    leftover_id   INTEGER,
    booster_id    INTEGER REFERENCES flavor_boosters(id) ON DELETE SET NULL,
    title         TEXT    NOT NULL DEFAULT '',
    kcal          REAL    NOT NULL DEFAULT 0,
    protein       REAL    NOT NULL DEFAULT 0,
    carbs         REAL    NOT NULL DEFAULT 0,
    fat           REAL    NOT NULL DEFAULT 0,
    cost          REAL    NOT NULL DEFAULT 0,
    buy_cost      REAL    NOT NULL DEFAULT 0,
    status        TEXT    NOT NULL DEFAULT 'draft',
    replace_flag  INTEGER NOT NULL DEFAULT 0,
    eat_time      TEXT,
    note          TEXT    NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_plan_meals_date ON plan_meals(date);

CREATE TABLE IF NOT EXISTS plan_actions (
    id         INTEGER PRIMARY KEY,
    created_at TEXT    NOT NULL,
    action     TEXT    NOT NULL,
    payload    TEXT    NOT NULL,
    undone     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS leftovers (
    id           INTEGER PRIMARY KEY,
    recipe_id    INTEGER REFERENCES recipes(id) ON DELETE SET NULL,
    cook_meal_id INTEGER,
    title        TEXT    NOT NULL,
    portions     REAL    NOT NULL,
    kcal         REAL    NOT NULL,
    protein      REAL    NOT NULL,
    carbs        REAL    NOT NULL,
    fat          REAL    NOT NULL,
    cooked_on    TEXT    NOT NULL,
    safe_until   TEXT    NOT NULL,
    location     TEXT    NOT NULL DEFAULT 'fridge'
);

CREATE TABLE IF NOT EXISTS craving_swaps (
    id         INTEGER PRIMARY KEY,
    craving    TEXT    NOT NULL,
    swap       TEXT    NOT NULL,
    kcal_from  INTEGER,
    kcal_to    INTEGER,
    note       TEXT    NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS quick_picks (
    id      INTEGER PRIMARY KEY,
    chain   TEXT    NOT NULL,
    item    TEXT    NOT NULL,
    kcal    INTEGER NOT NULL,
    protein REAL    NOT NULL,
    yen     INTEGER NOT NULL,
    note    TEXT    NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS eating_out_log (
    id       INTEGER PRIMARY KEY,
    date     TEXT    NOT NULL,
    slot     TEXT    NOT NULL,
    place    TEXT    NOT NULL DEFAULT '',
    item     TEXT    NOT NULL DEFAULT '',
    kcal     INTEGER NOT NULL,
    protein  REAL    NOT NULL DEFAULT 0,
    yen      INTEGER NOT NULL DEFAULT 0,
    planned  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS shopping_list (
    id         INTEGER PRIMARY KEY,
    week_start TEXT    NOT NULL,
    food_id    INTEGER NOT NULL REFERENCES foods(id) ON DELETE CASCADE,
    grams      REAL    NOT NULL,
    est_cost   REAL    NOT NULL,
    checked    INTEGER NOT NULL DEFAULT 0
);

-- Side log only; does not change food targets.
CREATE TABLE IF NOT EXISTS workouts (
    id            INTEGER PRIMARY KEY,
    date          TEXT    NOT NULL,
    kind          TEXT    NOT NULL,
    minutes       INTEGER NOT NULL,
    effort        INTEGER NOT NULL CHECK (effort BETWEEN 1 AND 10),
    kcal          INTEGER NOT NULL,
    kcal_estimated INTEGER NOT NULL DEFAULT 1,
    note          TEXT    NOT NULL DEFAULT ''
);

-- favorite: plan more often. never: tried it, didn't like it. try: want to try soon.
CREATE TABLE IF NOT EXISTS recipe_prefs (
    recipe_id INTEGER PRIMARY KEY REFERENCES recipes(id) ON DELETE CASCADE,
    status    TEXT    NOT NULL CHECK (status IN ('favorite', 'never', 'try'))
);

-- One-off changes for a single date: "free today", "gym today", "away today".
CREATE TABLE IF NOT EXISTS day_overrides (
    date   TEXT PRIMARY KEY,
    effort TEXT CHECK (effort IN ('none', 'low', 'full')),
    gym    INTEGER,
    away   INTEGER
);

CREATE TABLE IF NOT EXISTS water_log (
    date TEXT PRIMARY KEY,
    ml   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS weight_log (
    date TEXT PRIMARY KEY,
    kg   REAL NOT NULL
);
