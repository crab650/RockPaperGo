import base64

import pytest
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.test import Client
from werkzeug.wrappers import Response

from rockpapergo import create_app
from rockpapergo.db import init_db
from rockpapergo.db import get_db


@pytest.fixture
def app(tmp_path):
    app = create_app({"TESTING": True, "SECRET_KEY": "test", "ADMIN_PASSWORD": "dashboard-test",
                      "DATABASE": str(tmp_path / "test.db")})
    with app.app_context(): init_db()
    return app


def csrf(client):
    client.get("/")
    with client.session_transaction() as s: return s["csrf_token"]


def test_two_players_complete_round(app):
    a, b = app.test_client(), app.test_client()
    r = a.post("/rooms", data={"name": "甲", "csrf_token": csrf(a)})
    code = r.location.rstrip("/").split("/")[-1]
    r = b.post("/join", data={"name": "乙", "code": code, "csrf_token": csrf(b)})
    assert r.status_code == 302
    assert a.post(f"/rooms/{code}/move", data={"move": "rock", "csrf_token": csrf(a)}).status_code == 200
    assert b.post(f"/rooms/{code}/move", data={"move": "scissors", "csrf_token": csrf(b)}).status_code == 200
    # Retrying a move must not create another analytics row.
    assert b.post(f"/rooms/{code}/move", data={"move": "paper", "csrf_token": csrf(b)}).status_code == 200
    state = a.get(f"/rooms/{code}/state").get_json()
    assert state["both"] and state["result"] == "p1"
    with app.app_context():
        rounds = get_db().execute("SELECT * FROM game_rounds").fetchall()
        assert len(rounds) == 1
        assert rounds[0]["player1_move"] == "rock"
        assert rounds[0]["player2_move"] == "scissors"
        assert rounds[0]["result"] == "p1"
        assert rounds[0]["player1_anon_id"] != rounds[0]["player2_anon_id"]
        assert rounds[0]["player1_response_ms"] >= 0
        assert rounds[0]["player2_response_ms"] >= 0
        assert rounds[0]["round_status"] == "completed"
        assert rounds[0]["schema_version"] == 2
        assert rounds[0]["first_mover"] in {"p1", "p2"}
        assert rounds[0]["game_session_id"] != "legacy"
        assert rounds[0]["player1_round_index"] == 1
        assert rounds[0]["player2_round_index"] == 1
    assert a.post(f"/rooms/{code}/next", data={"csrf_token": csrf(a)}).status_code == 200
    assert a.get(f"/rooms/{code}/state").get_json()["score"] == [1, 0, 0]


def test_subpath_urls_keep_mount_prefix(app):
    mounted = DispatcherMiddleware(Response("Not Found", status=404), {"/rockpapergo": app})
    response = Client(mounted).get("/rockpapergo/")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'action="/rockpapergo/rooms"' in html
    assert 'href="/rockpapergo/static/app.css"' in html
    assert "v1.2.0" in html


def test_vietnamese_language_persists_and_keeps_join_code(app):
    client = app.test_client()
    response = client.get("/join?code=ABC123&lang=vi")
    html = response.get_data(as_text=True)
    assert 'lang="vi"' in html
    assert "Vào phòng" in html
    assert 'href="/join?code=ABC123&amp;lang=zh"' in html
    assert "Tạo phòng mới" in client.get("/").get_data(as_text=True)


def test_export_anonymized_rounds(app, tmp_path):
    output = tmp_path / "rounds.csv"
    result = app.test_cli_runner().invoke(args=["export-rounds", "--output", str(output)])
    assert result.exit_code == 0
    assert "Exported 0 rounds" in result.output
    header = output.read_text(encoding="utf-8-sig").splitlines()[0]
    assert "player1_anon_id" in header
    assert "player1_name" not in header


def test_archive_stale_incomplete_round(app):
    a, b = app.test_client(), app.test_client()
    response = a.post("/rooms", data={"name": "甲", "csrf_token": csrf(a)})
    code = response.location.rstrip("/").split("/")[-1]
    b.post("/join", data={"name": "乙", "code": code, "csrf_token": csrf(b)})
    a.post(f"/rooms/{code}/move", data={"move": "paper", "csrf_token": csrf(a)})
    with app.app_context():
        db = get_db()
        db.execute("UPDATE rooms SET updated_at='2000-01-01 00:00:00' WHERE code=?", (code,))
        db.commit()
    result = app.test_cli_runner().invoke(args=["archive-stale-rounds", "--minutes", "30"])
    assert result.exit_code == 0
    assert "Archived 1 stale rounds" in result.output
    with app.app_context():
        archived = get_db().execute("SELECT * FROM abandoned_rounds WHERE room_code=?", (code,)).fetchone()
        assert archived["round_status"] == "abandoned"
        assert archived["player1_move"] == "paper"


def test_analytics_dashboard_requires_password_and_shows_data(app):
    client = app.test_client()
    assert client.get("/analytics").status_code == 401
    token = base64.b64encode(b"admin:dashboard-test").decode()
    response = client.get("/analytics", headers={"Authorization": f"Basic {token}"})
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "數據儀表板" in html
    assert "完成局數" in html
    assert "v1.2.0" in html
