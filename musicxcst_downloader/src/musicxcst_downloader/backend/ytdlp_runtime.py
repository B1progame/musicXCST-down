from __future__ import annotations

import sys
import importlib.util
import re
import shutil
import subprocess

from .paths import app_data_dir


def available_js_runtime() -> tuple[str, str] | None:
    """Return the first supported JavaScript runtime visible to the app."""
    for name in ("deno", "node"):
        executable = shutil.which(name)
        if not executable:
            continue
        try:
            result = subprocess.run(
                [executable, "--version"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        match = re.search(r"\d+\.\d+(?:\.\d+)?", result.stdout or result.stderr or "")
        if result.returncode or not match:
            continue
        version = tuple(int(part) for part in match.group().split("."))
        minimum = (2, 3) if name == "deno" else (22, 0)
        if version >= minimum:
            return name, executable
    return None


def youtube_support_status() -> dict:
    has_ejs = importlib.util.find_spec("yt_dlp_ejs") is not None
    runtime = available_js_runtime()
    if not has_ejs:
        status = "YouTube challenge solver missing; use Update yt-dlp to install it."
    elif not runtime:
        status = "YouTube challenge solver ready; install Deno 2.3+ or Node.js 22+ for YouTube extraction."
    else:
        status = f"YouTube challenge solver and {runtime[0]} runtime ready."
    return {
        "ejs_installed": has_ejs,
        "js_runtime": runtime[0] if runtime else None,
        "js_runtime_path": runtime[1] if runtime else "",
        "ready": has_ejs and runtime is not None,
        "status": status,
    }


def activate_ytdlp_override() -> None:
    """Prefer the verified user-installed yt-dlp bundle before the packaged copy."""
    override = app_data_dir() / "yt_dlp_override"
    if override.exists() and str(override) not in sys.path:
        sys.path.insert(0, str(override))
