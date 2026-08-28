# Windows Task Scheduler runner.
# Schedule e.g. daily at 08:00:  schtasks /create /tn "news-to-sms" /tr "powershell -File run.ps1" /sc daily /st 08:00
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }
& $Python -m news_to_sms
exit $LASTEXITCODE
