param(
    [string]$PythonCommand = "python",
    [string]$Preset = "",
    [string]$ApiKey = "",
    [switch]$NonInteractive,
    [switch]$SkipGlobalLauncher
)

$ErrorActionPreference = "Stop"

$InstallRoot = (Resolve-Path $PSScriptRoot).Path
$LauncherDir = if ($env:EASYAI_LAUNCHER_DIR) { $env:EASYAI_LAUNCHER_DIR } else { (Get-Location).Path }
$UserBin = Join-Path $env:LOCALAPPDATA "EasyAI\bin"
$UserStateDir = Join-Path $env:LOCALAPPDATA "EasyAI"
$InstallRootFile = Join-Path $UserStateDir "install-root.txt"
$VenvPython = Join-Path $InstallRoot ".venv\Scripts\python.exe"
$VenvPip = Join-Path $InstallRoot ".venv\Scripts\pip.exe"
$VenvEasyAI = Join-Path $InstallRoot ".venv\Scripts\easyai.exe"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Write-Utf8NoBomFile($Path, $Text) {
    [System.IO.File]::WriteAllText($Path, $Text, $Utf8NoBom)
}

function Assert-LastExitCode($Message) {
    if ($LASTEXITCODE -ne 0) {
        throw $Message
    }
}

function Write-Section($Text) {
    Write-Host ""
    Write-Host $Text -ForegroundColor Cyan
}

function Ensure-UserPath($PathToAdd) {
    $current = [Environment]::GetEnvironmentVariable("Path", "User")
    $parts = @()
    if ($current) {
        $parts = $current.Split(";") | Where-Object { $_ }
    }
    if ($parts -notcontains $PathToAdd) {
        $newPath = if ($current) { "$PathToAdd;$current" } else { $PathToAdd }
        [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    }
    if (($env:Path.Split(";") | Where-Object { $_ }) -notcontains $PathToAdd) {
        $env:Path = "$PathToAdd;$env:Path"
    }
}

function Select-Preset {
    param([string]$Requested)
    $value = $Requested.Trim().ToLower()
    if ($value) { return $value }
    if ($NonInteractive) { return "deepseek" }
    Write-Host "Select model preset:" -ForegroundColor Yellow
    Write-Host "  1) deepseek    DeepSeek API"
    Write-Host "  2) openrouter  OpenRouter API"
    Write-Host "  3) openai      OpenAI API"
    Write-Host "  4) ollama      Local Ollama"
    $choice = Read-Host "Preset [1]"
    switch ($choice.Trim()) {
        "2" { return "openrouter" }
        "3" { return "openai" }
        "4" { return "ollama" }
        default { return "deepseek" }
    }
}

function Preset-Config {
    param([string]$Name)
    switch ($Name) {
        "openrouter" {
            return @{
                provider = "openai_compatible"
                model = "openai/gpt-4o-mini"
                base_url = "https://openrouter.ai/api/v1"
                key_name = "OPENROUTER_API_KEY"
            }
        }
        "openai" {
            return @{
                provider = "openai_compatible"
                model = "gpt-4o-mini"
                base_url = "https://api.openai.com/v1"
                key_name = "OPENAI_API_KEY"
            }
        }
        "ollama" {
            return @{
                provider = "ollama"
                model = "qwen2.5-coder:7b"
                base_url = "http://localhost:11434"
                key_name = ""
            }
        }
        default {
            return @{
                provider = "openai_compatible"
                model = "deepseek-v4-flash"
                base_url = "https://api.deepseek.com"
                key_name = "DEEPSEEK_API_KEY"
            }
        }
    }
}

Write-Section "Installing EasyAI client..."

if (-not (Get-Command $PythonCommand -ErrorAction SilentlyContinue)) {
    throw "Python was not found. Install Python 3.8+ first, then run this installer again."
}

if (-not (Test-Path $VenvPython)) {
    & $PythonCommand -m venv (Join-Path $InstallRoot ".venv")
}

& $VenvPython -m pip install --upgrade pip setuptools wheel
Assert-LastExitCode "Failed to upgrade pip/setuptools/wheel."
& $VenvPip install -e $InstallRoot --no-build-isolation
Assert-LastExitCode "Failed to install EasyAI client."

$selectedPreset = Select-Preset -Requested $Preset
$presetConfig = Preset-Config -Name $selectedPreset

if (-not $ApiKey -and -not $NonInteractive -and $presetConfig.key_name) {
    $ApiKey = Read-Host "API key for $($presetConfig.key_name) (leave empty to fill later)"
}

$configPath = Join-Path $InstallRoot "config.yaml"
$modelConfigured = "false"
if ($ApiKey) {
    $modelConfigured = "true"
}
$configText = @"
preset: $selectedPreset
provider: $($presetConfig.provider)
model: $($presetConfig.model)
base_url: $($presetConfig.base_url)
temperature: 0.2
max_tokens: 1200
app_base_url: https://xingkongtech.top
ollama_base_url: http://localhost:11434
model_connection_configured: $modelConfigured
"@
Write-Utf8NoBomFile -Path $configPath -Text $configText

$envPath = Join-Path $InstallRoot ".env"
$envLines = @(
    "DEEPSEEK_API_KEY=",
    "OPENROUTER_API_KEY=",
    "OPENAI_API_KEY=",
    "OPENAI_COMPATIBLE_API_KEY=",
    "OLLAMA_BASE_URL=http://localhost:11434"
)
if ($presetConfig.key_name -and $ApiKey) {
    $envLines = $envLines | ForEach-Object {
        if ($_.StartsWith("$($presetConfig.key_name)=")) { "$($presetConfig.key_name)=$ApiKey" } else { $_ }
    }
}
$envText = ($envLines -join [Environment]::NewLine) + [Environment]::NewLine
Write-Utf8NoBomFile -Path $envPath -Text $envText

$launcher = @"
@echo off
setlocal
"$VenvEasyAI" %*
"@
if (-not $SkipGlobalLauncher) {
    New-Item -ItemType Directory -Path $UserStateDir -Force | Out-Null
    New-Item -ItemType Directory -Path $UserBin -Force | Out-Null
    Write-Utf8NoBomFile -Path $InstallRootFile -Text $InstallRoot
    $globalPsLauncher = @'
$root = [System.IO.File]::ReadAllText(($env:LOCALAPPDATA + '\EasyAI\install-root.txt'), [System.Text.Encoding]::UTF8).Trim()
& (Join-Path $root '.venv\Scripts\python.exe') -m pyai_assistant.cli.client @args
exit $LASTEXITCODE
'@
    Write-Utf8NoBomFile -Path (Join-Path $UserBin "easyai-launch.ps1") -Text $globalPsLauncher
    $globalLauncher = @'
@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%LOCALAPPDATA%\EasyAI\bin\easyai-launch.ps1" %*
'@
    $globalLauncher | Set-Content -Path (Join-Path $UserBin "easyai.cmd") -Encoding ASCII
    $globalLauncher | Set-Content -Path (Join-Path $UserBin "Easyai.cmd") -Encoding ASCII
    Ensure-UserPath -PathToAdd $UserBin
}
$localLauncher = @'
@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -Command "& { & '%~dp0.venv\Scripts\python.exe' -m pyai_assistant.cli.client @args }" -- %*
'@
$localLauncher | Set-Content -Path (Join-Path $InstallRoot "Easyai.cmd") -Encoding ASCII
$localLauncher | Set-Content -Path (Join-Path $LauncherDir "easyai.cmd") -Encoding ASCII
$localLauncher | Set-Content -Path (Join-Path $LauncherDir "Easyai.cmd") -Encoding ASCII

$SelfTestWorkspace = Join-Path $env:TEMP "easyai-self-test-workspace"
New-Item -ItemType Directory -Path $SelfTestWorkspace -Force | Out-Null
Push-Location $SelfTestWorkspace
try {
    $SelfTestLauncher = if ($SkipGlobalLauncher) { (Join-Path $LauncherDir "easyai.cmd") } else { (Join-Path $UserBin "easyai.cmd") }
    & $SelfTestLauncher --self-test
    if ($LASTEXITCODE -ne 0) {
        throw "EasyAI self-test failed."
    }
}
finally {
    Pop-Location
}

Write-Section "EasyAI client installed."
Write-Host "Install root: $InstallRoot" -ForegroundColor Green
Write-Host "Global commands: easyai  or  Easyai" -ForegroundColor Green
Write-Host "Current directory launchers: $(Join-Path $LauncherDir 'easyai.cmd') and $(Join-Path $LauncherDir 'Easyai.cmd')" -ForegroundColor Green
Write-Host "Self-test: passed" -ForegroundColor Green
Write-Host "You can run EasyAI from any directory. File operations use the directory where you start it." -ForegroundColor Yellow
Write-Host ""
Write-Host "If an old terminal cannot find easyai from another directory immediately, open a new terminal so Windows reloads PATH." -ForegroundColor Cyan
