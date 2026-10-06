# Meal Planner

A self-hosted meal planner for cutting weight on a budget in Japan. It plans high-protein,
low-calorie meals from what's already in the fridge, keeps the week inside a yen budget, and
leaves room for snacks, cravings and eating out without wrecking the plan.

Flask + SQLite with a mobile-first web UI, meant to run on a home machine and be opened on a phone.

## What it does

- **Targets**: calories and macros from body stats (Mifflin-St Jeor + activity), with a calorie
  floor and a 0.75 kg/week pace cap. Gym days get more, rest days less, same weekly total.
- **Pantry**: stock with expiry dates and prices paid; price history per food.
- **Recipes**: macros and cost per serving computed from ingredients and current prices.
- **Weekly planner**: fills breakfast, lunch, dinner and a snack for each day. Hard filters
  (allergies, dislikes, spice, time available) then a score for taste, protein per kcal, budget
  fit and expiring stock. Batch cooks on free days turn into leftover lunches. Konbini is only a
  last resort. The budget is a hard limit.
- **Draft → approve**: mark meals to swap, approve, get a shopping list with estimated cost.
- **Push back**: slide tonight and everything after by 1-2 days, with undo.
- **Cook mode**: scaled grams, one step at a time with timers, screen kept awake. Finishing
  deducts from the pantry and stores extra portions as leftovers (fridge or freezer).
- **Taste learning**: star ratings and quick tags ("too spicy", "loved the crunch") shift future
  plans; ingredient likes/dislikes; favourites come back sooner.
- **Eating out**: reserved weekly slots with their own kcal and yen; logging an unplanned meal
  drops snacks and trims later portions instead of breaking the plan. Konbini and McDonald's
  quick picks ranked by protein per kcal.
- **Spending**: paid vs estimated, expected weekly total, price changes, past weeks.
- **Recipe ideas**: asks a model (DeepSeek through the opencode CLI) for a recipe using only
  foods in the catalogue. The app checks allergens and recomputes every number itself before
  it can be saved.
- **Workouts**: optional side log with calorie estimates from MET values.
- **Themes**: Apothecary (default) and Wakatake + Momo, each in dark and light.

## Running it

```bash
pip install -r requirements.txt
python run.py            # http://0.0.0.0:5000, open it from your phone on the same network
python -m pytest         # 100+ tests
```

| Variable | Default | Purpose |
|---|---|---|
| `MEALPLANNER_DB` | `instance/mealplanner.db` | SQLite file |
| `MEALPLANNER_SECRET` | dev value | Flask secret key |
| `MEALPLANNER_HOST` / `MEALPLANNER_PORT` | `0.0.0.0` / `5000` | Bind address |
| `MEALPLANNER_LLM` | `opencode` | Set to `none` to turn recipe ideas off |
| `MEALPLANNER_LLM_MODEL` | `opencode-go/deepseek-v4-flash` | Model passed to `opencode run -m` |

## Design notes

- All nutrition, cost, budget and planning math is plain Python (`nutrition.py`, `costing.py`,
  `budget.py`, `planner.py`, `extras.py`) with no Flask or database imports, so it is unit
  tested directly and could sit behind another front end.
- `planner.py` takes a context dict and returns meals; `plans.py` loads and saves them.
- A model is only ever used for recipe text. Its numbers are ignored and recomputed.
- JSON endpoints (`/plan/api/week`, `/recipes/api`, `/pantry/api/foods`) for other clients.

Fonts: Dela Gothic One and Zen Maru Gothic (SIL Open Font License), bundled for offline use.
