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

$Inno = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $Inno)) {
    $Inno = "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
}
if (-not (Test-Path $Inno)) {
    throw "Inno Setup 6 was not found. Install it, then rerun this script."
}

& $Inno "/DMyAppVersion=$Version" "installer\MusicXCST-Downloader.iss"
