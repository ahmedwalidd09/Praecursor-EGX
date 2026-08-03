@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo PRAECURSOR-EGX TASK SCHEDULER REGISTRATION
echo ===================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0register_scheduled_task.ps1" %*
set EXIT_CODE=%ERRORLEVEL%

if %EXIT_CODE% EQU 0 (
    echo.
    echo Task registration completed successfully.
) else (
    echo.
    echo ERROR: Task registration failed with exit code !EXIT_CODE!.
)

exit /b %EXIT_CODE%
