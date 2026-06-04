$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path "dist\MusicXCST Downloader")) {
    & "$PSScriptRoot\build_exe.ps1"
}

$Inno = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $Inno)) {
    $Inno = "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
}
if (-not (Test-Path $Inno)) {
    throw "Inno Setup 6 was not found. Install it, then rerun this script."
}

& $Inno "installer\MusicXCST-Downloader.iss"

