from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Callable


Log = Callable[[str], None]
APP_NAME = "MusicXCST Downloader"


def format_progress(percent: int) -> str:
    percent = max(0, min(100, int(percent)))
    filled = round(percent / 10)
    return f"[{'#' * filled}{'-' * (10 - filled)}] {percent}%"


def _safe_extract(payload: Path, staging: Path, log: Log) -> Path:
    root = staging / APP_NAME
    with zipfile.ZipFile(payload) as archive:
        members = archive.infolist()
        if not members:
            raise RuntimeError("Installer payload is empty.")
        last_percent = -1
        for index, member in enumerate(members, start=1):
            relative = Path(member.filename)
            if relative.is_absolute() or ".." in relative.parts:
                raise RuntimeError("Installer payload contains an unsafe path.")
            if not relative.parts or relative.parts[0] != APP_NAME:
                raise RuntimeError("Installer payload has an unexpected root folder.")
            destination = staging / relative
            if member.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target)
            percent = round(index / len(members) * 100)
            if percent != last_percent and (percent % 5 == 0 or percent == 100):
                log(f"Extracting {format_progress(percent)}")
                last_percent = percent
    if not (root / f"{APP_NAME}.exe").exists():
        raise RuntimeError("Installer payload does not contain the application executable.")
    log(f"Payload extracted: {len(members)} files")
    return root


def _copy_with_progress(source: Path, target: Path, log: Log) -> None:
    files = [path for path in source.rglob("*") if path.is_file()]
    last_percent = -1
    for index, source_file in enumerate(files, start=1):
        destination = target / source_file.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, destination)
        percent = round(index / len(files) * 100)
        if percent != last_percent and (percent % 5 == 0 or percent == 100):
            log(f"Installing {format_progress(percent)}")
            last_percent = percent


def install_payload(payload: Path, target: Path, log: Log = print) -> Path:
    """Install the staged app without touching %APPDATA% settings or history."""
    payload = Path(payload).resolve()
    target = Path(target).resolve()
    if not payload.is_file():
        raise FileNotFoundError(f"Payload not found: {payload}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="musicxcst-installer-") as temp_dir:
        staging = Path(temp_dir)
        app_root = _safe_extract(payload, staging, log)
        log(f"Installing to {target}")
        _copy_with_progress(app_root, target, log)
    log("Application files installed.")
    return target


def _payload_path() -> Path:
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return bundle_root / "payload.zip"


def _install_target() -> Path:
    local_app_data = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    return local_app_data / "Programs" / APP_NAME


def main() -> int:
    def log(message: str) -> None:
        print(f"[MusicXCST Installer] {message}", flush=True)

    print("=" * 62)
    print(f"  {APP_NAME} - automatic terminal installer")
    print("=" * 62)
    log("Starting unattended installation...")
    try:
        target = install_payload(_payload_path(), _install_target(), log)
        log("Settings and history were left untouched.")
        log("Launching the installed application...")
        subprocess.Popen([str(target / f"{APP_NAME}.exe")], close_fds=True)
        log("Done. The application is ready.")
        time.sleep(1.5)
        return 0
    except Exception as exc:
        log(f"ERROR: {exc}")
        time.sleep(2)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
