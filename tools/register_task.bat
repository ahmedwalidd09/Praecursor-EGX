@echo off
set TASK_NAME=PraecursorDailyUpdate
set TASK_TIME=17:00
set SCRIPT_PATH=

if not "%~1"=="" set TASK_NAME=%~1
if not "%~2"=="" set TASK_TIME=%~2
if not "%~3"=="" set SCRIPT_PATH=%~3

if "%SCRIPT_PATH%"=="" (
    for /f "delims=" %%I in ("%~dp0..") do set "SCRIPT_PATH=%%~fI\Daily Praecursor Update.bat"
)

if not exist "%SCRIPT_PATH%" (
    echo Error: Script path does not exist: %SCRIPT_PATH%
    exit /b 1
)

echo Registering Scheduled Task: %TASK_NAME% at %TASK_TIME%
echo Target script: %SCRIPT_PATH%

schtasks /Create /TN "%TASK_NAME%" /TR "\"%SCRIPT_PATH%\"" /SC DAILY /ST %TASK_TIME% /F
if %ERRORLEVEL% equ 0 (
    echo Task %TASK_NAME% registered successfully.
    exit /b 0
) else (
    echo Warning: schtasks returned error %ERRORLEVEL%. Administrative privileges may be required.
    exit /b %ERRORLEVEL%
)
