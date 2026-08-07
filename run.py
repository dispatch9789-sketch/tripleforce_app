"""Triple Force Logistic LLC — Application entry point.

Run locally:
    python run.py

Run on network (accessible from iPhone):
    python run.py
    (HOST=0.0.0.0 is set in .env by default)

Then open from iPhone:
    http://<YOUR-WINDOWS-IP>:5000
"""
import os
from app import create_app

app = create_app()

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1").lower() in ("true", "1", "yes")
    app.run(host=host, port=port, debug=debug)
