from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .paths import default_download_dir, settings_path

ALLOWED_MODES = {"audio", "video", "video-audio"}
ALLOWED_FORMATS = {"mp3", "ogg", "wav", "flac", "m4a", "opus", "aac", "alac", "mp4", "mkv", "webm", "mov", "avi", "m4v", "ts"}
ALLOWED_AUDIO_QUALITIES = {"audio-best", "audio-small"}
ALLOWED_VIDEO_QUALITIES = {"best", "2160", "1440", "1080", "720", "480", "360"}
ALLOWED_FFMPEG_MODES = {"system", "custom", "managed"}
ALLOWED_UI_THEMES = {"classic", "aurora"}
ALLOWED_COOKIE_BROWSERS = {"auto", "chrome", "edge", "firefox", "brave", "chromium", "opera", "vivaldi"}


@dataclass
class Settings:
    default_output_folder: str = str(default_download_dir())
    default_mode: str = "audio"
    default_format: str = "mp3"
    default_quality: str = "audio-best"
    default_video_quality: str = "best"
    accent_color: str = "#56f0ff"
    ffmpeg_mode: str = "system"
    custom_ffmpeg_path: str = ""
    max_duration_warning_minutes: int = 60
    open_folder_after_download: bool = False
    logging_level: str = "INFO"
    first_run_confirmed: bool = False
    ui_theme: str = "classic"
    motion_enabled: bool = True
    show_start_screen: bool = True
    use_browser_cookies: bool = True
    browser_cookie_source: str = "auto"
    settings_version: int = 3


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or settings_path()
        self._lock = threading.RLock()

    def load(self) -> Settings:
        with self._lock:
            if not self.path.exists():
                return Settings()
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                allowed = {field: data.get(field) for field in Settings.__dataclass_fields__}
                return self._normalize(Settings(**{k: v for k, v in allowed.items() if v is not None}))
            except Exception:
                return Settings()

    def save(self, settings: Settings | dict[str, Any]) -> Settings:
        with self._lock:
            if isinstance(settings, dict):
                current = asdict(self.load())
                current.update({k: v for k, v in settings.items() if k in current})
                settings_obj = self._normalize(Settings(**current))
            else:
                settings_obj = self._normalize(settings)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
            temp_path.write_text(json.dumps(asdict(settings_obj), indent=2), encoding="utf-8")
            temp_path.replace(self.path)
            return settings_obj

    @staticmethod
    def _normalize(settings: Settings) -> Settings:
        if settings.default_mode not in ALLOWED_MODES:
            settings.default_mode = "audio"
        if settings.default_format not in ALLOWED_FORMATS:
            settings.default_format = "mp3"
        if settings.default_quality not in ALLOWED_AUDIO_QUALITIES:
            settings.default_quality = "audio-best"
        if settings.default_video_quality not in ALLOWED_VIDEO_QUALITIES:
            settings.default_video_quality = "best"
        if settings.ffmpeg_mode not in ALLOWED_FFMPEG_MODES:
            settings.ffmpeg_mode = "system"
        if settings.ui_theme not in ALLOWED_UI_THEMES:
            settings.ui_theme = "classic"
        if settings.browser_cookie_source not in ALLOWED_COOKIE_BROWSERS:
            settings.browser_cookie_source = "auto"
        settings.settings_version = 3
        return settings
