from __future__ import annotations

import json
import hashlib
import os
import shutil
import subprocess
import tempfile
import urllib.request
from urllib.error import HTTPError
from pathlib import Path
from typing import Callable


REPOSITORY = "B1progame/musicXCST-down"
RELEASES_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
ProgressCallback = Callable[[dict], None]


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = value.lstrip("vV").split(".")
    result = []
    for part in parts:
        digits = "".join(char for char in part if char.isdigit())
        result.append(int(digits or 0))
    return tuple(result or [0])


def _github_token() -> str:
    gh = shutil.which("gh")
    if not gh:
        return ""
    try:
        result = subprocess.run(
            [gh, "auth", "token"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def _release_json() -> dict:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "MusicXCST-Downloader"}
    request = urllib.request.Request(RELEASES_URL, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.load(response)
    except HTTPError as exc:
        if exc.code not in {401, 404}:
            raise
        token = _github_token()
        if not token:
            raise RuntimeError(
                "GitHub could not be reached. This repository is private; sign in with GitHub CLI (gh auth login) first."
            ) from exc
        headers["Authorization"] = f"Bearer {token}"
        authenticated_request = urllib.request.Request(RELEASES_URL, headers=headers)
        with urllib.request.urlopen(authenticated_request, timeout=20) as response:
            return json.load(response)


def check_for_update(current_version: str) -> dict:
    release = _release_json()

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
        "installer_digest": str(installer.get("digest") or "") if installer else "",
        "release_url": str(release.get("html_url") or ""),
    }


def download_and_launch_update(
    installer_url: str,
    progress: ProgressCallback | None = None,
    expected_digest: str = "",
) -> dict:
    if not installer_url.startswith("https://github.com/"):
        raise RuntimeError("The update installer must be hosted on GitHub.")

    target = Path(tempfile.gettempdir()) / "MusicXCST-Downloader-update.exe"
    request = urllib.request.Request(installer_url, headers={"User-Agent": "MusicXCST-Downloader"})
    digest = expected_digest.removeprefix("sha256:").strip().lower()
    hasher = hashlib.sha256()
    with urllib.request.urlopen(request, timeout=120) as response, target.open("wb") as output:
        total = int(response.headers.get("Content-Length") or 0)
        downloaded = 0
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
            hasher.update(chunk)
            downloaded += len(chunk)
            if progress and total:
                progress({"percent": round(downloaded / total * 100, 1), "status": "Downloading application installer..."})

    if digest and hasher.hexdigest().lower() != digest:
        target.unlink(missing_ok=True)
        raise RuntimeError("The downloaded application installer failed its SHA-256 integrity check.")

    os.startfile(str(target))  # type: ignore[attr-defined]
    return {"path": str(target)}
