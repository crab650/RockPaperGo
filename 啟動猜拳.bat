@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Rock Paper Go - Flask Server

echo [1/4] Checking Python...
where py.exe >nul 2>nul
if not errorlevel 1 goto use_py

where python.exe >nul 2>nul
if errorlevel 1 goto no_python
set "PYTHON_CMD=python.exe"
goto python_ready

:use_py
set "PYTHON_CMD=py.exe"

:python_ready
if exist ".venv\Scripts\python.exe" goto venv_ready
echo       Creating virtual environment...
%PYTHON_CMD% -m venv ".venv"
if errorlevel 1 goto failed

:venv_ready
set "VENV_PY=%CD%\.venv\Scripts\python.exe"
if not exist "%VENV_PY%" goto failed

echo [2/4] Checking dependencies...
"%VENV_PY%" -c "import flask" >nul 2>nul
if not errorlevel 1 goto packages_ready
echo       Installing dependencies...
"%VENV_PY%" -m pip install -r "requirements.txt"
if errorlevel 1 goto failed

:packages_ready
set "ROCKPAPERGO_SECRET_KEY=local-dev-%RANDOM%-%RANDOM%-%RANDOM%-%RANDOM%"
set "ROCKPAPERGO_DATA_DIR=%CD%\instance"

echo [3/4] Initializing database...
"%VENV_PY%" -m flask --app wsgi init-db
if errorlevel 1 goto failed

echo [4/4] Server is ready.
echo.
echo Open on this PC: http://127.0.0.1:5000
echo For phones, use this PC's LAN IP followed by :5000
echo Example: http://192.168.1.100:5000
echo.
echo Press Ctrl+C or close this window to stop.
echo.
if /i "%~1"=="--check" goto check_ok
"%VENV_PY%" -m flask --app wsgi run --host 0.0.0.0 --port 5000
goto end

:check_ok
echo Startup check passed.
exit /b 0

:no_python
echo.
echo Python 3 was not found.
echo Install Python from https://www.python.org/downloads/
echo During setup, enable the option: Add Python to PATH
goto failed_pause

:failed
echo.
echo Startup failed. Review the error message above.

:failed_pause
pause
exit /b 1

:end
pause
endlocal
