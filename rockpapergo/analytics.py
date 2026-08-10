import hmac
from functools import wraps

from flask import Blueprint, Response, abort, current_app, render_template, request

from .db import get_db


bp = Blueprint("analytics", __name__, url_prefix="/analytics")


def admin_required(view):
    @wraps(view)
    def wrapped(**kwargs):
        expected = current_app.config.get("ADMIN_PASSWORD")
        if not expected:
            abort(404)
        auth = request.authorization
        valid = auth and auth.username == "admin" and hmac.compare_digest(auth.password or "", expected)
        if not valid:
            return Response(
                "Analytics login required.", 401,
                {"WWW-Authenticate": 'Basic realm="RockPaperGo Analytics"'},
            )
        return view(**kwargs)

    return wrapped


@bp.get("")
@bp.get("/")
@admin_required
def dashboard():
    db = get_db()
    total_rounds = db.execute("SELECT COUNT(*) FROM game_rounds").fetchone()[0]
    total_sessions = db.execute("SELECT COUNT(DISTINCT game_session_id) FROM game_rounds").fetchone()[0]
    total_players = db.execute("""SELECT COUNT(DISTINCT anon_id) FROM (
        SELECT player1_anon_id AS anon_id FROM game_rounds
        UNION ALL SELECT player2_anon_id FROM game_rounds
    )""").fetchone()[0]
    abandoned = db.execute("SELECT COUNT(*) FROM abandoned_rounds").fetchone()[0]
    move_rows = db.execute("""SELECT move, COUNT(*) AS count FROM (
        SELECT player1_move AS move FROM game_rounds
        UNION ALL SELECT player2_move FROM game_rounds
    ) GROUP BY move""").fetchall()
    moves = {row["move"]: row["count"] for row in move_rows}
    result_rows = db.execute("SELECT result, COUNT(*) AS count FROM game_rounds GROUP BY result").fetchall()
    results = {row["result"]: row["count"] for row in result_rows}
    timing = db.execute("""SELECT
        ROUND(AVG(player1_response_ms + player2_response_ms) / 2.0) AS server_ms,
        ROUND(AVG(CASE WHEN player1_client_response_ms IS NOT NULL AND player2_client_response_ms IS NOT NULL
            THEN (player1_client_response_ms + player2_client_response_ms) / 2.0 END)) AS client_ms
        FROM game_rounds""").fetchone()
    recent = db.execute("""SELECT room_code, round_no, player1_move, player2_move, result,
        first_mover, completed_at FROM game_rounds ORDER BY id DESC LIMIT 50""").fetchall()
    daily = db.execute("""SELECT substr(completed_at, 1, 10) AS day, COUNT(*) AS count
        FROM game_rounds GROUP BY day ORDER BY day DESC LIMIT 14""").fetchall()
    return render_template(
        "analytics.html", total_rounds=total_rounds, total_sessions=total_sessions,
        total_players=total_players, abandoned=abandoned, moves=moves, results=results,
        timing=timing, recent=recent, daily=list(reversed(daily)),
    )
