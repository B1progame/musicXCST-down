from __future__ import annotations

import sys

from .paths import app_data_dir


def activate_ytdlp_override() -> None:
    """Prefer the verified user-installed yt-dlp bundle before the packaged copy."""
    override = app_data_dir() / "yt_dlp_override"
    if override.exists() and str(override) not in sys.path:
        sys.path.insert(0, str(override))
