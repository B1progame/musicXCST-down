from __future__ import annotations

import os
from pathlib import Path


APP_NAME = "MusicXCST Downloader"


def app_data_dir() -> Path:
    base = os.environ.get("APPDATA")
    if base:
        root = Path(base)
    else:
        root = Path.home() / "AppData" / "Roaming"
    path = root / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def logs_dir() -> Path:
    path = app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_download_dir() -> Path:
    downloads = Path.home() / "Downloads"
    return downloads if downloads.exists() else Path.home()


def settings_path() -> Path:
    return app_data_dir() / "settings.json"


def managed_ffmpeg_dir() -> Path:
    return app_data_dir() / "ffmpeg"


def history_path() -> Path:
    return app_data_dir() / "history.json"


def browser_storage_dir() -> Path:
    path = app_data_dir() / "browser"
    path.mkdir(parents=True, exist_ok=True)
    return path


def frontend_index() -> Path:
    return Path(__file__).resolve().parents[1] / "frontend" / "index.html"
