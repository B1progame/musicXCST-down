from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
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


def _version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) if part.isdigit() else 0 for part in str(value).lstrip("vV").split("."))


def check_ytdlp_update() -> dict:
    """Compare installed yt-dlp with the latest PyPI release."""
    current = installed_ytdlp_version()
    request = urllib.request.Request(
        "https://pypi.org/pypi/yt-dlp/json",
        headers={"User-Agent": "MusicXCST-Downloader"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        latest = str(json.load(response)["info"]["version"])
    return {
        "current_version": current,
        "latest_version": latest,
        "update_available": _version_tuple(latest) > _version_tuple(current),
    }


def build_pip_update_command(python_executable: Path, target: Path) -> list[str]:
    return [
        str(python_executable),
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-input",
        "--upgrade",
        "--target",
        str(target),
        "yt-dlp",
    ]


def _pip_python() -> Path | None:
    if not getattr(sys, "frozen", False):
        return Path(sys.executable)
    for executable in (shutil.which("python"), shutil.which("py")):
        if executable:
            return Path(executable)
    return None


def _pip_install(target: Path, progress: ProgressCallback | None) -> None:
    python = _pip_python()
    if python is None:
        raise RuntimeError("No Python installation with pip was found.")
    target.mkdir(parents=True, exist_ok=True)
    command = build_pip_update_command(python, target)
    if progress:
        progress({"percent": 10, "status": "Running pip to update yt-dlp..."})
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert process.stdout is not None
    for line in process.stdout:
        message = line.strip()
        if message and progress:
            progress({"percent": 50 if "Downloading" in message else 75, "status": message})
    return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f"pip could not update yt-dlp (exit code {return_code}).")


def _package_version(target: Path) -> str:
    version_file = target / "yt_dlp" / "version.py"
    text = version_file.read_text(encoding="utf-8")
    marker = "__version__ = "
    start = text.find(marker)
    if start < 0:
        return "unknown"
    return text[start + len(marker):].splitlines()[0].strip().strip("'\"")


def _activate_staged_package(staged: Path) -> Path:
    override = app_data_dir() / "yt_dlp_override"
    if override.exists():
        shutil.rmtree(override)
    shutil.move(str(staged), str(override))
    return override


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
    """Install a pip-managed yt-dlp override, with a verified wheel fallback."""
    if progress:
        progress({"percent": 0, "status": "Checking the latest yt-dlp release..."})
    pip_error = None
    with tempfile.TemporaryDirectory(prefix="musicxcst-ytdlp-") as temp_dir:
        temp_path = Path(temp_dir)
        pip_target = temp_path / "pip-target"
        try:
            _pip_install(pip_target, progress)
            version = _package_version(pip_target)
            _activate_staged_package(pip_target)
            if progress:
                progress({"percent": 100, "status": f"yt-dlp {version} installed with pip. Restart the app to activate it."})
            return {"version": version, "output": "pip package override installed"}
        except Exception as exc:
            pip_error = exc
            if progress:
                progress({"percent": 15, "status": f"pip unavailable ({exc}); using verified wheel fallback..."})

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
        _activate_staged_package(staged)

    if progress:
        suffix = f" (pip fallback: {pip_error})" if pip_error else ""
        progress({"percent": 100, "status": f"yt-dlp {version} installed with verified wheel{suffix}. Restart the app to activate it."})
    return {"version": version, "output": "verified package override installed"}
