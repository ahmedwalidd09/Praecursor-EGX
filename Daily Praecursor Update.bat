@echo off
echo ===================================================
echo PRAECURSOR-EGX DAILY UPDATE RUNNER
echo ===================================================
echo.
cd /d "%USERPROFILE%\.gemini\antigravity\scratch\Praecursor-EGX"

echo [1/3] Starting the Dashboard Server (in a new window)...
start "Praecursor Dashboard Server" cmd /k "title Praecursor Dashboard Server && echo Leave this window open to keep the website running! && echo. && python -m praecursor.cli.dashboard"

echo.
echo [2/3] Running the daily scanner and updating accuracy tracking... (This takes 1-2 minutes)
python tools/run_scanner.py

echo.
echo [3/3] Launching Dashboard in your browser...
start http://127.0.0.1:8000

echo.
echo All done! You can now close this runner window.
pause
