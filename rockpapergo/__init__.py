import os
from pathlib import Path

from flask import Flask


__version__ = "1.2.0"


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    data_dir = Path(os.environ.get("ROCKPAPERGO_DATA_DIR", app.instance_path))
    data_dir.mkdir(parents=True, exist_ok=True)

    secret = os.environ.get("ROCKPAPERGO_SECRET_KEY")
    if not secret and not config:
        raise RuntimeError("正式環境必須設定 ROCKPAPERGO_SECRET_KEY")

    app.config.from_mapping(
        SECRET_KEY=secret or "test-only",
        DATABASE=str(data_dir / "rockpapergo.db"),
        SESSION_COOKIE_NAME="rockpapergo_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("ROCKPAPERGO_COOKIE_SECURE") == "1",
        APP_VERSION=os.environ.get("ROCKPAPERGO_APP_VERSION", __version__),
        CONSENT_VERSION="2026-08-10",
        ANALYTICS_SCHEMA_VERSION=2,
        ADMIN_PASSWORD=os.environ.get("ROCKPAPERGO_ADMIN_PASSWORD"),
    )
    if config:
        app.config.update(config)

    @app.context_processor
    def inject_app_version():
        return {"app_version": app.config["APP_VERSION"]}

    from . import db
    db.init_app(app)
    with app.app_context():
        db.init_db()

    from .game import bp
    app.register_blueprint(bp)
    from .analytics import bp as analytics_bp
    app.register_blueprint(analytics_bp)
    return app
