$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RepoRoot = Split-Path -Parent $ProjectRoot
Set-Location $ProjectRoot

$CandidateVenvs = @(
    (Join-Path $ProjectRoot ".venv"),
    (Join-Path $RepoRoot ".venv")
)

$Venv = $CandidateVenvs | Where-Object {
    Test-Path (Join-Path $_ "Scripts\python.exe")
} | Select-Object -First 1

if (-not $Venv) {
    $Venv = Join-Path $ProjectRoot ".venv"
    $PythonVersion = $null
    foreach ($Version in @("3.12", "3.11")) {
        py "-$Version" --version *> $null
        if ($LASTEXITCODE -eq 0) {
            $PythonVersion = $Version
            break
        }
    }
    if (-not $PythonVersion) {
        throw "Python 3.12 or 3.11 was not found. Install Python 3.12, then rerun this script."
    }
    py "-$PythonVersion" -m venv $Venv
}

$Python = Join-Path $Venv "Scripts\python.exe"
$PyInstaller = Join-Path $Venv "Scripts\pyinstaller.exe"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command,
        [Parameter(Mandatory = $true)]
        [string]$Label
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

Invoke-Checked { & $Python -m ensurepip --upgrade } "ensurepip"
Invoke-Checked { & $Python -m pip install --upgrade pip } "pip upgrade"
Invoke-Checked { & $Python -m pip install -e .[dev] } "dependency install"

$Icon = "src\musicxcst_downloader\frontend\assets\icon.ico"
$AddData = "src\musicxcst_downloader\frontend;musicxcst_downloader\frontend"

Invoke-Checked { & $PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --windowed `
    --name "MusicXCST Downloader" `
    --icon $Icon `
    --add-data $AddData `
    --collect-all webview `
    --paths "src" `
    "src\run_musicxcst_downloader.py" } "PyInstaller build"

Write-Host "Built dist\MusicXCST Downloader"
