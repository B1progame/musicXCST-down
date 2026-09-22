from __future__ import annotations

import logging
import os
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
AUDIO_FORMATS = {"mp3", "ogg", "wav", "flac", "m4a", "opus", "aac", "alac"}
VIDEO_FORMATS = {"mp4", "mkv", "webm", "mov", "avi", "m4v", "ts"}
DOWNLOAD_MODES = {"audio", "video", "video-audio"}
VIDEO_QUALITIES = {"best", "2160", "1440", "1080", "720", "480", "360"}
ATMOS_AUDIO_CODECS = {"eac3", "ec3", "ec-3"}
COOKIE_BROWSERS = ("brave", "chrome", "edge", "firefox", "chromium", "opera", "vivaldi")


def _browser_cookie_data_exists(browser: str) -> bool:
    local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
    roaming_app_data = Path(os.environ.get("APPDATA", ""))
    locations = {
        "brave": (local_app_data / "BraveSoftware" / "Brave-Browser" / "User Data",),
        "chrome": (local_app_data / "Google" / "Chrome" / "User Data",),
        "edge": (local_app_data / "Microsoft" / "Edge" / "User Data",),
        "firefox": (roaming_app_data / "Mozilla" / "Firefox" / "Profiles",),
        "chromium": (local_app_data / "Chromium" / "User Data",),
        "opera": (roaming_app_data / "Opera Software" / "Opera Stable",),
        "vivaldi": (local_app_data / "Vivaldi" / "User Data",),
    }
    return any(path and path.exists() for path in locations.get(browser, ()))


def _browser_cookie_profiles(browser: str) -> tuple[str | None, ...]:
    local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
    roaming_app_data = Path(os.environ.get("APPDATA", ""))
    roots = {
        "brave": (local_app_data / "BraveSoftware" / "Brave-Browser" / "User Data",),
        "chrome": (local_app_data / "Google" / "Chrome" / "User Data",),
        "edge": (local_app_data / "Microsoft" / "Edge" / "User Data",),
        "firefox": (roaming_app_data / "Mozilla" / "Firefox" / "Profiles",),
        "chromium": (local_app_data / "Chromium" / "User Data",),
        "opera": (roaming_app_data / "Opera Software" / "Opera Stable",),
        "vivaldi": (local_app_data / "Vivaldi" / "User Data",),
    }.get(browser, ())
    profiles: list[str] = []
    for root in roots:
        if not root.exists():
            continue
        if browser == "firefox":
            profiles.extend(path.name for path in root.iterdir() if path.is_dir() and (path / "cookies.sqlite").exists())
        else:
            profiles.extend(
                path.name
                for path in root.iterdir()
                if path.is_dir() and ((path / "Cookies").exists() or (path / "Network" / "Cookies").exists())
            )
    return tuple(dict.fromkeys(profiles)) or (None,) if _browser_cookie_data_exists(browser) else ()


def cookie_browser_candidates(source: str = "auto") -> tuple[str, ...]:
    source = str(source or "auto").lower()
    if source != "auto":
        return (source,)
    detected = tuple(browser for browser in COOKIE_BROWSERS if _browser_cookie_data_exists(browser))
    return detected or COOKIE_BROWSERS


def _cookie_attempts(source: str = "auto") -> tuple[tuple[str, str | None], ...]:
    browsers = cookie_browser_candidates(source)
    attempts = []
    for browser in browsers:
        profiles = _browser_cookie_profiles(browser)
        if not profiles and str(source or "auto").lower() != "auto":
            profiles = (None,)
        attempts.extend((browser, profile) for profile in profiles)
    return tuple(attempts)


def _with_browser_cookies(options: dict, browser: str, profile: str | None = None) -> dict:
    cookie_options = dict(options)
    cookie_options["cookiesfrombrowser"] = (browser, profile) if profile else (browser,)
    return cookie_options


def _with_cookie_file(options: dict, cookie_file_path: str) -> dict:
    cookie_options = dict(options)
    cookie_options["cookiefile"] = str(Path(cookie_file_path).expanduser())
    return cookie_options


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


def format_bytes(size: int | float | None) -> str:
    if not size:
        return ""
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return ""


def format_supports_dolby_atmos(fmt: dict) -> bool:
    searchable = " ".join(
        str(fmt.get(key) or "")
        for key in (
            "acodec",
            "format",
            "format_id",
            "format_note",
            "format_name",
            "audio_ext",
            "dynamic_range",
            "audio_channels",
            "language",
        )
    ).lower()
    codec = re.sub(r"[^a-z0-9]+", "", str(fmt.get("acodec") or "").lower())
    return "atmos" in searchable or "dolby atmos" in searchable or codec in ATMOS_AUDIO_CODECS


def _best_formats(formats: list[dict]) -> dict:
    audios = [f for f in formats if f.get("acodec") not in (None, "none")]
    videos = [f for f in formats if f.get("vcodec") not in (None, "none")]
    best_audio = max(audios, key=lambda f: f.get("abr") or f.get("tbr") or 0, default={})
    best_video = max(
        videos,
        key=lambda f: (f.get("height") or 0, f.get("fps") or 0, f.get("tbr") or 0),
        default={},
    )
    best_video_height = best_video.get("height") or 0
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
        "best_audio_filesize": format_bytes(best_audio.get("filesize") or best_audio.get("filesize_approx")),
        "dolby_atmos": "Yes" if any(format_supports_dolby_atmos(f) for f in audios) else "No",
        "best_video_quality": f"{best_video_height}p" if best_video_height else "Unknown",
        "best_video_height": best_video_height,
        "best_video_width": best_video.get("width") or "",
        "best_video_fps": best_video.get("fps") or "",
        "best_video_codec": best_video.get("vcodec") or "Unknown",
        "best_video_bitrate": best_video.get("vbr") or best_video.get("tbr") or "",
        "best_video_filesize": best_video.get("filesize") or best_video.get("filesize_approx") or "",
        "best_video_size": format_bytes(best_video.get("filesize") or best_video.get("filesize_approx")),
        "video_formats_count": len(videos),
        "audio_formats_count": len(audios),
    }


def analyze_url(url: str, max_duration_warning_minutes: int = 60, use_browser_cookies: bool = False, browser_cookie_source: str = "auto", cookie_file_path: str = "") -> dict:
    if not validate_url(url):
        raise ValueError("Enter a valid http or https URL.")
    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "extract_flat": False,
    }
    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as first_error:
        if not use_browser_cookies and not cookie_file_path:
            raise
        last_error = first_error
        failures = []
        cookie_attempts = _cookie_attempts(browser_cookie_source) if use_browser_cookies else ()
        for browser, profile in cookie_attempts:
            label = f"{browser}/{profile}" if profile else browser
            LOGGER.info("Analysis failed; retrying with %s browser cookies", label)
            try:
                with YoutubeDL(_with_browser_cookies(options, browser, profile)) as ydl:
                    info = ydl.extract_info(url, download=False)
                break
            except Exception as cookie_error:
                last_error = cookie_error
                failures.append(f"{label}: {cookie_error}")
                LOGGER.debug("Browser cookie analysis retry failed for %s", browser, exc_info=True)
        else:
            cookie_file = str(cookie_file_path or "").strip()
            if cookie_file and Path(cookie_file).is_file():
                try:
                    with YoutubeDL(_with_cookie_file(options, cookie_file)) as ydl:
                        info = ydl.extract_info(url, download=False)
                except Exception as cookie_file_error:
                    last_error = cookie_file_error
                    failures.append(f"cookie file: {cookie_file_error}")
                else:
                    failures = []
            if failures or not cookie_file:
                raise RuntimeError(f"{last_error} Cookie attempts: {'; '.join(failures) or 'none detected'}.") from first_error
    formats = info.get("formats") or []
    audio_formats = [f for f in formats if f.get("acodec") not in (None, "none")]
    video_formats = [f for f in formats if f.get("vcodec") not in (None, "none")]
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
                "vcodec": f.get("vcodec"),
                "kind": "video" if f.get("vcodec") not in (None, "none") else "audio",
                "width": f.get("width") or "",
                "height": f.get("height") or "",
                "fps": f.get("fps") or "",
                "filesize": f.get("filesize") or f.get("filesize_approx") or "",
                "tbr": f.get("tbr"),
                "asr": f.get("asr"),
                "dolby_atmos": format_supports_dolby_atmos(f),
            }
            for f in sorted(audio_formats + video_formats, key=lambda item: (item.get("height") or 0, item.get("tbr") or 0), reverse=True)[:120]
        ],
        "formats_count": len(formats),
        "long_warning": bool(duration and duration > max_duration_warning_minutes * 60),
        **best,
    }


def build_format_selector(fmt: str, quality: str, mode: str = "audio") -> str:
    if mode not in DOWNLOAD_MODES:
        raise ValueError(f"Unsupported download mode: {mode}")
    if mode == "audio":
        if fmt not in AUDIO_FORMATS:
            raise ValueError(f"Unsupported audio format: {fmt}")
        return "bestaudio/best"
    if fmt not in VIDEO_FORMATS:
        raise ValueError(f"Unsupported video format: {fmt}")
    if quality not in VIDEO_QUALITIES:
        raise ValueError(f"Unsupported video quality: {quality}")
    limit = "" if quality == "best" else f"[height<={quality}]"
    if mode == "video":
        return f"bestvideo{limit}/bestvideo/best"
    return f"bestvideo{limit}+bestaudio/best{limit}"


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
        mode = request.get("mode", "audio")
        fmt = request.get("format", "mp3" if mode == "audio" else "mp4")
        quality = request.get("quality", "audio-best" if mode == "audio" else "best")
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
                if now - last_progress_emit < 0.8 and abs(percent - last_percent) < 2:
                    return
                last_progress_emit = now
                last_percent = percent
                downloaded_text = format_bytes(downloaded)
                total_text = format_bytes(total)
                self.progress(
                    {
                        "type": "progress",
                        "percent": round(percent, 1),
                        "speed": event.get("_speed_str", "").strip(),
                        "eta": event.get("_eta_str", "").strip(),
                        "status": "Downloading...",
                        "stage": "Downloading audio",
                        "downloaded": downloaded_text,
                        "total": total_text,
                        "detail": f"{downloaded_text} / {total_text}" if downloaded_text and total_text else downloaded_text,
                    }
                )
            elif event.get("status") == "finished":
                self.progress(
                    {
                        "type": "progress",
                        "percent": 96,
                        "status": "Download finished. Preparing conversion...",
                        "stage": "Preparing conversion",
                    }
                )

        def postprocessor_hook(event: dict) -> None:
            status = event.get("status")
            processor = event.get("postprocessor") or "FFmpeg"
            if status == "started":
                self.progress(
                    {
                        "type": "progress",
                        "percent": 97,
                        "status": f"{processor} started...",
                        "stage": "Converting audio",
                    }
                )
            elif status == "processing":
                self.progress(
                    {
                        "type": "progress",
                        "percent": 98,
                        "status": f"{processor} processing...",
                        "stage": "Converting audio",
                    }
                )
            elif status == "finished":
                self.progress(
                    {
                        "type": "progress",
                        "percent": 99,
                        "status": f"{processor} finished.",
                        "stage": "Finalizing file",
                    }
                )

        options = {
            "format": build_format_selector(fmt, quality, mode),
            "outtmpl": str(target.with_suffix(".%(ext)s")),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "restrictfilenames": False,
            "progress_hooks": [hook],
            "postprocessor_hooks": [postprocessor_hook],
            "ffmpeg_location": str(Path(ffmpeg_info["ffmpeg_path"]).parent),
            "postprocessors": [],
            "postprocessor_args": [],
            "keepvideo": mode == "video",
        }
        if mode == "audio":
            options["postprocessors"].append(
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "aac" if fmt == "m4a" else fmt,
                    "preferredquality": "0" if quality != "audio-small" else "5",
                }
            )
        else:
            options["merge_output_format"] = fmt
            options["postprocessors"].append({"key": "FFmpegVideoRemuxer", "preferedformat": fmt})

        LOGGER.info("Starting download for %s", url)
        self.progress({"type": "terminal", "line": f"Starting {mode} download as {fmt} ({quality})."})
        self.progress({"type": "progress", "percent": 0, "status": "Starting download...", "stage": "Starting"})
        try:
            with YoutubeDL(options) as ydl:
                ydl.download([url])
        except Exception as first_error:
            if not request.get("use_browser_cookies"):
                raise
            last_error = first_error
            failures = []
            for browser, profile in _cookie_attempts(request.get("browser_cookie_source", "auto")):
                label = f"{browser}/{profile}" if profile else browser
                self.progress({"type": "terminal", "line": f"Retrying with {label} browser cookies..."})
                try:
                    with YoutubeDL(_with_browser_cookies(options, browser, profile)) as ydl:
                        ydl.download([url])
                    break
                except Exception as cookie_error:
                    last_error = cookie_error
                    failures.append(f"{label}: {cookie_error}")
                    LOGGER.debug("Browser cookie download retry failed for %s", browser, exc_info=True)
            else:
                cookie_file = str(request.get("cookie_file_path") or "").strip()
                if cookie_file and Path(cookie_file).is_file():
                    try:
                        with YoutubeDL(_with_cookie_file(options, cookie_file)) as ydl:
                            ydl.download([url])
                    except Exception as cookie_file_error:
                        last_error = cookie_file_error
                        failures.append(f"cookie file: {cookie_file_error}")
                    else:
                        failures = []
                if failures or not cookie_file:
                    raise RuntimeError(f"{last_error} Cookie attempts: {'; '.join(failures) or 'none detected'}.") from first_error
        self.progress(
            {
                "type": "complete",
                "percent": 100,
                "status": "Download complete",
                "output_path": str(target),
            }
        )
