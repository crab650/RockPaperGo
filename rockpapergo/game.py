import hmac
import secrets
import string
from datetime import datetime, timezone

from flask import Blueprint, abort, current_app, jsonify, redirect, render_template, request, session, url_for

from .db import get_db

bp = Blueprint("game", __name__)
MOVES = {"rock", "paper", "scissors"}
BEATS = {"rock": "scissors", "scissors": "paper", "paper": "rock"}
LANGUAGES = {"zh": "中文", "vi": "Tiếng Việt"}
TRANSLATIONS = {
    "zh": {
        "site_name": "猜拳 GO", "tagline": "兩支手機，一決勝負！", "your_name": "你的暱稱",
        "name_example": "例如：小明", "create_room": "建立新房間", "or": "或", "room_code": "房間代碼",
        "join_room": "加入房間", "room_number": "房號", "enter_game": "進入對戰", "back_home": "返回首頁",
        "round": "第 {number} 局", "waiting": "等待對手加入…", "share_link": "把這個連結傳給朋友：",
        "copy_invite": "複製邀請連結", "draws": "平手", "choose_move": "請出拳！", "rock": "石頭",
        "paper": "布", "scissors": "剪刀", "next_round": "再來一局", "room_title": "房間 {code}｜猜拳 GO",
        "name_required": "請輸入你的暱稱。", "room_not_found": "找不到這個房間。",
        "room_full": "這個房間已經有兩位玩家。", "room_just_filled": "剛剛已有其他玩家加入。",
        "submitted": "已出拳，等待對手…", "draw_result": "平手！", "you_win": "你贏了！",
        "opponent_wins": "對手獲勝！", "played": "{name}出{move}", "connection_lost": "連線中斷，正在重試…",
        "copied": "已複製！", "language": "語言",
        "data_notice": "開始遊戲即表示你同意我們匿名記錄出拳、勝負與反應時間，用於統計分析；不會記錄暱稱或 IP。",
    },
    "vi": {
        "site_name": "Oẳn tù tì GO", "tagline": "Hai điện thoại, một trận quyết đấu!", "your_name": "Biệt danh của bạn",
        "name_example": "Ví dụ: Minh", "create_room": "Tạo phòng mới", "or": "hoặc", "room_code": "Mã phòng",
        "join_room": "Vào phòng", "room_number": "Phòng", "enter_game": "Bắt đầu thi đấu", "back_home": "Về trang chủ",
        "round": "Ván {number}", "waiting": "Đang chờ đối thủ…", "share_link": "Gửi liên kết này cho bạn bè:",
        "copy_invite": "Sao chép liên kết mời", "draws": "Hòa", "choose_move": "Hãy ra tay!", "rock": "Búa",
        "paper": "Bao", "scissors": "Kéo", "next_round": "Chơi ván nữa", "room_title": "Phòng {code}｜Oẳn tù tì GO",
        "name_required": "Vui lòng nhập biệt danh.", "room_not_found": "Không tìm thấy phòng này.",
        "room_full": "Phòng này đã có đủ hai người chơi.", "room_just_filled": "Một người chơi khác vừa vào phòng.",
        "submitted": "Đã ra tay, đang chờ đối thủ…", "draw_result": "Hòa!", "you_win": "Bạn thắng!",
        "opponent_wins": "Đối thủ thắng!", "played": "{name} ra {move}", "connection_lost": "Mất kết nối, đang thử lại…",
        "copied": "Đã sao chép!", "language": "Ngôn ngữ",
        "data_notice": "Khi bắt đầu, bạn đồng ý cho chúng tôi ghi ẩn danh lựa chọn, kết quả và thời gian phản hồi để phân tích; biệt danh và IP không được lưu trong dữ liệu phân tích.",
    },
}


@bp.before_app_request
def select_language():
    if "anon_player_id" not in session:
        session["anon_player_id"] = secrets.token_urlsafe(18)
    requested = request.args.get("lang")
    if requested in LANGUAGES:
        session["lang"] = requested


@bp.app_context_processor
def inject_i18n():
    lang = session.get("lang", "zh")

    def translate(key, **values):
        return TRANSLATIONS[lang].get(key, key).format(**values)

    def language_url(code):
        values = request.args.to_dict()
        values.update(request.view_args or {})
        values["lang"] = code
        return url_for(request.endpoint, **values)

    return {"t": translate, "lang": lang, "languages": LANGUAGES, "language_url": language_url}


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(24)
    return session["csrf_token"]


@bp.app_context_processor
def inject_csrf():
    return {"csrf_token": csrf_token}


def require_csrf():
    supplied = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token", "")
    if not hmac.compare_digest(supplied, session.get("csrf_token", "")):
        abort(400, "CSRF 驗證失敗")


def clean_name(value):
    return " ".join(value.strip().split())[:20]


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def response_ms(started_at, moved_at):
    start = datetime.fromisoformat(started_at)
    moved = datetime.fromisoformat(moved_at)
    return max(0, round((moved - start).total_seconds() * 1000))


def clean_client_response_ms(value):
    try:
        milliseconds = int(value)
    except (TypeError, ValueError):
        return None
    return milliseconds if 0 <= milliseconds <= 3_600_000 else None


def room_for_player(code):
    room = get_db().execute("SELECT * FROM rooms WHERE code = ?", (code,)).fetchone()
    if not room:
        abort(404)
    token = session.get("player_token")
    if token == room["player1_token"]:
        return room, 1
    if token and token == room["player2_token"]:
        return room, 2
    abort(403)


@bp.get("/")
def index():
    return render_template("index.html")


@bp.post("/rooms")
def create_room():
    require_csrf()
    name = clean_name(request.form.get("name", ""))
    if not name:
        return render_template("index.html", error_key="name_required"), 400
    db = get_db()
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(10):
        code = "".join(secrets.choice(alphabet) for _ in range(6))
        if not db.execute("SELECT 1 FROM rooms WHERE code = ?", (code,)).fetchone():
            break
    token = secrets.token_urlsafe(24)
    game_session_id = secrets.token_urlsafe(18)
    db.execute("""INSERT INTO rooms(
        code, game_session_id, player1_name, player1_token, player1_anon_id, player1_lang,
        round_started_at) VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (code, game_session_id, name, token, session["anon_player_id"],
         session.get("lang", "zh"), now_iso()))
    db.commit()
    session["player_token"] = token
    return redirect(url_for("game.room", code=code))


@bp.route("/join", methods=["GET", "POST"])
def join():
    code = request.values.get("code", "").strip().upper()[:6]
    if request.method == "GET":
        return render_template("join.html", code=code)
    require_csrf()
    name = clean_name(request.form.get("name", ""))
    room = get_db().execute("SELECT * FROM rooms WHERE code = ?", (code,)).fetchone()
    if not room:
        return render_template("join.html", code=code, error_key="room_not_found"), 404
    if not name:
        return render_template("join.html", code=code, error_key="name_required"), 400
    if room["player2_token"]:
        return render_template("join.html", code=code, error_key="room_full"), 409
    token = secrets.token_urlsafe(24)
    db = get_db()
    changed = db.execute(
        """UPDATE rooms SET player2_name=?, player2_token=?, player2_anon_id=?, player2_lang=?,
        round_started_at=?, updated_at=CURRENT_TIMESTAMP WHERE code=? AND player2_token IS NULL""",
        (name, token, session["anon_player_id"], session.get("lang", "zh"), now_iso(), code),
    ).rowcount
    db.commit()
    if not changed:
        return render_template("join.html", code=code, error_key="room_just_filled"), 409
    session["player_token"] = token
    return redirect(url_for("game.room", code=code))


@bp.get("/rooms/<code>")
def room(code):
    room, player = room_for_player(code.upper())
    return render_template("room.html", room=room, player=player)


@bp.get("/rooms/<code>/state")
def state(code):
    room, player = room_for_player(code.upper())
    mine = room[f"player{player}_move"]
    both = bool(room["player1_move"] and room["player2_move"])
    result = None
    if both:
        a, b = room["player1_move"], room["player2_move"]
        result = "draw" if a == b else ("p1" if BEATS[a] == b else "p2")
    return jsonify({
        "round": room["round_no"], "joined": bool(room["player2_token"]), "submitted": bool(mine),
        "both": both, "moves": [room["player1_move"], room["player2_move"]] if both else [None, None],
        "result": result, "score": [room["score1"], room["score2"], room["draws"]],
        "names": [room["player1_name"], room["player2_name"]], "player": player,
        "app_version": current_app.config["APP_VERSION"],
    })


@bp.post("/rooms/<code>/move")
def move(code):
    require_csrf()
    room, player = room_for_player(code.upper())
    choice = request.form.get("move")
    if choice not in MOVES or not room["player2_token"]:
        abort(400)
    column = f"player{player}_move"
    time_column = f"player{player}_moved_at"
    client_time_column = f"player{player}_client_response_ms"
    moved_at = now_iso()
    client_response = clean_client_response_ms(request.form.get("client_response_ms"))
    db = get_db()
    changed = db.execute(
        f"UPDATE rooms SET {column}=?, {time_column}=?, {client_time_column}=?, updated_at=CURRENT_TIMESTAMP "
        f"WHERE code=? AND {column} IS NULL", (choice, moved_at, client_response, room["code"])
    ).rowcount
    completed = db.execute("SELECT * FROM rooms WHERE code=?", (room["code"],)).fetchone()
    if changed and completed["player1_move"] and completed["player2_move"]:
        a, b = completed["player1_move"], completed["player2_move"]
        result = "draw" if a == b else ("p1" if BEATS[a] == b else "p2")
        finished_at = max(completed["player1_moved_at"], completed["player2_moved_at"])
        first_mover = "p1" if completed["player1_moved_at"] < completed["player2_moved_at"] else "p2"
        previous = db.execute(
            "SELECT result FROM game_rounds WHERE room_code=? AND round_no<? ORDER BY round_no DESC LIMIT 1",
            (completed["code"], completed["round_no"]),
        ).fetchone()
        indexes = []
        for anon_id in (completed["player1_anon_id"], completed["player2_anon_id"]):
            count = db.execute("""SELECT COUNT(*) FROM game_rounds
                WHERE player1_anon_id=? OR player2_anon_id=?""", (anon_id, anon_id)).fetchone()[0]
            indexes.append(count + 1)
        db.execute("""INSERT OR IGNORE INTO game_rounds(
            room_code, round_no, player1_anon_id, player2_anon_id, player1_lang, player2_lang,
            player1_move, player2_move, result, round_started_at, player1_moved_at,
            player2_moved_at, completed_at, player1_response_ms, player2_response_ms,
            player1_client_response_ms, player2_client_response_ms, first_mover, previous_result,
            player1_round_index, player2_round_index, consent_version, schema_version,
            app_version, game_session_id, round_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (
            completed["code"], completed["round_no"], completed["player1_anon_id"],
            completed["player2_anon_id"], completed["player1_lang"], completed["player2_lang"],
            a, b, result, completed["round_started_at"], completed["player1_moved_at"],
            completed["player2_moved_at"], finished_at,
            response_ms(completed["round_started_at"], completed["player1_moved_at"]),
            response_ms(completed["round_started_at"], completed["player2_moved_at"]),
            completed["player1_client_response_ms"], completed["player2_client_response_ms"],
            first_mover, previous["result"] if previous else None, indexes[0], indexes[1],
            current_app.config["CONSENT_VERSION"], current_app.config["ANALYTICS_SCHEMA_VERSION"],
            current_app.config["APP_VERSION"], completed["game_session_id"], "completed",
        ))
    db.commit()
    return jsonify(ok=True)


@bp.post("/rooms/<code>/next")
def next_round(code):
    require_csrf()
    room, _player = room_for_player(code.upper())
    if not room["player1_move"] or not room["player2_move"]:
        abort(409)
    a, b = room["player1_move"], room["player2_move"]
    score1 = 1 if a != b and BEATS[a] == b else 0
    score2 = 1 if a != b and BEATS[b] == a else 0
    draw = 1 if a == b else 0
    db = get_db()
    db.execute("""UPDATE rooms SET round_no=round_no+1, player1_move=NULL, player2_move=NULL,
        player1_moved_at=NULL, player2_moved_at=NULL, round_started_at=?,
        player1_client_response_ms=NULL, player2_client_response_ms=NULL,
        score1=score1+?, score2=score2+?, draws=draws+?, updated_at=CURRENT_TIMESTAMP
        WHERE code=? AND player1_move IS NOT NULL AND player2_move IS NOT NULL""",
        (now_iso(), score1, score2, draw, room["code"]))
    db.commit()
    return jsonify(ok=True)
