from __future__ import annotations

import subprocess
from pathlib import Path
from shutil import which


def _bin_name(name: str) -> str:
    return f"{name}.exe"


def resolve_binary(name: str, custom_ffmpeg_path: str = "", mode: str = "system") -> str | None:
    if mode == "custom" and custom_ffmpeg_path:
        custom = Path(custom_ffmpeg_path)
        if custom.is_dir():
            candidate = custom / _bin_name(name)
        else:
            candidate = custom.with_name(_bin_name(name)) if custom.name.lower() == "ffmpeg.exe" else custom
        return str(candidate) if candidate.exists() else None
    return which(name)


def get_version(binary: str | None) -> str:
    if not binary:
        return "Not found"
    try:
        result = subprocess.run(
            [binary, "-version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        first_line = (result.stdout or result.stderr).splitlines()[0]
        return first_line.strip() if first_line else "Unknown version"
    except Exception as exc:
        return f"Error: {exc}"


def probe(mode: str = "system", custom_ffmpeg_path: str = "") -> dict:
    ffmpeg = resolve_binary("ffmpeg", custom_ffmpeg_path, mode)
    ffprobe = resolve_binary("ffprobe", custom_ffmpeg_path, mode)
    return {
        "ffmpeg_path": ffmpeg or "",
        "ffprobe_path": ffprobe or "",
        "ffmpeg_version": get_version(ffmpeg),
        "ffprobe_version": get_version(ffprobe),
        "ready": bool(ffmpeg and ffprobe),
    }

