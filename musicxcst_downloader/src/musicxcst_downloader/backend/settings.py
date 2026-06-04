from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .paths import default_download_dir, settings_path


@dataclass
class Settings:
    default_output_folder: str = str(default_download_dir())
    default_format: str = "mp4"
    default_quality: str = "best"
    accent_color: str = "#56f0ff"
    ffmpeg_mode: str = "system"
    custom_ffmpeg_path: str = ""
    max_duration_warning_minutes: int = 60
    open_folder_after_download: bool = False
    keep_temporary_original: bool = False
    logging_level: str = "INFO"
    first_run_confirmed: bool = False


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or settings_path()

    def load(self) -> Settings:
        if not self.path.exists():
            return Settings()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            allowed = {field: data.get(field) for field in Settings.__dataclass_fields__}
            return Settings(**{k: v for k, v in allowed.items() if v is not None})
        except Exception:
            return Settings()

    def save(self, settings: Settings | dict[str, Any]) -> Settings:
        if isinstance(settings, dict):
            current = asdict(self.load())
            current.update({k: v for k, v in settings.items() if k in current})
            settings_obj = Settings(**current)
        else:
            settings_obj = settings
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(asdict(settings_obj), indent=2), encoding="utf-8")
        return settings_obj

