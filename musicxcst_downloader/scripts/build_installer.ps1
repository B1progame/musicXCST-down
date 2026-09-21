$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Get-ProjectVersion {
    $Pyproject = Join-Path $Root "pyproject.toml"
    $Match = [regex]::Match((Get-Content $Pyproject -Raw), '(?m)^version\s*=\s*"([^"]+)"\s*$')
    if (-not $Match.Success) {
        throw "Could not read project version from pyproject.toml"
    }
    return $Match.Groups[1].Value
}

$Version = Get-ProjectVersion

# Always rebuild before creating the installer so the packaged files and installer
# metadata stay aligned with the current source version.
& "$PSScriptRoot\build_exe.ps1"

$Payload = Join-Path $Root "installer\payload.zip"
$PayloadSource = Join-Path $Root "dist\MusicXCST Downloader"
if (-not (Test-Path $PayloadSource)) {
    throw "PyInstaller output was not found at $PayloadSource"
}
Compress-Archive -Path $PayloadSource -DestinationPath $Payload -Force

$CandidateVenvs = @(
    (Join-Path $Root ".venv"),
    (Join-Path (Split-Path -Parent $Root) ".venv")
)
$Venv = $CandidateVenvs | Where-Object {
    Test-Path (Join-Path $_ "Scripts\pyinstaller.exe")
} | Select-Object -First 1
if (-not $Venv) {
    throw "The project virtual environment with PyInstaller was not found."
}
$PyInstaller = Join-Path $Venv "Scripts\pyinstaller.exe"
$Icon = Join-Path $Root "src\musicxcst_downloader\frontend\assets\icon.ico"
$InstallerName = "MusicXCST-Downloader-Setup-$Version"

& $PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name $InstallerName `
    --icon $Icon `
    --add-data "$Payload;." `
    --add-data "$Icon;." `
    --distpath (Join-Path $Root "dist\installer") `
    --workpath (Join-Path $Root "build\terminal-installer") `
    --specpath (Join-Path $Root "build\terminal-installer") `
    "installer\terminal_installer.py"
if ($LASTEXITCODE -ne 0) {
    throw "Terminal installer build failed with exit code $LASTEXITCODE"
}
Write-Host "Built dist\installer\$InstallerName.exe"
