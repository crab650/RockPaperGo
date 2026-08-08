import os
from datetime import datetime, timedelta

import caldav
import sys

from icalendar import Calendar
from flask import redirect
from flask import Flask, jsonify, request, send_from_directory
from pathlib import Path
from werkzeug.middleware.dispatcher import DispatcherMiddleware

app = Flask(__name__)





ICLOUD_USER = "crab650@icloud.com"
ICLOUD_PASS = "fitn-jixx-zpum-cowe"
CALDAV_URL = "https://caldav.icloud.com/"



# ===== 原 ERP Blueprint =====
sys.path.append("/home/mamahow/ai_server/erp_demo")
from erp_app import erp_bp

# ===== 咖啡店問卷 Blueprint =====
sys.path.append("/home/mamahow/ai_server")
from cafe_survey.survey_bp import cafe_survey_bp

# ===== HoaNguVN mounted application =====
# Deployment path: /home/mamahow/ai_server/hoanguvn
if "/home/mamahow/ai_server" not in sys.path:
    sys.path.insert(0, "/home/mamahow/ai_server")

from hoanguvn.app import app as hoanguvn_app


# ===== GlucoFlow mounted application =====
# Deployment path: /home/mamahow/ai_server/GlucoFlow
GLUCOFLOW_PATH = "/home/mamahow/ai_server/GlucoFlow"
if GLUCOFLOW_PATH not in sys.path:
    sys.path.insert(0, GLUCOFLOW_PATH)

# GLUCOFLOW_SECRET_KEY must be set by the outer PythonAnywhere WSGI file
# before this module is imported.  Keeping it out of source control prevents
# every mounted application from sharing a public development secret.
os.environ.setdefault("GLUCOFLOW_ENV", "production")
os.environ.setdefault(
    "GLUCOFLOW_DATABASE",
    "/home/mamahow/ai_server/GlucoFlow/instance/glucoflow.sqlite3",
)
os.environ.setdefault("GLUCOFLOW_SECURE_COOKIE", "1")

from gluc_flow import create_app as create_glucoflow_app

glucoflow_app = create_glucoflow_app()


# ===== RockPaperGo mounted application =====
# Deployment path: /home/mamahow/ai_server/rockpapergo
ROCKPAPERGO_PATH = "/home/mamahow/ai_server/rockpapergo"
if ROCKPAPERGO_PATH not in sys.path:
    sys.path.insert(0, ROCKPAPERGO_PATH)

# ROCKPAPERGO_SECRET_KEY must be set by the outer PythonAnywhere WSGI file.
# Keep the database in the project's instance directory. Preserve this
# directory when replacing application code during deployment.
os.environ.setdefault(
    "ROCKPAPERGO_DATA_DIR",
    "/home/mamahow/ai_server/rockpapergo/instance",
)
os.environ.setdefault("ROCKPAPERGO_COOKIE_SECURE", "1")

from rockpapergo import create_app as create_rockpapergo_app

rockpapergo_app = create_rockpapergo_app()


# ===== 原本 AI Frontend =====
FRONTEND_DIR = Path("/home/mamahow/ai_server/frontend")
SAYIT_DIR = Path("/home/mamahow/ai_server/sayit")



# ===== iCloud 行事曆功能 =====
def get_week_calendar_summary():
    if not ICLOUD_USER or not ICLOUD_PASS:
        return "尚未設定 ICLOUD_USER 或 ICLOUD_PASS 環境變數。"

    client = caldav.DAVClient(
        url=CALDAV_URL,
        username=ICLOUD_USER,
        password=ICLOUD_PASS
    )

    principal = client.principal()
    calendars = principal.calendars()

    week_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = week_start + timedelta(days=7)

    result = []

    for calendar in calendars:
        events = calendar.date_search(
            start=week_start,
            end=week_end,
            expand=True
        )

        for event in events:
            cal = Calendar.from_ical(event.data)

            for component in cal.walk():
                if component.name == "VEVENT":
                    title = str(component.get("summary", "無標題"))
                    start = component.get("dtstart").dt
                    end = component.get("dtend").dt if component.get("dtend") else None

                    result.append({
                        "calendar": calendar.name,
                        "title": title,
                        "start": start,
                        "end": end
                    })

    result.sort(key=lambda x: str(x["start"]))

    if not result:
        return "未來 7 天沒有 iCloud 行事曆事件。"

    lines = [f"未來 7 天共有 {len(result)} 個行程："]

    for e in result:
        start = e["start"]

        if hasattr(start, "strftime"):
            time_text = start.strftime("%m月%d日 %H:%M")
        else:
            time_text = str(start)

        lines.append(f"{time_text}，{e['title']}。")

    return "\n".join(lines)


# ===== API 區 =====
@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json(silent=True) or {}
    question = data.get("question", "")

    if "行程" in question or "日曆" in question or "calendar" in question.lower():
        answer = get_week_calendar_summary()
    else:
        answer = f"我收到你的問題：{question}"

    return jsonify({
        "answer": answer,
        "debug": str(data)
    })


# ===== 家庭入口頁 =====
@app.route("/home")
def home():
    return """
    <h1>🏠 AI 家庭入口</h1>
    <p>AI-MAMAHOW 家庭智慧平台</p>
    <p><a href="/">回主網站</a></p>
    """



app.register_blueprint(erp_bp, url_prefix="/ERP")
app.register_blueprint(cafe_survey_bp, url_prefix="/survey")

@app.route("/assets/<path:filename>")
def assets(filename):
    return send_from_directory(FRONTEND_DIR / "assets", filename)


@app.route("/sayit")
def sayit_index():
    return send_from_directory(SAYIT_DIR, "index.html")

@app.route("/sayit/<path:filename>")
def sayit_static(filename):
    return send_from_directory(SAYIT_DIR, filename)

@app.route("/")
def index():
    return redirect("/login")


@app.route("/<path:path>")
def ai_frontend(path="index.html"):
    file_path = FRONTEND_DIR / path

    if file_path.exists() and file_path.is_file():
        return send_from_directory(FRONTEND_DIR, path)

    return send_from_directory(FRONTEND_DIR, "index.html")


# PythonAnywhere WSGI must import `application` from this module.
application = DispatcherMiddleware(
    app,
    {
        "/hoanguvn": hoanguvn_app,
        "/glucoflow": glucoflow_app,
        "/rockpapergo": rockpapergo_app,
    },
)


if __name__ == "__main__":
    app.run()
