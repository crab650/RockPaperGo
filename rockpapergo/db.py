import csv
import sqlite3
from pathlib import Path

import click
from flask import current_app, g
from flask.cli import with_appcontext


SCHEMA = """
CREATE TABLE IF NOT EXISTS rooms (
  code TEXT PRIMARY KEY,
  game_session_id TEXT NOT NULL,
  player1_name TEXT NOT NULL,
  player1_token TEXT NOT NULL UNIQUE,
  player1_anon_id TEXT NOT NULL,
  player1_lang TEXT NOT NULL DEFAULT 'zh',
  player2_name TEXT,
  player2_token TEXT UNIQUE,
  player2_anon_id TEXT,
  player2_lang TEXT,
  round_no INTEGER NOT NULL DEFAULT 1,
  player1_move TEXT,
  player1_moved_at TEXT,
  player1_client_response_ms INTEGER,
  player2_move TEXT,
  player2_moved_at TEXT,
  player2_client_response_ms INTEGER,
  score1 INTEGER NOT NULL DEFAULT 0,
  score2 INTEGER NOT NULL DEFAULT 0,
  draws INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS game_rounds (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  room_code TEXT NOT NULL,
  round_no INTEGER NOT NULL,
  player1_anon_id TEXT NOT NULL,
  player2_anon_id TEXT NOT NULL,
  player1_lang TEXT NOT NULL,
  player2_lang TEXT NOT NULL,
  player1_move TEXT NOT NULL CHECK (player1_move IN ('rock', 'paper', 'scissors')),
  player2_move TEXT NOT NULL CHECK (player2_move IN ('rock', 'paper', 'scissors')),
  result TEXT NOT NULL CHECK (result IN ('draw', 'p1', 'p2')),
  round_started_at TEXT NOT NULL,
  player1_moved_at TEXT NOT NULL,
  player2_moved_at TEXT NOT NULL,
  completed_at TEXT NOT NULL,
  player1_response_ms INTEGER NOT NULL,
  player2_response_ms INTEGER NOT NULL,
  player1_client_response_ms INTEGER,
  player2_client_response_ms INTEGER,
  first_mover TEXT NOT NULL,
  previous_result TEXT,
  player1_round_index INTEGER NOT NULL,
  player2_round_index INTEGER NOT NULL,
  consent_version TEXT NOT NULL DEFAULT 'unknown',
  schema_version INTEGER NOT NULL DEFAULT 1,
  app_version TEXT NOT NULL DEFAULT 'unknown',
  game_session_id TEXT NOT NULL DEFAULT 'legacy',
  round_status TEXT NOT NULL DEFAULT 'completed',
  UNIQUE(room_code, round_no)
);

CREATE TABLE IF NOT EXISTS abandoned_rounds (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  room_code TEXT NOT NULL,
  round_no INTEGER NOT NULL,
  game_session_id TEXT NOT NULL,
  player1_anon_id TEXT NOT NULL,
  player2_anon_id TEXT,
  player1_move TEXT,
  player2_move TEXT,
  round_started_at TEXT NOT NULL,
  abandoned_at TEXT NOT NULL,
  round_status TEXT NOT NULL DEFAULT 'abandoned',
  consent_version TEXT NOT NULL,
  schema_version INTEGER NOT NULL,
  app_version TEXT NOT NULL,
  UNIQUE(room_code, round_no)
);

CREATE INDEX IF NOT EXISTS idx_game_rounds_players
  ON game_rounds(player1_anon_id, player2_anon_id);
CREATE INDEX IF NOT EXISTS idx_game_rounds_completed
  ON game_rounds(completed_at);
"""

ROOM_MIGRATIONS = {
    "game_session_id": "TEXT NOT NULL DEFAULT 'legacy'",
    "player1_anon_id": "TEXT NOT NULL DEFAULT 'legacy'",
    "player1_lang": "TEXT NOT NULL DEFAULT 'zh'",
    "player2_anon_id": "TEXT",
    "player2_lang": "TEXT",
    "player1_moved_at": "TEXT",
    "player2_moved_at": "TEXT",
    "player1_client_response_ms": "INTEGER",
    "player2_client_response_ms": "INTEGER",
    "round_started_at": "TEXT NOT NULL DEFAULT '1970-01-01T00:00:00+00:00'",
}

ROUND_MIGRATIONS = {
    "player1_client_response_ms": "INTEGER",
    "player2_client_response_ms": "INTEGER",
    "first_mover": "TEXT NOT NULL DEFAULT 'unknown'",
    "previous_result": "TEXT",
    "player1_round_index": "INTEGER NOT NULL DEFAULT 1",
    "player2_round_index": "INTEGER NOT NULL DEFAULT 1",
    "consent_version": "TEXT NOT NULL DEFAULT 'unknown'",
    "schema_version": "INTEGER NOT NULL DEFAULT 1",
    "app_version": "TEXT NOT NULL DEFAULT 'unknown'",
    "game_session_id": "TEXT NOT NULL DEFAULT 'legacy'",
    "round_status": "TEXT NOT NULL DEFAULT 'completed'",
}


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
    columns = {row[1] for row in db.execute("PRAGMA table_info(rooms)")}
    for name, definition in ROOM_MIGRATIONS.items():
        if name not in columns:
            db.execute(f"ALTER TABLE rooms ADD COLUMN {name} {definition}")
    round_columns = {row[1] for row in db.execute("PRAGMA table_info(game_rounds)")}
    for name, definition in ROUND_MIGRATIONS.items():
        if name not in round_columns:
            db.execute(f"ALTER TABLE game_rounds ADD COLUMN {name} {definition}")
    db.commit()


@click.command("init-db")
def init_db_command():
    init_db()
    click.echo("Database initialized.")


@click.command("export-rounds")
@click.option("--output", type=click.Path(dir_okay=False, path_type=Path), default=Path("game_rounds.csv"))
@with_appcontext
def export_rounds_command(output):
    """Export anonymized completed rounds as UTF-8 CSV."""
    rows = get_db().execute("SELECT * FROM game_rounds ORDER BY id").fetchall()
    columns = [item[0] for item in get_db().execute("SELECT * FROM game_rounds LIMIT 0").description]
    with output.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(columns)
        writer.writerows([tuple(row) for row in rows])
    click.echo(f"Exported {len(rows)} rounds to {output}")


@click.command("export-abandoned")
@click.option("--output", type=click.Path(dir_okay=False, path_type=Path), default=Path("abandoned_rounds.csv"))
@with_appcontext
def export_abandoned_command(output):
    """Export anonymized abandoned rounds as UTF-8 CSV."""
    rows = get_db().execute("SELECT * FROM abandoned_rounds ORDER BY id").fetchall()
    columns = [item[0] for item in get_db().execute("SELECT * FROM abandoned_rounds LIMIT 0").description]
    with output.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(columns)
        writer.writerows([tuple(row) for row in rows])
    click.echo(f"Exported {len(rows)} abandoned rounds to {output}")


@click.command("archive-stale-rounds")
@click.option("--minutes", type=click.IntRange(min=1), default=30, show_default=True)
@with_appcontext
def archive_stale_rounds_command(minutes):
    """Archive incomplete rounds that have been inactive for a while."""
    db = get_db()
    config = current_app.config
    cursor = db.execute("""INSERT OR IGNORE INTO abandoned_rounds(
        room_code, round_no, game_session_id, player1_anon_id, player2_anon_id,
        player1_move, player2_move, round_started_at, abandoned_at,
        consent_version, schema_version, app_version
    ) SELECT code, round_no, game_session_id, player1_anon_id, player2_anon_id,
        player1_move, player2_move, round_started_at, CURRENT_TIMESTAMP, ?, ?, ?
      FROM rooms
      WHERE (player1_move IS NOT NULL OR player2_move IS NOT NULL)
        AND NOT (player1_move IS NOT NULL AND player2_move IS NOT NULL)
        AND updated_at <= datetime('now', ?)
    """, (config["CONSENT_VERSION"], config["ANALYTICS_SCHEMA_VERSION"],
           config["APP_VERSION"], f"-{minutes} minutes"))
    db.commit()
    click.echo(f"Archived {cursor.rowcount} stale rounds.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(export_rounds_command)
    app.cli.add_command(export_abandoned_command)
    app.cli.add_command(archive_stale_rounds_command)
