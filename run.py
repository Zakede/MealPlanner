import os

from mealplanner import create_app

app = create_app()

if __name__ == "__main__":
    # LAN only: bind to 0.0.0.0 so phones on the home network can reach it.
    host = os.environ.get("MEALPLANNER_HOST", "0.0.0.0")
    port = int(os.environ.get("MEALPLANNER_PORT", "5000"))
    app.run(host=host, port=port, debug=os.environ.get("MEALPLANNER_DEBUG") == "1")
