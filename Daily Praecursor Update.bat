@echo off
echo ===================================================
echo PRAECURSOR-EGX MISSION CONTROL & DAILY SCANNER
echo ===================================================
echo.
cd /d "%USERPROFILE%\.gemini\antigravity\scratch\Praecursor-EGX"

echo [1/2] Starting Mission Control Dashboard Server...
start "Praecursor Mission Control Server" cmd /k "title Praecursor Mission Control Server && echo =================================================== && echo PRAECURSOR-EGX MISSION CONTROL SERVER && echo Keep this window open while using Mission Control! && echo =================================================== && echo. && python -m praecursor.cli.dashboard"

echo [2/2] Launching Mission Control in your default browser...
timeout /t 2 /nobreak >nul
start http://127.0.0.1:8000

echo.
echo Mission Control is live at http://127.0.0.1:8000
echo You can trigger scans, monitor real-time progress, and review institutional reports from the web UI.
exit

