# One-time setup for Windows (PowerShell):
#   powershell -ExecutionPolicy Bypass -File install.ps1 [path\to\profile.json]
param([string]$Profile = "")
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$py = Get-Command py -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python -ErrorAction SilentlyContinue }
if (-not $py) {
  Write-Host "Python 3 is needed. Install it from https://www.python.org/downloads/ (tick 'Add python.exe to PATH') and run this again."
  exit 1
}
& $py.Source -c "import sys; sys.exit(sys.version_info < (3, 11))"
if ($LASTEXITCODE -ne 0) { Write-Host "Python 3.11 or newer is needed."; exit 1 }

& $py.Source -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --quiet --upgrade pip
& .\.venv\Scripts\python.exe -m pip install --quiet -e .
& .\.venv\Scripts\jobagent.exe init

if ($Profile -ne "") { & .\.venv\Scripts\jobagent.exe profile import $Profile }

& .\.venv\Scripts\jobagent.exe schedule install --every 30
Write-Host ""
Write-Host "Done. The agent now runs every 30 minutes in the background."
Write-Host "Dashboard:  .\.venv\Scripts\jobagent.exe serve   then open http://127.0.0.1:8765"
Write-Host "Connect Gmail + Calendar when ready:  .\.venv\Scripts\jobagent.exe connect google"
