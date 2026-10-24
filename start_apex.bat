@echo off
rem Apex Coach: starts the backend, the website and the game recorder, then opens the site.
cd /d "%~dp0"

start "Apex backend" cmd /k "python -m uvicorn main:app --port 8000"
start "Apex website" cmd /k "cd frontend && npm.cmd run dev"
start "Apex recorder" cmd /k "python ac_recorder.py --driver Siva"

echo Starting. The browser opens in a few seconds.
timeout /t 8 /nobreak >nul
start "" http://localhost:5173
