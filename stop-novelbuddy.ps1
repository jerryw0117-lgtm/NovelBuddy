$ErrorActionPreference = "Stop"
$processes = Get-CimInstance Win32_Process |
    Where-Object { $_.Name -eq "python.exe" -and $_.CommandLine -like "*novelbuddy.web*" }

if (-not $processes) {
    Write-Host "NovelBuddy is not running."
    exit 0
}

$processes | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Write-Host "NovelBuddy stopped."
