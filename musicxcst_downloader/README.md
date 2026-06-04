# MusicXCST Downloader

MusicXCST Downloader is a standalone Windows desktop app by B1progame. It is a modern private downloader tool with a web-style GUI built with Python, pywebview, yt-dlp, and FFmpeg.

This app is not the Minecraft mod and is not integrated into any Minecraft mod jar. The MusicXCST name/style is only a visual reference.

## Legal use warning

Use this tool only for videos/music you own, have permission to use, or are legally allowed to download.

The app does not bypass DRM, paywalls, logins, private content, age restrictions, geo-blocks, or platform protections. It does not use cookies, browser profile extraction, account tokens, credential import, telemetry, accounts, or credential storage.

## Features

- Paste a video/music link and analyze metadata before downloading.
- Choose MP4, WebM, MP3, OGG, WAV, FLAC, or M4A/AAC output.
- Choose best, 1080p, 720p, 480p, best audio, or smaller audio settings.
- Select output folder and editable safe filename.
- Legal confirmation required before download.
- Live progress, speed, ETA, cancel support, final path, open folder, and copy path.
- Local settings, history, and logs under `%APPDATA%\MusicXCST Downloader`.
- FFmpeg detection from PATH or a custom path.

## Installation for development

Python 3.12 is recommended. Python 3.11 is also supported for local development on machines where 3.12 is not installed.

```powershell
cd musicxcst_downloader
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .[dev]
.\.venv\Scripts\python.exe -m musicxcst_downloader.app
```

If Python 3.12 is not installed, use:

```powershell
py -3.11 -m venv .venv
```

## FFmpeg setup

Install FFmpeg and make sure `ffmpeg.exe` and `ffprobe.exe` are available on PATH, or choose a custom `ffmpeg.exe` path in Settings.

If FFmpeg is missing, the app shows setup status and explains why it is needed. Managed FFmpeg download is intentionally not implemented yet because it must pin a URL, pin a SHA-256 checksum, verify the file, and show third-party notices before use.

## How to use

1. Start the app.
2. Confirm the first-run legal notice.
3. Paste a link.
4. Click **Analyze Link**.
5. Choose format, quality, folder, and filename.
6. Check **I confirm I have the right to download this content.**
7. Click **Download**.

## Keyboard shortcuts

- `Ctrl+L`: focus URL input
- `Ctrl+O`: choose output folder
- `Ctrl+Enter`: analyze or start download
- `Esc`: cancel active download

## Build the .exe

PyInstaller one-folder builds are preferred to reduce antivirus false positives:

```powershell
cd musicxcst_downloader
.\scripts\build_exe.ps1
```

The build script reuses either `musicxcst_downloader\.venv` or a repo-root `.venv` if one already exists.

Output:

```text
dist\MusicXCST Downloader\
```

## Build the installer

Install Inno Setup 6, then run:

```powershell
cd musicxcst_downloader
.\scripts\build_installer.ps1
```

Output:

```text
dist\installer\MusicXCST-Downloader-Setup.exe
```

## Local data

- Settings: `%APPDATA%\MusicXCST Downloader\settings.json`
- History: `%APPDATA%\MusicXCST Downloader\history.json`
- Logs: `%APPDATA%\MusicXCST Downloader\logs\`

## Troubleshooting

- **FFmpeg missing:** Install FFmpeg or select `ffmpeg.exe` in Settings, then click **Test FFmpeg**.
- **Invalid URL:** Use a full `https://` or `http://` link.
- **Download fails on protected content:** The app does not bypass platform protections or account-only content.
- **Output exists:** Rename the output file before downloading.
- **Conversion fails:** Verify both `ffmpeg.exe` and `ffprobe.exe` work from PATH or the selected folder.

## Disclaimer

This tool is not affiliated with YouTube, Google, Mojang, Microsoft, Dolby, Adobe, or any video platform.
