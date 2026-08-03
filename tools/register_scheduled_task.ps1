<#
.SYNOPSIS
    Registers Praecursor-EGX Daily Scanner task in Windows Task Scheduler for 5:00 PM (17:00) on EGX Trading Days (Sun-Thu).
.DESCRIPTION
    Creates or updates the Windows Scheduled Task 'Praecursor-EGX Daily Scanner' to execute
    the autonomous headless pipeline runner (tools/run_autonomous_pipeline.py).
#>

[CmdletBinding()]
param (
    [string]$TaskName = "Praecursor-EGX Daily Scanner",
    [string]$Time = "17:00",
    [string]$ProjectPath = ""
)

$ErrorActionPreference = "Stop"

# Resolve Project Root Path dynamically if not passed
if ([string]::IsNullOrWhiteSpace($ProjectPath)) {
    $ProjectPath = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

# Resolve Python Executable Path
$PythonPath = $env:PYTHON_EXECUTABLE
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    $PythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($PythonCmd) {
        $PythonPath = $PythonCmd.Source
    } else {
        $PythonPath = (Get-Command where.exe python -ErrorAction SilentlyContinue | Select-Object -First 1)
    }
}

if ([string]::IsNullOrWhiteSpace($PythonPath) -or -not (Test-Path $PythonPath)) {
    Write-Error "Python executable could not be resolved. Please ensure python is in PATH or set PYTHON_EXECUTABLE."
    exit 1
}

$ScriptPath = Join-Path $ProjectPath "tools\run_autonomous_pipeline.py"
if (-not (Test-Path $ScriptPath)) {
    Write-Error "Runner script not found at $ScriptPath"
    exit 1
}

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "Registering Scheduled Task: '$TaskName'" -ForegroundColor Cyan
Write-Host "Project Directory: $ProjectPath"
Write-Host "Python Executable: $PythonPath"
Write-Host "Pipeline Script:   $ScriptPath"
Write-Host "Schedule:          Sunday, Monday, Tuesday, Wednesday, Thursday at $Time"
Write-Host "=================================================="

# 1. Action: Execute Python with tools/run_autonomous_pipeline.py in project root cwd
$Action = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument "`"$ScriptPath`"" `
    -WorkingDirectory $ProjectPath

# 2. Trigger: Weekly on Sun, Mon, Tue, Wed, Thu at 17:00 (5:00 PM EET/EEST)
$Trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -DaysOfWeek Sunday, Monday, Tuesday, Wednesday, Thursday `
    -At $Time

# 3. Settings: Start on battery, don't stop if battery, restart on failure, 30 min limit
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

# 4. Register Scheduled Task
$Description = "Automated daily EGX stock scan, outcome tracking, retraining, and reporting for Praecursor-EGX at 5:00 PM on EGX trading days."

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description $Description `
    -Force | Out-Null

Write-Host "Scheduled task '$TaskName' registered successfully!" -ForegroundColor Green
