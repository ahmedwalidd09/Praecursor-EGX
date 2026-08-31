@echo off
echo ===================================================
echo PRAECURSOR-EGX DAILY AUTONOMOUS PIPELINE
echo ===================================================
echo.
cd /d "%USERPROFILE%\.gemini\antigravity\scratch\Praecursor-EGX"

echo [1/3] Starting the Dashboard Server (in a new window)...
start "Praecursor Dashboard Server" cmd /k "title Praecursor Dashboard Server && echo Leave this window open to keep the website running! && echo. && python -m praecursor.cli.dashboard"

echo.
echo [2/3] Running autonomous pipeline (scanner + accuracy + retraining + dashboard)...
echo This takes 2-5 minutes. Do not close this window.
echo.
python tools/run_autonomous_pipeline.py --force

echo.
echo [3/3] Launching Dashboard in your browser...
start http://127.0.0.1:8000

echo.
echo Pipeline complete. Check logs/ for details.
pause
