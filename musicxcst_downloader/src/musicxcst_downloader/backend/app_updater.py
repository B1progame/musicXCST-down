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
from urllib.parse import quote


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
    gh = _github_cli()
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


def _github_cli() -> str:
    located = shutil.which("gh")
    if located:
        return located
    candidates = [
        str(Path(os.environ.get("ProgramFiles", "")) / "GitHub CLI" / "gh.exe"),
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "GitHub CLI" / "gh.exe"),
    ]
    return next((candidate for candidate in candidates if candidate and Path(candidate).is_file()), "")


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

    installer_name = str(installer.get("name") or "") if installer else ""
    tag_name = str(release.get("tag_name") or "")
    # GitHub's browser_download_url can occasionally point at a stale Azure
    # blob after an asset is replaced. Build the stable release URL from the
    # release tag and asset name instead.
    canonical_url = (
        f"https://github.com/{REPOSITORY}/releases/download/"
        f"{quote(tag_name, safe='')}/{quote(installer_name, safe='')}"
        if tag_name and installer_name
        else ""
    )

    return {
        "version": latest_version,
        "current_version": current_version,
        "update_available": _version_tuple(latest_version) > _version_tuple(current_version),
        "installer_url": canonical_url or (str(installer.get("browser_download_url")) if installer else ""),
        "installer_api_url": str(installer.get("url") or "") if installer else "",
        "installer_name": installer_name,
        "installer_digest": str(installer.get("digest") or "") if installer else "",
        "release_url": str(release.get("html_url") or ""),
    }


def update_event(current_version: str, release: dict) -> dict:
    """Build a UI event that identifies both installed and latest versions."""
    return {
        "current_version": current_version,
        "version": release["version"],
        "available": bool(release["update_available"]),
    }


def download_and_launch_update(
    installer_url: str,
    progress: ProgressCallback | None = None,
    expected_digest: str = "",
    fallback_url: str = "",
) -> dict:
    allowed_hosts = ("https://github.com/", "https://api.github.com/")
    if not installer_url.startswith(allowed_hosts):
        raise RuntimeError("The update installer must be hosted on GitHub.")

    target = Path(tempfile.gettempdir()) / "MusicXCST-Downloader-update.exe"
    headers = {"User-Agent": "MusicXCST-Downloader"}
    request = urllib.request.Request(installer_url, headers=headers)
    digest = expected_digest.removeprefix("sha256:").strip().lower()
    hasher = hashlib.sha256()
    try:
        response_context = urllib.request.urlopen(request, timeout=120)
    except HTTPError as exc:
        if exc.code != 404 or not fallback_url or not fallback_url.startswith("https://api.github.com/"):
            raise RuntimeError(
                "GitHub could not find the Windows installer asset (HTTP 404). "
                "The release may still be publishing; try again in a moment."
            ) from exc
        fallback_headers = {
            "Accept": "application/octet-stream",
            "User-Agent": "MusicXCST-Downloader",
        }
        token = _github_token()
        if token:
            fallback_headers["Authorization"] = f"Bearer {token}"
        fallback_request = urllib.request.Request(fallback_url, headers=fallback_headers)
        try:
            response_context = urllib.request.urlopen(fallback_request, timeout=120)
        except HTTPError as fallback_exc:
            raise RuntimeError(
                "GitHub could not provide the Windows installer asset (HTTP 404). "
                "Please try again after the release finishes publishing."
            ) from fallback_exc

    with response_context as response, target.open("wb") as output:
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

    command = [str(target), "--wait-pid", str(os.getpid())]
    subprocess.Popen(command, close_fds=True)
    return {"path": str(target)}
