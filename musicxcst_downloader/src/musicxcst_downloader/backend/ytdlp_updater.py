from __future__ import annotations

import subprocess
import sys

from yt_dlp.version import __version__


def installed_ytdlp_version() -> str:
    return __version__


def update_ytdlp() -> dict:
    """Update yt-dlp in the Python environment used by this app."""
    completed = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    output = (completed.stdout or completed.stderr or "").strip()
    if completed.returncode != 0:
        raise RuntimeError(output or "yt-dlp update failed.")

    version_check = subprocess.run(
        [sys.executable, "-c", "from yt_dlp.version import __version__; print(__version__)"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    version = version_check.stdout.strip() if version_check.returncode == 0 else installed_ytdlp_version()
    return {"version": version, "output": output}
