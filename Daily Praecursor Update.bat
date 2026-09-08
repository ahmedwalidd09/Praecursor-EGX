@echo off
echo ===================================================
echo PRAECURSOR-EGX MISSION CONTROL LAUNCHER
echo ===================================================
echo.
cd /d "%USERPROFILE%\.gemini\antigravity\scratch\Praecursor-EGX"

echo [1/2] Starting the Dashboard Server in the background...
start "Praecursor Dashboard Server" cmd /k "title Praecursor Dashboard Server && echo Leave this window open to keep Mission Control running! && echo. && python -m praecursor.cli.dashboard"

echo.
echo [2/2] Launching Mission Control in your browser...
timeout /t 2 /nobreak >nul
start http://127.0.0.1:8000

echo.
echo ===================================================
echo Mission Control is live at http://127.0.0.1:8000
echo Click 'RUN SCAN' on the launch screen to trigger
echo the full autonomous scan and live telemetry!
echo ===================================================

