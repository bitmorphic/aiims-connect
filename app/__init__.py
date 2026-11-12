import os
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask

load_dotenv()


def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.update(
        SECRET_KEY=os.getenv("FLASK_SECRET_KEY", "local-development-key-change-me"),
        DEBUG=os.getenv("FLASK_DEBUG", "0") == "1",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "0") == "1",
        PERMANENT_SESSION_LIFETIME=timedelta(minutes=45),
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
    )

    from .routes import bp
    app.register_blueprint(bp)

    @app.get("/healthz")
    def healthz():
        from .db import ping
        result = ping()
        return {"status": "ok", "database": result["db_name"]}, 200

    return app
