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
    $ScriptPath = Join-Path $ProjectRoot "Daily Praecursor Update.bat"
}

Write-Host "Registering Windows Scheduled Task '$TaskName' at $Time..."
Write-Host "Target script: $ScriptPath"

if (-not (Test-Path $ScriptPath)) {
    Write-Error "Error: Script path does not exist: $ScriptPath"
    exit 1
}

# Run schtasks to register the daily task at specified time non-interactively
$schtasks = Get-Command "schtasks.exe" -ErrorAction SilentlyContinue
if (-not $schtasks) {
    Write-Error "schtasks.exe command not found on system."
    exit 1
}

& schtasks.exe /Create /TN "$TaskName" /TR "`"$ScriptPath`"" /SC DAILY /ST "$Time" /F

if ($LASTEXITCODE -eq 0) {
    Write-Host "Task '$TaskName' registered successfully for $Time daily."
    exit 0
} else {
    Write-Warning "schtasks returned exit code $LASTEXITCODE. Administrative privileges may be required."
    exit $LASTEXITCODE
}
