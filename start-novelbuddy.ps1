param(
    [int]$Port = 8765,
    [switch]$OpenBrowser
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$uv = (Get-Command uv).Source

Get-CimInstance Win32_Process |
    Where-Object { $_.Name -eq "python.exe" -and $_.CommandLine -like "*novelbuddy.web*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Start-Sleep -Seconds 1
Start-Process -FilePath $uv -ArgumentList @("run", "python", "-m", "novelbuddy.web", "--port", "$Port") -WorkingDirectory $root -WindowStyle Hidden

$url = "http://127.0.0.1:$Port/"
for ($i = 0; $i -lt 20; $i++) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing $url -TimeoutSec 2
        if ($response.StatusCode -eq 200) {
            Write-Host "NovelBuddy started: $url"
            if ($OpenBrowser) {
                Start-Process $url
            }
            exit 0
        }
    } catch {
        Start-Sleep -Milliseconds 500
    }
}

Write-Error "NovelBuddy failed to start. Check whether port $Port is already in use."
exit 1
