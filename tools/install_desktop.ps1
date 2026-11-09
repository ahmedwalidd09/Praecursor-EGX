$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$desktopPath = [Environment]::GetFolderPath('Desktop')
$pythonPath = (Get-Command python.exe).Source
$pythonWindowless = Join-Path (Split-Path -Parent $pythonPath) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonWindowless)) { $pythonWindowless = $pythonPath }
$shortcutPath = Join-Path $desktopPath 'Praecursor EGX.lnk'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $pythonWindowless
$shortcut.Arguments = '"' + (Join-Path $repoRoot 'tools\desktop.py') + '"'
$shortcut.WorkingDirectory = $repoRoot
$shortcut.Description = 'Open the Praecursor EGX research dashboard'
$shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,16"
$shortcut.WindowStyle = 7
$shortcut.Save()
Write-Output $shortcutPath
