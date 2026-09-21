from __future__ import annotations

import os
import argparse
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
import threading
from pathlib import Path
from typing import Callable


Log = Callable[[str], None]
APP_NAME = "MusicXCST Downloader"


def format_progress(percent: int) -> str:
    percent = max(0, min(100, int(percent)))
    filled = round(percent / 10)
    return f"[{'#' * filled}{'-' * (10 - filled)}] {percent}%"


def _safe_extract(payload: Path, staging: Path, log: Log) -> Path:
    root = staging / APP_NAME
    with zipfile.ZipFile(payload) as archive:
        members = archive.infolist()
        if not members:
            raise RuntimeError("Installer payload is empty.")
        last_percent = -1
        for index, member in enumerate(members, start=1):
            relative = Path(member.filename)
            if relative.is_absolute() or ".." in relative.parts:
                raise RuntimeError("Installer payload contains an unsafe path.")
            if not relative.parts or relative.parts[0] != APP_NAME:
                raise RuntimeError("Installer payload has an unexpected root folder.")
            destination = staging / relative
            if member.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target)
            percent = round(index / len(members) * 100)
            if percent != last_percent and (percent % 5 == 0 or percent == 100):
                log(f"Extracting {format_progress(percent)}")
                last_percent = percent
    if not (root / f"{APP_NAME}.exe").exists():
        raise RuntimeError("Installer payload does not contain the application executable.")
    log(f"Payload extracted: {len(members)} files")
    return root


def _copy_with_progress(source: Path, target: Path, log: Log) -> None:
    files = [path for path in source.rglob("*") if path.is_file()]
    last_percent = -1
    for index, source_file in enumerate(files, start=1):
        destination = target / source_file.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        last_error = None
        for attempt in range(12):
            try:
                shutil.copy2(source_file, destination)
                last_error = None
                break
            except PermissionError as exc:
                last_error = exc
                time.sleep(0.5)
        if last_error is not None:
            raise last_error
        percent = round(index / len(files) * 100)
        if percent != last_percent and (percent % 5 == 0 or percent == 100):
            log(f"Installing {format_progress(percent)}")
            last_percent = percent


def install_payload(payload: Path, target: Path, log: Log = print) -> Path:
    """Install the staged app without touching %APPDATA% settings or history."""
    payload = Path(payload).resolve()
    target = Path(target).resolve()
    if not payload.is_file():
        raise FileNotFoundError(f"Payload not found: {payload}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="musicxcst-installer-") as temp_dir:
        staging = Path(temp_dir)
        app_root = _safe_extract(payload, staging, log)
        log(f"Installing to {target}")
        _copy_with_progress(app_root, target, log)
    log("Application files installed.")
    return target


def _payload_path() -> Path:
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return bundle_root / "payload.zip"


def _install_target() -> Path:
    local_app_data = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    return local_app_data / "Programs" / APP_NAME


def _process_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def wait_for_process_exit(pid: int, log: Log = print, timeout: float = 45.0) -> None:
    """Wait for the previous app process to release files before copying."""
    if not _process_is_running(pid):
        return
    log("Closing the previous version...")
    deadline = time.monotonic() + timeout
    while _process_is_running(pid) and time.monotonic() < deadline:
        time.sleep(0.25)
    if _process_is_running(pid):
        raise RuntimeError("The previous application is still running. Close it and retry the update.")


class VisualInstaller:
    """Small windowed installer with a Circular progress ring."""

    def __init__(self):
        import tkinter as tk

        self.tk = tk
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} Update")
        self.root.geometry("520x420")
        self.root.resizable(False, False)
        self.root.configure(bg="#0b0e15")
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)
        tk.Label(self.root, text="MusicXCST", bg="#0b0e15", fg="#f7f8fb", font=("Segoe UI", 22, "bold")).pack(pady=(28, 2))
        tk.Label(self.root, text="Updating your desktop app", bg="#0b0e15", fg="#9da7b7", font=("Segoe UI", 11)).pack()
        self.canvas = tk.Canvas(self.root, width=220, height=220, bg="#0b0e15", highlightthickness=0)
        self.canvas.pack(pady=(12, 0))
        self.canvas.create_oval(20, 20, 200, 200, outline="#202837", width=14)
        self.arc = self.canvas.create_arc(20, 20, 200, 200, start=90, extent=0, outline="#56f0ff", width=14, style=tk.ARC)
        self.percent = self.canvas.create_text(110, 98, text="0%", fill="#f7f8fb", font=("Segoe UI", 24, "bold"))
        self.canvas.create_text(110, 132, text="Installing", fill="#9da7b7", font=("Segoe UI", 10))
        self.status = tk.Label(self.root, text="Preparing update...", bg="#0b0e15", fg="#c8d1df", font=("Segoe UI", 11))
        self.status.pack(pady=(2, 0))
        self.detail = tk.Label(self.root, text="Your settings and downloads are kept", bg="#0b0e15", fg="#667084", font=("Segoe UI", 9))
        self.detail.pack(pady=(4, 0))
        self.close_button = tk.Button(self.root, text="Close", state=tk.DISABLED, command=self.root.destroy, bg="#202837", fg="#f7f8fb", relief=tk.FLAT, padx=24, pady=8)
        self.close_button.pack(pady=16)

    def update(self, percent: int, status: str) -> None:
        def apply():
            safe = max(0, min(100, int(percent)))
            self.canvas.itemconfigure(self.arc, extent=-safe * 3.6)
            self.canvas.itemconfigure(self.percent, text=f"{safe}%")
            self.status.configure(text=status)
        self.root.after(0, apply)

    def finish(self, success: bool, message: str) -> None:
        def apply():
            if success:
                self.canvas.itemconfigure(self.arc, extent=-360, outline="#57e389")
                self.canvas.itemconfigure(self.percent, text="✓")
                self.status.configure(text="Update complete")
                self.detail.configure(text="Launching the updated app...")
                self.root.after(900, self.root.destroy)
            else:
                self.canvas.itemconfigure(self.arc, outline="#ff5a67")
                self.status.configure(text="Update could not be completed")
                self.detail.configure(text=message)
                self.close_button.configure(state=self.tk.NORMAL)
        self.root.after(0, apply)

    def run(self) -> int:
        self.root.mainloop()
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--wait-pid", type=int, default=0)
    args, _ = parser.parse_known_args()
    visual = VisualInstaller()

    def worker() -> None:
        try:
            if args.wait_pid:
                wait_for_process_exit(args.wait_pid, log=lambda message: visual.update(2, message))
            visual.update(5, "Preparing files...")
            target = install_payload(
                _payload_path(),
                _install_target(),
                log=lambda message: visual.update(
                    int(message.rsplit(" ", 1)[-1].rstrip("%")) if message.startswith(("Extracting", "Installing")) else 4,
                    "Installing update...",
                ),
            )
            visual.update(100, "Launching updated app...")
            subprocess.Popen([str(target / f"{APP_NAME}.exe")], close_fds=True)
            visual.finish(True, "")
        except Exception as exc:
            visual.finish(False, str(exc))

    threading.Thread(target=worker, daemon=True).start()
    return visual.run()


if __name__ == "__main__":
    raise SystemExit(main())
