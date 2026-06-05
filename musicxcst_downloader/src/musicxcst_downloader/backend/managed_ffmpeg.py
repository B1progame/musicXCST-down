from __future__ import annotations

import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

from .paths import managed_ffmpeg_dir

FFMPEG_DOWNLOAD_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
FFMPEG_SOURCE_PAGE = "https://www.gyan.dev/ffmpeg/builds/"
FFMPEG_LICENSE_LABEL = "LGPLv3 essentials build"

ProgressCallback = Callable[[dict], None]


def extract_managed_ffmpeg(zip_path: Path, target_dir: Path | None = None) -> Path:
    target = target_dir or managed_ffmpeg_dir()
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="musicxcst-ffmpeg-", dir=str(target.parent)))
    try:
        bin_dir = staging / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        found = set()
        with zipfile.ZipFile(zip_path) as archive:
            for member in archive.infolist():
                name = Path(member.filename.replace("\\", "/")).name.lower()
                if name not in {"ffmpeg.exe", "ffprobe.exe"}:
                    continue
                with archive.open(member) as source, (bin_dir / name).open("wb") as destination:
                    shutil.copyfileobj(source, destination)
                found.add(name)
        missing = {"ffmpeg.exe", "ffprobe.exe"} - found
        if missing:
            raise RuntimeError(f"FFmpeg download did not contain: {', '.join(sorted(missing))}")
        if target.exists():
            shutil.rmtree(target)
        staging.replace(target)
        return target / "bin" / "ffmpeg.exe"
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def download_managed_ffmpeg(progress: ProgressCallback | None = None) -> dict:
    target = managed_ffmpeg_dir()
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix="musicxcst-ffmpeg-", suffix=".zip", delete=False) as temp_file:
        zip_path = Path(temp_file.name)
    try:
        if progress:
            progress({"type": "ffmpeg_download", "status": "Downloading app-managed FFmpeg...", "percent": 0})
        request = urllib.request.Request(FFMPEG_DOWNLOAD_URL, headers={"User-Agent": "MusicXCST Downloader"})
        with urllib.request.urlopen(request, timeout=30) as response, zip_path.open("wb") as output:
            total = int(response.headers.get("Content-Length") or 0)
            downloaded = 0
            while True:
                chunk = response.read(1024 * 256)
                if not chunk:
                    break
                output.write(chunk)
                downloaded += len(chunk)
                if progress and total:
                    progress(
                        {
                            "type": "ffmpeg_download",
                            "status": "Downloading app-managed FFmpeg...",
                            "percent": round(downloaded / total * 100, 1),
                        }
                    )
        if progress:
            progress({"type": "ffmpeg_download", "status": "Installing app-managed FFmpeg...", "percent": 96})
        ffmpeg_path = extract_managed_ffmpeg(zip_path, target)
        if progress:
            progress({"type": "ffmpeg_download", "status": "App-managed FFmpeg ready.", "percent": 100})
        return {
            "ok": True,
            "ffmpeg_path": str(ffmpeg_path),
            "install_dir": str(target),
            "source_url": FFMPEG_DOWNLOAD_URL,
            "source_page": FFMPEG_SOURCE_PAGE,
            "license": FFMPEG_LICENSE_LABEL,
        }
    finally:
        zip_path.unlink(missing_ok=True)
