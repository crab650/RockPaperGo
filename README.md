# 猜拳 GO

目前版本：`1.2.0`

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

## 匿名對局資料

每局在兩位玩家出拳後會立即寫入 `game_rounds`，包含匿名玩家代碼、遊戲場次、雙方出拳、結果、語言、伺服器與瀏覽器反應時間、先出拳者、上一局結果、玩家累積局次，以及同意／資料格式／程式版本。分析資料不包含暱稱或 IP，且同一房間局數只能寫入一次。

匯出 UTF-8 CSV：

```powershell
.venv\Scripts\flask --app wsgi export-rounds --output game_rounds.csv
```

將超過 30 分鐘未完成的局封存後，可另外匯出流失資料：

```powershell
.venv\Scripts\flask --app wsgi archive-stale-rounds --minutes 30
.venv\Scripts\flask --app wsgi export-abandoned --output abandoned_rounds.csv
```

正式運行時可用排程每 30 分鐘或每小時執行 `archive-stale-rounds`。

## 數據儀表板

設定管理密碼後開啟 `/analytics`，瀏覽器會要求輸入帳號密碼：

- 帳號：`admin`
- 密碼：環境變數 `ROCKPAPERGO_ADMIN_PASSWORD` 的值

儀表板會顯示完成局數、匿名玩家、遊戲場次、中止局數、出拳與勝負分布、平均反應時間、每日局數及最近對局。本機批次檔預設使用 `12345678`，公開部署時務必透過環境變數設定不同的高強度密碼。

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
os.environ["ROCKPAPERGO_ADMIN_PASSWORD"] = "請設定高強度管理密碼"
from rockpapergo import create_app

application = DispatcherMiddleware(Response("Not Found", status=404), {
    "/rockpapergo": create_app(),
})
```

設定 virtualenv、Reload 後即可由 `/rockpapergo/` 使用。請勿將正式密鑰提交至 Git。
