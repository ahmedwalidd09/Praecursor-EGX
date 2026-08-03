@echo off
echo Updating Website from latest database scan...
python tools/regenerate_dashboard.py
echo.
echo Website updated successfully!
pause
