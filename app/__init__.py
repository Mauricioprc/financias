import os
from pathlib import Path

from flask import Flask, send_from_directory

from app.config import CONFIG_BY_NAME
from app.extensions import db, jwt, limiter, migrate

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = PROJECT_ROOT / "static"


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="")

    resolved_config_name: str = config_name or os.environ.get("FLASK_ENV", "development")
    app.config.from_object(CONFIG_BY_NAME[resolved_config_name])

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    limiter.init_app(app)

    from app import models  # noqa: F401  (garante que os models sejam registrados no metadata)
    from app.api.errors import register_error_handlers
    from app.api.v1 import register_v1_blueprints
    from app.cli import register_cli
    from bot.webhook import bp as bot_webhook_bp

    register_error_handlers(app)
    register_v1_blueprints(app)
    register_cli(app)
    app.register_blueprint(bot_webhook_bp, url_prefix="/bot")

    @app.route("/")
    def serve_dashboard():
        return send_from_directory(app.static_folder, "index.html")

    return app
