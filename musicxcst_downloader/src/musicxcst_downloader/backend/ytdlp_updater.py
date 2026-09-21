from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

from yt_dlp.version import __version__

from .paths import app_data_dir

ProgressCallback = Callable[[dict], None]


def installed_ytdlp_version() -> str:
    return __version__


def _download(url: str, target: Path, expected_sha256: str, progress: ProgressCallback | None) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "MusicXCST-Downloader"})
    digest = hashlib.sha256()
    with urllib.request.urlopen(request, timeout=120) as response, target.open("wb") as output:
        total = int(response.headers.get("Content-Length") or 0)
        downloaded = 0
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
            digest.update(chunk)
            downloaded += len(chunk)
            if progress and total:
                progress({"percent": round(downloaded / total * 100, 1), "status": "Downloading yt-dlp..."})
    if digest.hexdigest().lower() != expected_sha256.lower():
        target.unlink(missing_ok=True)
        raise RuntimeError("The yt-dlp download failed its SHA-256 integrity check.")


def _extract_verified_package(archive_path: Path, destination: Path) -> None:
    with zipfile.ZipFile(archive_path) as archive:
        members = [member for member in archive.infolist() if member.filename.startswith("yt_dlp/")]
        if not members:
            raise RuntimeError("The verified yt-dlp wheel did not contain its package.")
        for member in members:
            relative = Path(member.filename)
            if relative.is_absolute() or ".." in relative.parts:
                raise RuntimeError("The yt-dlp package contained an unsafe path.")
            target = destination / relative
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)


def update_ytdlp(progress: ProgressCallback | None = None) -> dict:
    """Install a hash-verified yt-dlp package override for the next app start."""
    if progress:
        progress({"percent": 0, "status": "Checking the latest yt-dlp release..."})
    metadata_request = urllib.request.Request("https://pypi.org/pypi/yt-dlp/json", headers={"User-Agent": "MusicXCST-Downloader"})
    with urllib.request.urlopen(metadata_request, timeout=30) as response:
        metadata = json.load(response)
    version = str(metadata["info"]["version"])
    wheel = next(
        (file for file in metadata["releases"].get(version, []) if str(file.get("filename", "")).endswith("py3-none-any.whl")),
        None,
    )
    if not wheel or not wheel.get("digests", {}).get("sha256"):
        raise RuntimeError(f"No compatible verified yt-dlp wheel was found for {version}.")

    with tempfile.TemporaryDirectory(prefix="musicxcst-ytdlp-") as temp_dir:
        temp_path = Path(temp_dir)
        wheel_path = temp_path / str(wheel["filename"])
        _download(str(wheel["url"]), wheel_path, str(wheel["digests"]["sha256"]), progress)
        staged = temp_path / "override"
        _extract_verified_package(wheel_path, staged)
        override = app_data_dir() / "yt_dlp_override"
        if override.exists():
            shutil.rmtree(override)
        shutil.move(str(staged), str(override))

    if progress:
        progress({"percent": 100, "status": f"yt-dlp {version} installed. Restart the app to activate it."})
    return {"version": version, "output": "verified package override installed"}
