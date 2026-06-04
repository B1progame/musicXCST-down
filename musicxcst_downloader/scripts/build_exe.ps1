$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".venv")) {
    py -3.12 -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e .[dev]

$Icon = "src\musicxcst_downloader\frontend\assets\icon.ico"
$AddData = "src\musicxcst_downloader\frontend;musicxcst_downloader\frontend"

& .\.venv\Scripts\pyinstaller.exe `
    --noconfirm `
    --clean `
    --onedir `
    --windowed `
    --name "MusicXCST Downloader" `
    --icon $Icon `
    --add-data $AddData `
    --collect-all webview `
    --paths "src" `
    "src\run_musicxcst_downloader.py"

Write-Host "Built dist\MusicXCST Downloader"
