[CmdletBinding()]
param (
    [Parameter(Position=0)]
    [string]$TaskName = "PraecursorDailyUpdate",

    [Parameter(Position=1)]
    [string]$Time = "17:00",

    [Parameter(Position=2)]
    [string]$ScriptPath = ""
)

$ErrorActionPreference = "Stop"

$ProjectRoot = $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = Get-Location
}

if ([string]::IsNullOrWhiteSpace($ScriptPath)) {
    $ScriptPath = Join-Path $ProjectRoot "tools\run_autonomous_pipeline.py"
}

Write-Host "Registering Windows Scheduled Task '$TaskName' at $Time..."
Write-Host "Target script: $ScriptPath"

if (-not (Test-Path $ScriptPath)) {
    Write-Error "Error: Script path does not exist: $ScriptPath"
    exit 1
}

# Resolve Python executable
$PythonPath = $env:PYTHON_EXECUTABLE
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    $PythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($PythonCmd) {
        $PythonPath = $PythonCmd.Source
    } else {
        $PythonPath = (Get-Command where.exe python -ErrorAction SilentlyContinue | Select-Object -First 1)
    }
}
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    $PythonPath = "python"
}

# Run schtasks to register the weekly task on Sun-Thu at specified time non-interactively
$schtasks = Get-Command "schtasks.exe" -ErrorAction SilentlyContinue
if (-not $schtasks) {
    Write-Error "schtasks.exe command not found on system."
    exit 1
}

if ($ScriptPath.EndsWith(".py")) {
    $TaskAction = "`"$PythonPath`" `"$ScriptPath`""
} else {
    $TaskAction = "`"$ScriptPath`""
}

& schtasks.exe /Create /TN "$TaskName" /TR "$TaskAction" /SC WEEKLY /D SUN,MON,TUE,WED,THU /ST "$Time" /F

if ($LASTEXITCODE -eq 0) {
    Write-Host "Task '$TaskName' registered successfully for $Time on EGX trading days (Sun-Thu)."
    exit 0
} else {
    Write-Warning "schtasks returned exit code $LASTEXITCODE. Administrative privileges may be required."
    exit $LASTEXITCODE
}
