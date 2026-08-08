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

$ToolsDir = $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($ToolsDir)) {
    $ToolsDir = Get-Location
}
$ProjectRoot = Split-Path -Parent $ToolsDir

if ([string]::IsNullOrWhiteSpace($ScriptPath)) {
    $ScriptPath = Join-Path $ToolsDir "run_autonomous_pipeline.py"
}

Write-Host "Registering Windows Scheduled Task '$TaskName' at $Time..."
Write-Host "Target script: $ScriptPath"

if (-not (Test-Path $ScriptPath)) {
    Write-Error "Error: Script path does not exist: $ScriptPath"
    exit 1
}

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

if ($ScriptPath.EndsWith(".py")) {
    $TaskAction = "`"`"$PythonPath`"`" `"`"$ScriptPath`"`""
} else {
    $TaskAction = "`"`"$ScriptPath`"`""
}

$process = Start-Process -FilePath "schtasks.exe" -ArgumentList "/Create", "/TN", "`"$TaskName`"", "/TR", $TaskAction, "/SC", "WEEKLY", "/D", "SUN,MON,TUE,WED,THU", "/ST", "$Time", "/F" -NoNewWindow -Wait -PassThru

if ($process.ExitCode -eq 0) {
    Write-Host "Task '$TaskName' registered successfully for $Time on EGX trading days (Sun-Thu)."
    exit 0
} else {
    Write-Warning "schtasks returned exit code $($process.ExitCode). Administrative privileges may be required."
    exit $process.ExitCode
}
