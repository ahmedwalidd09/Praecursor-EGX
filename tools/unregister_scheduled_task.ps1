<#
.SYNOPSIS
    Unregisters the Praecursor-EGX Daily Scanner task from Windows Task Scheduler.
#>

[CmdletBinding()]
param (
    [string]$TaskName = "Praecursor-EGX Daily Scanner"
)

$ErrorActionPreference = "Stop"

Write-Host "Unregistering Scheduled Task '$TaskName'..." -ForegroundColor Cyan

try {
    $Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($Task) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "Task '$TaskName' successfully unregistered." -ForegroundColor Green
    } else {
        Write-Host "Task '$TaskName' was not found in Task Scheduler." -ForegroundColor Yellow
    }
} catch {
    Write-Host "Task '$TaskName' was not found or could not be unregistered: $_" -ForegroundColor Yellow
}
