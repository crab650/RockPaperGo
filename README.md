# 猜拳 GO

兩位玩家用手機瀏覽器加入同一房間的即時猜拳遊戲。相容 PythonAnywhere 子路徑掛載。

Windows 可直接雙擊 `啟動猜拳.bat`，程式會自動建立環境、安裝套件、初始化資料庫並啟動網站。

## 本機執行

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
$env:ROCKPAPERGO_SECRET_KEY = (python -c "import secrets; print(secrets.token_hex(32))")
.venv\Scripts\flask --app wsgi init-db
.venv\Scripts\flask --app wsgi run --host 0.0.0.0
```

同一個 Wi-Fi 下，另一支手機可用電腦的區網 IP 與 `:5000` 開啟網站。

## PythonAnywhere

建立共用資料目錄並設定三個 `.env.example` 中的環境變數，執行 `flask --app wsgi init-db`。網站 WSGI 設定可掛載：

```python
import os, sys
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.wrappers import Response

sys.path.insert(0, "/home/帳號/apps/rockpapergo/current")
os.environ["ROCKPAPERGO_SECRET_KEY"] = "正式環境隨機密鑰"
os.environ["ROCKPAPERGO_DATA_DIR"] = "/home/帳號/apps/rockpapergo/shared/data"
os.environ["ROCKPAPERGO_COOKIE_SECURE"] = "1"
from rockpapergo import create_app

application = DispatcherMiddleware(Response("Not Found", status=404), {
    "/rockpapergo": create_app(),
})
```

設定 virtualenv、Reload 後即可由 `/rockpapergo/` 使用。請勿將正式密鑰提交至 Git。
