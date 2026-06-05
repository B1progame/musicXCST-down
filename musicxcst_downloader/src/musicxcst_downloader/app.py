from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import asdict
from pathlib import Path

import webview
from .backend.downloader import DownloadWorker, analyze_url, output_filename_from_title, validate_url
from .backend.external import open_external_url
from .backend.ffmpeg import probe
from .backend.history import HistoryItem, HistoryStore
from .backend.legal import FIRST_RUN_NOTICE, can_download
from .backend.logging_setup import configure_logging
from .backend.managed_ffmpeg import download_managed_ffmpeg
from .backend.paths import frontend_index
from .backend.settings import Settings, SettingsStore

LOGGER = logging.getLogger(__name__)


class Api:
    def __init__(self) -> None:
        self.window: webview.Window | None = None
        self.settings_store = SettingsStore()
        self.history_store = HistoryStore()
        self.settings = self.settings_store.load()
        configure_logging(self.settings.logging_level)
        self.worker = DownloadWorker(self._emit)
        self.last_analysis: dict | None = None
        self.ffmpeg_download_running = False
        self.emit_lock = threading.Lock()

    def bind_window(self, window: webview.Window) -> None:
        self.window = window

    def _emit(self, event: dict) -> None:
        if not self.window:
            return
        payload = json.dumps(event, separators=(",", ":"))
        with self.emit_lock:
            try:
                self.window.evaluate_js(f"window.MusicXCST.receiveEvent({payload})")
            except Exception:
                LOGGER.exception("Could not emit UI event")

    def startup(self) -> dict:
        return {
            "settings": asdict(self.settings),
            "history": self.history_store.load(),
            "legalNotice": FIRST_RUN_NOTICE,
            "ffmpeg": probe(self.settings.ffmpeg_mode, self.settings.custom_ffmpeg_path),
        }

    def save_settings(self, patch: dict) -> dict:
        self.settings = self.settings_store.save(patch)
        configure_logging(self.settings.logging_level)
        return asdict(self.settings)

    def reset_settings(self) -> dict:
        self.settings = self.settings_store.save(Settings())
        return asdict(self.settings)

    def choose_output_folder(self) -> str:
        if not self.window:
            return ""
        result = self.window.create_file_dialog(webview.FOLDER_DIALOG)
        return result[0] if result else ""

    def select_ffmpeg(self) -> str:
        if not self.window:
            return ""
        result = self.window.create_file_dialog(
            webview.OPEN_DIALOG,
            file_types=("FFmpeg executable (*.exe)", "All files (*.*)"),
        )
        return result[0] if result else ""

    def test_ffmpeg(self, mode: str | None = None, custom_path: str | None = None) -> dict:
        return probe(mode or self.settings.ffmpeg_mode, custom_path or self.settings.custom_ffmpeg_path)

    def download_managed_ffmpeg(self) -> dict:
        if self.ffmpeg_download_running:
            return {"ok": False, "error": "FFmpeg download is already running."}

        def run() -> None:
            self.ffmpeg_download_running = True
            try:
                result = download_managed_ffmpeg(self._emit)
                self.settings = self.settings_store.save({"ffmpeg_mode": "managed"})
                ffmpeg_status = probe(self.settings.ffmpeg_mode, self.settings.custom_ffmpeg_path)
                self._emit({"type": "settings", "settings": asdict(self.settings)})
                self._emit({"type": "ffmpeg", "status": ffmpeg_status})
                self._emit({"type": "ffmpeg_download", "ok": True, "status": result["license"], "percent": 100})
            except Exception as exc:
                LOGGER.exception("Managed FFmpeg download failed")
                self._emit({"type": "ffmpeg_download", "ok": False, "status": str(exc), "percent": 0})
            finally:
                self.ffmpeg_download_running = False

        threading.Thread(target=run, daemon=True).start()
        return {"ok": True, "status": "FFmpeg download started"}

    def analyze(self, url: str) -> dict:
        if not validate_url(url):
            return {"ok": False, "error": "Enter a valid http or https URL."}

        def run() -> None:
            try:
                self._emit({"type": "analyze_status", "status": "Analyzing link..."})
                info = analyze_url(url, self.settings.max_duration_warning_minutes)
                self.last_analysis = info
                default_ext = self.settings.default_format
                info["suggested_filename"] = output_filename_from_title(info["safe_filename"], default_ext)
                self._emit({"type": "analysis", "ok": True, "data": info})
            except Exception as exc:
                LOGGER.exception("Analyze failed")
                self._emit({"type": "analysis", "ok": False, "error": str(exc)})

        threading.Thread(target=run, daemon=True).start()
        return {"ok": True, "status": "Analysis started"}

    def download(self, request: dict) -> dict:
        if not can_download(bool(request.get("legal_confirmed"))):
            return {"ok": False, "error": "Confirm that you have the right to download this content first."}
        if not validate_url(request.get("url", "")):
            return {"ok": False, "error": "Enter a valid http or https URL."}
        if self.worker.running:
            return {"ok": False, "error": "A download is already running."}

        title = (self.last_analysis or {}).get("title") or request.get("filename") or "Download"

        def progress(event: dict) -> None:
            self._emit(event)
            if event.get("type") in {"complete", "error"}:
                status = "success" if event.get("type") == "complete" else "failed"
                output_path = event.get("output_path") or request.get("output_folder", "")
                items = self.history_store.add(
                    HistoryItem.now(
                        title=title,
                        source_url=request["url"],
                        selected_format=request.get("format", ""),
                        output_path=output_path,
                        status=status,
                    )
                )
                self._emit({"type": "history", "items": items})
                if status == "success" and self.settings.open_folder_after_download:
                    self.open_folder(output_path)

        self.worker.progress = progress
        try:
            self.worker.start(request, self.settings.ffmpeg_mode, self.settings.custom_ffmpeg_path)
            return {"ok": True, "status": "Download started"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def cancel_download(self) -> dict:
        if self.worker.running:
            self.worker.cancel()
            return {"ok": True}
        return {"ok": False, "error": "No active download."}

    def open_folder(self, path: str) -> dict:
        try:
            target = Path(path)
            folder = target if target.is_dir() else target.parent
            os.startfile(folder)  # type: ignore[attr-defined]
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def open_external_url(self, url: str) -> dict:
        return open_external_url(url)

    def remove_history(self, index: int) -> list[dict]:
        return self.history_store.remove(index)

    def clear_history(self) -> list[dict]:
        self.history_store.clear()
        return []


def main() -> None:
    api = Api()
    window = webview.create_window(
        "MusicXCST Downloader",
        url=frontend_index().as_uri(),
        js_api=api,
        width=1323,
        height=960,
        min_size=(860, 560),
        background_color="#080a0f",
    )
    api.bind_window(window)
    webview.start(debug=False)


if __name__ == "__main__":
    main()
