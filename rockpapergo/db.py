import sqlite3

import click
from flask import current_app, g


SCHEMA = """
CREATE TABLE IF NOT EXISTS rooms (
  code TEXT PRIMARY KEY,
  player1_name TEXT NOT NULL,
  player1_token TEXT NOT NULL UNIQUE,
  player2_name TEXT,
  player2_token TEXT UNIQUE,
  round_no INTEGER NOT NULL DEFAULT 1,
  player1_move TEXT,
  player2_move TEXT,
  score1 INTEGER NOT NULL DEFAULT 0,
  score2 INTEGER NOT NULL DEFAULT 0,
  draws INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"], timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.execute("PRAGMA journal_mode = WAL")
        g.db.execute("PRAGMA busy_timeout = 10000")
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(SCHEMA)
    db.commit()


@click.command("init-db")
def init_db_command():
    init_db()
    click.echo("資料庫初始化完成。")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
