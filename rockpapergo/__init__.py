import os
from pathlib import Path

from flask import Flask


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
    )
    if config:
        app.config.update(config)

    from . import db
    db.init_app(app)

    from .game import bp
    app.register_blueprint(bp)
    return app
