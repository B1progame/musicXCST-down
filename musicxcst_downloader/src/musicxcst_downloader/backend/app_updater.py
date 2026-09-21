from __future__ import annotations

import json
import os
import subprocess
import tempfile
import urllib.request
from pathlib import Path


REPOSITORY = "B1progame/musicXCST-down"
RELEASES_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = value.lstrip("vV").split(".")
    result = []
    for part in parts:
        digits = "".join(char for char in part if char.isdigit())
        result.append(int(digits or 0))
    return tuple(result or [0])


def check_for_update(current_version: str) -> dict:
    request = urllib.request.Request(
        RELEASES_URL,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "MusicXCST-Downloader"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        release = json.load(response)

    latest_version = str(release.get("tag_name") or release.get("name") or "").lstrip("vV")
    if not latest_version:
        raise RuntimeError("The latest GitHub release has no version tag.")

    assets = release.get("assets") or []
    installer = next(
        (
            asset for asset in assets
            if str(asset.get("name", "")).lower().endswith(".exe")
            and "setup" in str(asset.get("name", "")).lower()
        ),
        None,
    )
    if installer is None:
        installer = next(
            (asset for asset in assets if str(asset.get("name", "")).lower().endswith(".exe")),
            None,
        )

    return {
        "version": latest_version,
        "current_version": current_version,
        "update_available": _version_tuple(latest_version) > _version_tuple(current_version),
        "installer_url": str(installer.get("browser_download_url")) if installer else "",
        "release_url": str(release.get("html_url") or ""),
    }


def download_and_launch_update(installer_url: str) -> dict:
    if not installer_url.startswith("https://github.com/"):
        raise RuntimeError("The update installer must be hosted on GitHub.")

    target = Path(tempfile.gettempdir()) / "MusicXCST-Downloader-update.exe"
    request = urllib.request.Request(installer_url, headers={"User-Agent": "MusicXCST-Downloader"})
    with urllib.request.urlopen(request, timeout=120) as response, target.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)

    os.startfile(str(target))  # type: ignore[attr-defined]
    return {"path": str(target)}
