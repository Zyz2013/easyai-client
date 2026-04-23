param(
    [string]$PythonCommand = "python"
)

$ErrorActionPreference = "Stop"

Write-Host "Installing EasyAI client..." -ForegroundColor Cyan

if (-not (Get-Command $PythonCommand -ErrorAction SilentlyContinue)) {
    throw "Python was not found. Install Python 3.8+ first, then run this installer again."
}

& $PythonCommand -m venv .venv
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\pip.exe" install -e .

$launcher = @"
@echo off
setlocal
cd /d "%~dp0"
".venv\Scripts\easyai.exe" %*
"@
$launcher | Set-Content -Path "Easyai.cmd" -Encoding ASCII

Write-Host ""
Write-Host "EasyAI client installed." -ForegroundColor Green
Write-Host "Run it with:" -ForegroundColor Green
Write-Host "  .\Easyai.cmd" -ForegroundColor Yellow
Write-Host ""
Write-Host "If this is the first run, edit config.yaml/.env for this user's API or Ollama settings." -ForegroundColor Cyan
