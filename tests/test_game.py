import pytest
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.test import Client
from werkzeug.wrappers import Response

from rockpapergo import create_app
from rockpapergo.db import init_db


@pytest.fixture
def app(tmp_path):
    app = create_app({"TESTING": True, "SECRET_KEY": "test", "DATABASE": str(tmp_path / "test.db")})
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
    state = a.get(f"/rooms/{code}/state").get_json()
    assert state["both"] and state["result"] == "p1"
    assert a.post(f"/rooms/{code}/next", data={"csrf_token": csrf(a)}).status_code == 200
    assert a.get(f"/rooms/{code}/state").get_json()["score"] == [1, 0, 0]


def test_subpath_urls_keep_mount_prefix(app):
    mounted = DispatcherMiddleware(Response("Not Found", status=404), {"/rockpapergo": app})
    response = Client(mounted).get("/rockpapergo/")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'action="/rockpapergo/rooms"' in html
    assert 'href="/rockpapergo/static/app.css"' in html


def test_vietnamese_language_persists_and_keeps_join_code(app):
    client = app.test_client()
    response = client.get("/join?code=ABC123&lang=vi")
    html = response.get_data(as_text=True)
    assert 'lang="vi"' in html
    assert "Vào phòng" in html
    assert 'href="/join?code=ABC123&amp;lang=zh"' in html
    assert "Tạo phòng mới" in client.get("/").get_data(as_text=True)
