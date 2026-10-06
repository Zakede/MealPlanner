# Meal Planner

A self-hosted meal planner for cutting weight on a budget. It plans high-protein,
low-calorie meals from what's already in the fridge, keeps the week inside a yen
budget, and leaves room for snacks, cravings and eating out.

Built with Flask + SQLite, with a mobile-first web UI meant to be opened on a phone
over the home network.

## Features

- Calorie and macro targets from body stats (Mifflin-St Jeor + activity level), with a
  minimum calorie floor and a 0.75 kg/week pace cap
- Weekly food budget in JPY with reserved eating-out slots

## Running it

```bash
pip install -r requirements.txt
python run.py            # serves on http://0.0.0.0:5000
python -m pytest         # run the tests
```

Configuration is through environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `MEALPLANNER_DB` | `instance/mealplanner.db` | SQLite file |
| `MEALPLANNER_SECRET` | dev value | Flask secret key, change it on a server |
| `MEALPLANNER_HOST` / `MEALPLANNER_PORT` | `0.0.0.0` / `5000` | Bind address |

## Design notes

All nutrition, cost and budget math lives in plain Python modules
(`nutrition.py`, and later `costing.py`, `budget.py`) with unit tests, separate from the Flask views.
