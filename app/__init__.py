import os

from flask import Flask

from app.config import CONFIG_BY_NAME
from app.extensions import db, jwt, migrate


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__)

    resolved_config_name: str = config_name or os.environ.get("FLASK_ENV", "development")
    app.config.from_object(CONFIG_BY_NAME[resolved_config_name])

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    from app import models  # noqa: F401  (garante que os models sejam registrados no metadata)
    from app.api.errors import register_error_handlers
    from app.api.v1 import register_v1_blueprints

    register_error_handlers(app)
    register_v1_blueprints(app)

    return app
