from __future__ import annotations

import logging
import re
import threading
import time
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from yt_dlp import YoutubeDL

from .ffmpeg import probe

LOGGER = logging.getLogger(__name__)
ProgressCallback = Callable[[dict], None]

INVALID_FILENAME_CHARS = r'<>:"/\\|?*\x00-\x1f'
AUDIO_FORMATS = {"mp3", "ogg", "wav", "flac", "m4a"}


def validate_url(url: str) -> bool:
    try:
        parsed = urlparse(url.strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def sanitize_filename(name: str, fallback: str = "download") -> str:
    cleaned = re.sub(f"[{INVALID_FILENAME_CHARS}]", "_", name).strip(" ._")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return (cleaned[:180].strip() or fallback)


def output_filename_from_title(title: str, extension: str) -> str:
    return f"{sanitize_filename(title)}.{extension.lstrip('.')}"


def format_duration(seconds: int | float | None) -> str:
    if not seconds:
        return "Unknown"
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, sec = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{sec:02d}"
    return f"{minutes}:{sec:02d}"


def _best_formats(formats: list[dict]) -> dict:
    audios = [f for f in formats if f.get("acodec") not in (None, "none")]
    best_audio = max(audios, key=lambda f: f.get("abr") or f.get("tbr") or 0, default={})
    return {
        "best_audio_quality": (
            f"{round(best_audio.get('abr') or best_audio.get('tbr'))} kbps"
            if (best_audio.get("abr") or best_audio.get("tbr"))
            else "Unknown"
        ),
        "audio_codec": best_audio.get("acodec") or "Unknown",
        "audio_bitrate": best_audio.get("abr") or best_audio.get("tbr") or "",
        "audio_sample_rate": best_audio.get("asr") or "",
        "audio_channels": best_audio.get("audio_channels") or "",
    }


def analyze_url(url: str, max_duration_warning_minutes: int = 60) -> dict:
    if not validate_url(url):
        raise ValueError("Enter a valid http or https URL.")
    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "extract_flat": False,
    }
    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=False)
    formats = info.get("formats") or []
    audio_formats = [f for f in formats if f.get("acodec") not in (None, "none")]
    best = _best_formats(formats)
    duration = info.get("duration")
    return {
        "title": info.get("title") or "Untitled",
        "uploader": info.get("uploader") or info.get("channel") or "Unknown",
        "duration": format_duration(duration),
        "duration_seconds": duration or 0,
        "thumbnail": info.get("thumbnail") or "",
        "webpage_url": info.get("webpage_url") or url,
        "safe_filename": sanitize_filename(info.get("title") or "download"),
        "available_formats": [
            {
                "format_id": f.get("format_id"),
                "ext": f.get("ext"),
                "acodec": f.get("acodec"),
                "tbr": f.get("tbr"),
                "asr": f.get("asr"),
            }
            for f in audio_formats[:80]
        ],
        "long_warning": bool(duration and duration > max_duration_warning_minutes * 60),
        **best,
    }


def build_format_selector(fmt: str, quality: str) -> str:
    if fmt not in AUDIO_FORMATS:
        raise ValueError(f"Unsupported audio format: {fmt}")
    return "bestaudio/best"


class DownloadWorker:
    def __init__(self, progress: ProgressCallback) -> None:
        self.progress = progress
        self._thread: threading.Thread | None = None
        self._cancel = threading.Event()

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def cancel(self) -> None:
        self._cancel.set()
        self.progress({"type": "status", "status": "Cancel requested..."})

    def start(self, request: dict, ffmpeg_mode: str = "system", custom_ffmpeg_path: str = "") -> None:
        if self.running:
            raise RuntimeError("A download is already running.")
        self._cancel.clear()
        self._thread = threading.Thread(
            target=self._run,
            args=(request, ffmpeg_mode, custom_ffmpeg_path),
            daemon=True,
        )
        self._thread.start()

    def _run(self, request: dict, ffmpeg_mode: str, custom_ffmpeg_path: str) -> None:
        try:
            self._download(request, ffmpeg_mode, custom_ffmpeg_path)
        except Exception as exc:
            LOGGER.exception("Download failed")
            self.progress({"type": "error", "message": str(exc)})

    def _download(self, request: dict, ffmpeg_mode: str, custom_ffmpeg_path: str) -> None:
        url = request["url"]
        fmt = request.get("format", "mp3")
        quality = request.get("quality", "audio-best")
        output_dir = Path(request["output_folder"]).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = sanitize_filename(request.get("filename") or "download")
        if not Path(filename).suffix:
            filename = f"{filename}.{fmt}"
        target = output_dir / filename
        if target.exists() and not request.get("overwrite"):
            raise FileExistsError(f"{target.name} already exists. Rename it or confirm overwrite.")

        ffmpeg_info = probe(ffmpeg_mode, custom_ffmpeg_path)
        if not ffmpeg_info["ready"]:
            raise RuntimeError("FFmpeg and ffprobe are required for reliable downloads and conversions.")

        last_progress_emit = 0.0
        last_percent = -1.0

        def hook(event: dict) -> None:
            nonlocal last_progress_emit, last_percent
            if self._cancel.is_set():
                raise RuntimeError("Download cancelled.")
            if event.get("status") == "downloading":
                total = event.get("total_bytes") or event.get("total_bytes_estimate") or 0
                downloaded = event.get("downloaded_bytes") or 0
                percent = (downloaded / total * 100) if total else 0
                now = time.monotonic()
                if now - last_progress_emit < 0.25 and abs(percent - last_percent) < 1:
                    return
                last_progress_emit = now
                last_percent = percent
                self.progress(
                    {
                        "type": "progress",
                        "percent": round(percent, 1),
                        "speed": event.get("_speed_str", "").strip(),
                        "eta": event.get("_eta_str", "").strip(),
                        "status": "Downloading...",
                    }
                )
            elif event.get("status") == "finished":
                self.progress({"type": "progress", "percent": 96, "status": "Converting/merging..."})

        options = {
            "format": build_format_selector(fmt, quality),
            "outtmpl": str(target.with_suffix(".%(ext)s")),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "restrictfilenames": False,
            "progress_hooks": [hook],
            "ffmpeg_location": str(Path(ffmpeg_info["ffmpeg_path"]).parent),
            "postprocessors": [],
            "postprocessor_args": [],
            "keepvideo": False,
        }
        options["postprocessors"].append(
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "aac" if fmt == "m4a" else fmt,
                "preferredquality": "0" if quality != "audio-small" else "5",
            }
        )

        LOGGER.info("Starting download for %s", url)
        self.progress({"type": "status", "status": "Starting download..."})
        with YoutubeDL(options) as ydl:
            ydl.download([url])
        self.progress(
            {
                "type": "complete",
                "percent": 100,
                "status": "Download complete",
                "output_path": str(target),
            }
        )
