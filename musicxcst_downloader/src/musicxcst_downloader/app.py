from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlparse

import webview
from . import __version__
from .backend.app_updater import check_for_update, download_and_launch_update, update_event
from .backend.ytdlp_runtime import activate_ytdlp_override

activate_ytdlp_override()

from .backend.downloader import DownloadWorker, analyze_url, output_filename_from_title, validate_url
from .backend.browser import BROWSER_HOME, normalize_browser_url
from .backend.external import open_external_url
from .backend.ffmpeg import probe
from .backend.history import HistoryItem, HistoryStore
from .backend.legal import FIRST_RUN_NOTICE, can_download
from .backend.logging_setup import configure_logging
from .backend.managed_ffmpeg import download_managed_ffmpeg
from .backend.paths import browser_storage_dir, frontend_index
from .backend.settings import Settings, SettingsStore
from .backend.ytdlp_updater import check_ytdlp_update, installed_ytdlp_version, update_ytdlp

LOGGER = logging.getLogger(__name__)


def restart_application() -> None:
    """Start the current app again, preserving the packaged or development entrypoint."""
    command = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, *sys.argv]
    subprocess.Popen(command, close_fds=True)


class Api:
    _BRIDGE_METHODS = {
        "startup",
        "save_settings",
        "reset_settings",
        "choose_output_folder",
        "choose_default_output_folder",
        "select_ffmpeg",
        "select_cookie_file",
        "test_ffmpeg",
        "download_managed_ffmpeg",
        "update_ytdlp",
        "check_app_update",
        "update_app",
        "analyze",
        "download",
        "cancel_download",
        "open_folder",
        "open_external_url",
        "browser_open",
        "browser_home",
        "browser_back",
        "browser_forward",
        "browser_reload",
        "browser_stop",
        "browser_zoom",
        "browser_find",
        "browser_copy_url",
        "browser_open_external",
        "browser_layout",
        "browser_current_url",
        "browser_send_current_to_download",
        "remove_history",
        "clear_history",
    }

    def __init__(self) -> None:
        self._window: webview.Window | None = None
        self._settings_store = SettingsStore()
        self._history_store = HistoryStore()
        self._settings = self._settings_store.load()
        configure_logging(self._settings.logging_level)
        self._worker = DownloadWorker(self._emit)
        self._last_analysis: dict | None = None
        self._ffmpeg_download_running = False
        self._ytdlp_update_running = False
        self._emit_lock = threading.Lock()
        self._browser_control = None
        self._browser_creating = False
        self._browser_ready = False
        self._browser_pending_url = BROWSER_HOME
        self._browser_url = ""
        self._browser_zoom_factor = 1.0

    def bind_window(self, window: webview.Window) -> None:
        self._window = window

    def invoke(self, method: str, args: list | None = None):
        """Stable JS bridge entry point used across packaged app upgrades."""
        if method not in self._BRIDGE_METHODS:
            raise ValueError(f"Unknown API method: {method}")
        target = getattr(self, method)
        return target(*(args or []))

    def _emit(self, event: dict) -> None:
        if not self._window:
            return
        payload = json.dumps(event, separators=(",", ":"))
        with self._emit_lock:
            try:
                self._window.evaluate_js(f"window.MusicXCST.receiveEvent({payload})")
            except Exception:
                LOGGER.exception("Could not emit UI event")

    def startup(self) -> dict:
        ytdlp_version = installed_ytdlp_version()
        return {
            "appVersion": __version__,
            "settings": asdict(self._settings),
            "history": self._history_store.load(),
            "legalNotice": FIRST_RUN_NOTICE,
            "ffmpeg": probe(self._settings.ffmpeg_mode, self._settings.custom_ffmpeg_path),
            "ytdlp": {
                "version": ytdlp_version,
                "current_version": ytdlp_version,
                "latest_version": None,
                "available": None,
            },
        }

    def save_settings(self, patch: dict) -> dict:
        self._settings = self._settings_store.save(patch)
        configure_logging(self._settings.logging_level)
        return asdict(self._settings)

    def reset_settings(self) -> dict:
        self._settings = self._settings_store.save(Settings())
        return asdict(self._settings)

    def choose_output_folder(self) -> str:
        if not self._window:
            return ""
        result = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        return result[0] if result else ""

    def choose_default_output_folder(self) -> dict:
        folder = self.choose_output_folder()
        if not folder:
            return {"ok": False, "cancelled": True}
        self._settings = self._settings_store.save({"default_output_folder": folder})
        return {"ok": True, "folder": folder, "settings": asdict(self._settings)}

    def select_ffmpeg(self) -> str:
        if not self._window:
            return ""
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            file_types=("FFmpeg executable (*.exe)", "All files (*.*)"),
        )
        return result[0] if result else ""

    def select_cookie_file(self) -> dict:
        if not self._window:
            return {"ok": False, "cancelled": True}
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            file_types=("Netscape cookies (*.txt)", "Cookie files (*.cookies)", "All files (*.*)"),
        )
        if not result:
            return {"ok": False, "cancelled": True}
        path = result[0]
        self._settings = self._settings_store.save({"cookie_file_path": path})
        return {"ok": True, "path": path, "settings": asdict(self._settings)}

    def test_ffmpeg(self, mode: str | None = None, custom_path: str | None = None) -> dict:
        return probe(mode or self._settings.ffmpeg_mode, custom_path or self._settings.custom_ffmpeg_path)

    def download_managed_ffmpeg(self) -> dict:
        if self._ffmpeg_download_running:
            return {"ok": False, "error": "FFmpeg download is already running."}

        def run() -> None:
            self._ffmpeg_download_running = True
            try:
                result = download_managed_ffmpeg(self._emit)
                self._settings = self._settings_store.save({"ffmpeg_mode": "managed"})
                ffmpeg_status = probe(self._settings.ffmpeg_mode, self._settings.custom_ffmpeg_path)
                self._emit({"type": "settings", "settings": asdict(self._settings)})
                self._emit({"type": "ffmpeg", "status": ffmpeg_status})
                self._emit({"type": "ffmpeg_download", "ok": True, "status": result["license"], "percent": 100})
            except Exception as exc:
                LOGGER.exception("Managed FFmpeg download failed")
                self._emit({"type": "ffmpeg_download", "ok": False, "status": str(exc), "percent": 0})
            finally:
                self._ffmpeg_download_running = False

        threading.Thread(target=run, daemon=True).start()
        return {"ok": True, "status": "FFmpeg download started"}

    def update_ytdlp(self) -> dict:
        if self._ytdlp_update_running:
            return {"ok": False, "error": "yt-dlp update is already running."}

        def run() -> None:
            self._ytdlp_update_running = True
            self._emit({"type": "ytdlp_update", "running": True, "status": "Updating yt-dlp..."})
            try:
                def report(update: dict) -> None:
                    self._emit({"type": "ytdlp_update", "running": True, **update})
                    if update.get("status"):
                        self._emit({"type": "terminal", "line": update["status"]})

                result = update_ytdlp(report)
                self._emit({
                    "type": "ytdlp_update",
                    "running": False,
                    "ok": True,
                    "version": result["version"],
                    "current_version": result["version"],
                    "latest_version": result["version"],
                    "available": False,
                    "restart": True,
                    "status": f"yt-dlp updated to {result['version']}. Restarting the app...",
                })
                threading.Timer(0.8, self._restart_after_update).start()
            except Exception as exc:
                LOGGER.exception("yt-dlp update failed")
                self._emit({"type": "ytdlp_update", "running": False, "ok": False, "status": str(exc)})
            finally:
                self._ytdlp_update_running = False

        threading.Thread(target=run, daemon=True).start()
        return {"ok": True, "status": "yt-dlp update started"}

    def _restart_after_update(self) -> None:
        try:
            restart_application()
        except Exception:
            LOGGER.exception("Could not restart the app after updating yt-dlp")
        finally:
            if self._window:
                self._window.destroy()

    def update_app(self) -> dict:
        def run() -> None:
            self._emit({"type": "app_update", "running": True, "status": "Checking GitHub for updates..."})
            try:
                release = check_for_update(__version__)
                if not release["update_available"]:
                    self._emit({"type": "app_update", "running": False, "ok": True, **update_event(__version__, release), "status": f"The app is up to date ({__version__})."})
                    return
                if not release["installer_url"]:
                    raise RuntimeError(f"GitHub release {release['version']} has no Windows installer asset.")
                self._emit({"type": "app_update", "running": True, "status": f"Downloading version {release['version']}..."})
                def report(update: dict) -> None:
                    self._emit({"type": "app_update", "running": True, **update})
                    if update.get("status"):
                        self._emit({"type": "terminal", "line": update["status"]})

                download_and_launch_update(
                    release["installer_url"],
                    report,
                    release.get("installer_digest", ""),
                    release.get("installer_api_url", ""),
                )
                self._emit({"type": "app_update", "running": False, "ok": True, "available": True, "version": release["version"], "status": "Update downloaded. Closing the app to install it..."})
                if self._window:
                    self._window.destroy()
            except Exception as exc:
                LOGGER.exception("Application update failed")
                self._emit({"type": "app_update", "running": False, "ok": False, "status": str(exc)})

        threading.Thread(target=run, daemon=True).start()
        return {"ok": True, "status": "Checking GitHub for updates..."}

    def check_app_update(self) -> dict:
        """Check for a release without downloading anything or closing the app."""
        def run() -> None:
            try:
                release = check_for_update(__version__)
                self._emit({
                    "type": "app_update",
                    "running": False,
                    "ok": True,
                    **update_event(__version__, release),
                    "status": (
                        f"Update available: {release['version']}"
                        if release["update_available"]
                        else f"The app is up to date ({__version__})."
                    ),
                })
            except Exception as exc:
                LOGGER.warning("Background application update check failed: %s", exc)
                self._emit({"type": "app_update", "running": False, "ok": False, "status": str(exc)})
            try:
                library = check_ytdlp_update()
                self._emit({
                    "type": "ytdlp_update",
                    "running": False,
                    "ok": True,
                    "version": library["current_version"],
                    "current_version": library["current_version"],
                    "latest_version": library["latest_version"],
                    "available": library["update_available"],
                    "status": (
                        f"yt-dlp update available: {library['latest_version']}"
                        if library["update_available"]
                        else f"yt-dlp is up to date ({library['current_version']})."
                    ),
                })
            except Exception as exc:
                LOGGER.warning("Background yt-dlp update check failed: %s", exc)
                self._emit({"type": "ytdlp_update", "running": False, "ok": False, "status": str(exc)})

        threading.Thread(target=run, daemon=True).start()
        return {"ok": True, "status": "Checking GitHub for updates..."}

    def analyze(self, url: str) -> dict:
        if not validate_url(url):
            return {"ok": False, "error": "Enter a valid http or https URL."}

        def run() -> None:
            try:
                self._emit({"type": "analyze_status", "status": "Analyzing link..."})
                info = analyze_url(url, self._settings.max_duration_warning_minutes, self._settings.use_browser_cookies, self._settings.browser_cookie_source, self._settings.cookie_file_path)
                self._last_analysis = info
                default_ext = self._settings.default_format
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
        if self._worker.running:
            return {"ok": False, "error": "A download is already running."}

        output_folder = str(Path(request.get("output_folder") or self._settings.default_output_folder).expanduser())
        if output_folder != self._settings.default_output_folder:
            self._settings = self._settings_store.save({"default_output_folder": output_folder})
            self._emit({"type": "settings", "settings": asdict(self._settings)})
        request["output_folder"] = output_folder
        request["use_browser_cookies"] = self._settings.use_browser_cookies
        request["browser_cookie_source"] = self._settings.browser_cookie_source
        request["cookie_file_path"] = self._settings.cookie_file_path

        title = (self._last_analysis or {}).get("title") or request.get("filename") or "Download"

        def progress(event: dict) -> None:
            self._emit(event)
            if event.get("type") in {"complete", "error"}:
                status = "success" if event.get("type") == "complete" else "failed"
                output_path = event.get("output_path") or request.get("output_folder", "")
                items = self._history_store.add(
                    HistoryItem.now(
                        title=title,
                        source_url=request["url"],
                        selected_format=f"{request.get('mode', 'audio')} / {request.get('format', '')}",
                        output_path=output_path,
                        status=status,
                    )
                )
                self._emit({"type": "history", "items": items})
                if status == "success" and self._settings.open_folder_after_download:
                    self.open_folder(output_path)

        self._worker.progress = progress
        try:
            self._worker.start(request, self._settings.ffmpeg_mode, self._settings.custom_ffmpeg_path)
            return {"ok": True, "status": "Download started"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def cancel_download(self) -> dict:
        if self._worker.running:
            self._worker.cancel()
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

    def _run_on_ui(self, callback):
        if not self._window or not self._window.native:
            raise RuntimeError("The app window is not ready.")
        form = self._window.native
        if form.InvokeRequired:
            from System import Action

            def invoke_callback() -> None:
                try:
                    callback()
                except Exception:
                    LOGGER.exception("Native browser UI action failed")

            form.BeginInvoke(Action(invoke_callback))
            return None
        return callback()

    def _ensure_browser_control(self) -> None:
        if self._browser_control is not None or self._browser_creating:
            return
        self._browser_creating = True

        def create_control() -> None:
            try:
                from Microsoft.Web.WebView2.WinForms import WebView2

                control = WebView2()
                control.Visible = False
                control.DefaultBackgroundColor = self._window.native.BackColor
                control.CoreWebView2InitializationCompleted += self._on_browser_initialized
                control.NavigationStarting += self._on_browser_navigation_starting
                control.NavigationCompleted += self._on_browser_navigation_completed
                control.SourceChanged += self._on_browser_source_changed
                self._window.native.Controls.Add(control)
                control.BringToFront()
                self._browser_control = control
                control.EnsureCoreWebView2Async(None)
            finally:
                self._browser_creating = False

        self._run_on_ui(create_control)

    def _on_browser_initialized(self, sender, event) -> None:
        if not event.IsSuccess:
            self._emit({"type": "browser_status", "open": False, "error": "WebView2 initialization failed."})
            return
        core = sender.CoreWebView2
        core.Settings.IsStatusBarEnabled = False
        core.Settings.AreDefaultContextMenusEnabled = True
        core.Settings.AreDevToolsEnabled = False
        core.Settings.IsZoomControlEnabled = True
        core.NewWindowRequested += self._on_browser_new_window
        core.DownloadStarting += self._on_browser_download_starting
        self._browser_ready = True
        sender.Source = self._system_uri(self._browser_pending_url)

    @staticmethod
    def _system_uri(url: str):
        from System import Uri

        return Uri(url)

    def _on_browser_new_window(self, sender, event) -> None:
        event.Handled = True
        if self._browser_control and event.Uri:
            self._browser_control.Source = self._system_uri(event.Uri)

    def _on_browser_download_starting(self, _, event) -> None:
        filename = Path(str(event.ResultFilePath)).name if event.ResultFilePath else "file"
        self._emit({"type": "status", "status": f"Browser download started: {filename}"})

    def _on_browser_source_changed(self, sender, _) -> None:
        url = str(sender.Source) if sender.Source else ""
        self._browser_url = url
        threading.Thread(target=self._emit, args=({"type": "browser_status", "url": url, "open": True},), daemon=True).start()

    def _on_browser_navigation_completed(self, sender, event) -> None:
        url = str(sender.Source) if sender.Source else ""
        self._browser_url = url
        threading.Thread(
            target=self._emit,
            args=({
                "type": "browser_status",
                "url": url,
                "open": True,
                "loading": False,
                "canBack": bool(sender.CanGoBack),
                "canForward": bool(sender.CanGoForward),
                "error": "" if event.IsSuccess else "Page failed to load.",
            },),
            daemon=True,
        ).start()
        host = (urlparse(url).hostname or "").lower()
        if host == "youtube.com" or host.endswith(".youtube.com"):
            sender.CoreWebView2.ExecuteScriptAsync(
                """
                document.documentElement.style.colorScheme = 'dark';
                if (!document.getElementById('musicxcst-send-download')) {
                  const button = document.createElement('button');
                  button.id = 'musicxcst-send-download';
                  button.setAttribute('aria-label', 'Send this page to MusicXCST Download');
                  button.innerHTML = '<span style="font-size:18px">&#8595;</span><span>Download</span>';
                  Object.assign(button.style, {
                    position: 'fixed', top: '14px', right: '18px', zIndex: '2147483647',
                    display: 'flex', alignItems: 'center', gap: '7px', padding: '10px 15px',
                    border: '0', borderRadius: '8px', cursor: 'pointer', color: '#041108',
                    background: '#39e075', font: '700 14px Segoe UI, sans-serif',
                    boxShadow: '0 10px 30px rgba(57,224,117,.35)'
                  });
                  button.onclick = () => location.href = 'musicxcst://download?url=' + encodeURIComponent(location.href);
                  document.body.appendChild(button);
                }
                """
            )

    def _on_browser_navigation_starting(self, sender, event) -> None:
        url = str(event.Uri or "")
        if not url.startswith("musicxcst://download"):
            self._browser_url = url
            threading.Thread(
                target=self._emit,
                args=({"type": "browser_status", "url": url, "open": True, "loading": True},),
                daemon=True,
            ).start()
            return
        event.Cancel = True
        threading.Thread(target=self.browser_send_current_to_download, daemon=True).start()

    def browser_open(self, value: str = BROWSER_HOME) -> dict:
        url = normalize_browser_url(value)
        self._browser_pending_url = url
        self._ensure_browser_control()

        def navigate() -> None:
            if self._browser_ready:
                self._browser_control.Source = self._system_uri(url)
            self._browser_control.Visible = True
            self._browser_control.BringToFront()

        self._run_on_ui(navigate)
        return {"ok": True, "url": url}

    def browser_layout(self, bounds: dict, visible: bool = True) -> dict:
        if not visible and self._browser_control is None:
            return {"ok": True}
        self._ensure_browser_control()

        def apply_layout() -> None:
            from System.Drawing import Rectangle

            self._browser_control.Bounds = Rectangle(
                max(0, int(bounds.get("x", 0))),
                max(0, int(bounds.get("y", 0))),
                max(1, int(bounds.get("width", 1))),
                max(1, int(bounds.get("height", 1))),
            )
            self._browser_control.Visible = bool(visible)
            if visible:
                self._browser_control.BringToFront()

        self._run_on_ui(apply_layout)
        return {"ok": True}

    def _browser_action(self, callback) -> dict:
        if not self._browser_control or not self._browser_ready:
            return {"ok": False, "error": "Open the web browser first."}
        self._run_on_ui(callback)
        return {"ok": True}

    def browser_home(self) -> dict:
        return self.browser_open(BROWSER_HOME)

    def browser_back(self) -> dict:
        return self._browser_action(lambda: self._browser_control.GoBack() if self._browser_control.CanGoBack else None)

    def browser_forward(self) -> dict:
        return self._browser_action(lambda: self._browser_control.GoForward() if self._browser_control.CanGoForward else None)

    def browser_reload(self) -> dict:
        return self._browser_action(lambda: self._browser_control.Reload())

    def browser_stop(self) -> dict:
        return self._browser_action(lambda: self._browser_control.CoreWebView2.Stop())

    def browser_zoom(self, delta: float) -> dict:
        self._browser_zoom_factor = min(3.0, max(0.25, self._browser_zoom_factor + float(delta)))

        def zoom() -> None:
            self._browser_control.ZoomFactor = self._browser_zoom_factor

        result = self._browser_action(zoom)
        if result["ok"]:
            result["zoom"] = round(self._browser_zoom_factor * 100)
        return result

    def browser_find(self, text: str) -> dict:
        query = json.dumps(str(text or ""))
        return self._browser_action(lambda: self._browser_control.CoreWebView2.ExecuteScriptAsync(f"window.find({query})"))

    def browser_copy_url(self) -> dict:
        current = self.browser_current_url()
        if not current["ok"]:
            return current
        return {"ok": True, "url": current["url"]}

    def browser_open_external(self) -> dict:
        current = self.browser_current_url()
        return open_external_url(current["url"]) if current["ok"] else current

    def browser_current_url(self) -> dict:
        url = self._browser_url
        return {"ok": bool(url), "url": url or ""}

    def browser_send_current_to_download(self) -> dict:
        current = self.browser_current_url()
        url = current.get("url", "")
        host = (urlparse(url).hostname or "").lower()
        if not (host == "youtube.com" or host.endswith(".youtube.com") or host == "youtu.be"):
            return {"ok": False, "error": "Open a YouTube or YouTube Music page first."}
        self._emit({"type": "browser_send_download", "url": url})
        return {"ok": True, "url": url}

    def remove_history(self, index: int) -> list[dict]:
        return self._history_store.remove(index)

    def clear_history(self) -> list[dict]:
        self._history_store.clear()
        return []


def main() -> None:
    webview.settings["ALLOW_DOWNLOADS"] = True
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = False
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
    webview.start(debug=False, private_mode=False, storage_path=str(browser_storage_dir()))


if __name__ == "__main__":
    main()
