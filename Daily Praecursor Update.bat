@echo off
echo ===================================================
echo PRAECURSOR-EGX DAILY AUTONOMOUS PIPELINE
echo ===================================================
echo.
cd /d "%USERPROFILE%\.gemini\antigravity\scratch\Praecursor-EGX"

echo [1/3] Starting the Dashboard Server in the background...
start "Praecursor Dashboard Server" cmd /k "title Praecursor Dashboard Server && echo Leave this window open to keep Mission Control running! && echo. && python -m praecursor.cli.dashboard"

echo.
echo [2/3] Launching Mission Control in your browser...
timeout /t 2 /nobreak >nul
start http://127.0.0.1:8000

echo.
echo [3/3] Running autonomous pipeline (scanner + outcome backfill + retraining + dashboard + telegram)...
echo Watch live progress in this terminal and on your browser screen!
echo.
python tools/run_autonomous_pipeline.py --force

echo.
echo ===================================================
echo Pipeline complete! Check reports/dashboard.html and Telegram.
echo ===================================================
pause

