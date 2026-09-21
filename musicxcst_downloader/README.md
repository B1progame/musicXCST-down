# MusicXCST Downloader

MusicXCST Downloader is a standalone Windows desktop app by **B1progame**. It is a modern private downloader tool with a polished web-style GUI built with Python, pywebview, yt-dlp, and FFmpeg.

This app is not the Minecraft mod and is not integrated into any Minecraft mod jar. The MusicXCST name/style is only a visual reference.

## Status

- App type: standalone Windows desktop app
- GUI: local HTML/CSS/JS through pywebview
- Downloader engine: yt-dlp
- Conversion/probing: FFmpeg and ffprobe
- Packaging: PyInstaller one-folder build
- Installer: self-contained windowed PyInstaller installer with circular progress
- Network styling: no online CSS or JS CDNs
- Privacy: no telemetry or credential export; Web tab site data stays in its local browser profile

## Legal use warning

Use this tool only for music or audio you own, have permission to use, or are legally allowed to download. You alone are responsible for what you download; B1progame and MusicXCST Downloader are not responsible for downloads of music you do not own or have rights to use.

The app does not bypass DRM, paywalls, logins, private content, age restrictions, geo-blocks, or platform protections. The Web tab may store normal browser cookies locally, but downloads do not extract browser profiles, account tokens, or login credentials.

## Features

- Paste a music or audio link and analyze metadata before downloading.
- Choose audio-only, video-only, or video-with-audio downloads.
- Choose MP3, OGG, WAV, FLAC, M4A/AAC, MP4, MKV, WebM, MOV, AVI, M4V, or TS output.
- Scan available streams, codecs, bitrates, sizes, frame rates, and the best quality before downloading.
- Choose best audio or smaller audio settings.
- Select output folder and editable safe filename.
- Legal confirmation required before download.
- Live download progress, speed, ETA, conversion stage, cancel support, final path, open folder, and copy path.
- Live yt-dlp update percentage and terminal-style operation log.
- Settings can switch between the default Classic UI and the optional Aurora 3.0 redesign, with a motion toggle.
- The app checks GitHub in the background at startup and shows an update warning in Settings when a newer release is available; it never installs automatically.
- Settings has an animated rainbow accent and the existing motion toggle disables it when reduced motion is preferred.
- Application updates use a visual installer, wait for the previous app to exit, retry locked files, and relaunch the updated app automatically.
- The yt-dlp updater uses pip directly into an app-managed override and falls back to a verified package when pip is unavailable.
- Combined video downloads expose an explicit **Best video + best audio** choice.
- Local settings, history, and logs under `%APPDATA%\MusicXCST Downloader`.
- FFmpeg detection from PATH or a custom path.
- About page links open in the default browser.

## License

This project uses a private-use license. See the repository root `LICENSE` file.

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

If FFmpeg is missing, the app shows setup status and explains why it is needed. The Settings page can download and verify a managed FFmpeg build.

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

```powershell
cd musicxcst_downloader
.\scripts\build_installer.ps1
```

The script builds the app, embeds the complete payload into a self-contained terminal-style installer, and does not require Inno Setup. Running the installer performs the installation automatically without setup pages or click-through prompts.

Output:

```text
dist\installer\MusicXCST-Downloader-Setup-<version>.exe
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
- **yt-dlp update fails:** Open Settings and retry **Update yt-dlp**; the app shows pip output and uses a verified fallback when pip cannot run.
- **Conversion fails:** Verify both `ffmpeg.exe` and `ffprobe.exe` work from PATH or the selected folder.

## Disclaimer

This tool is not affiliated with YouTube, Google, Mojang, Microsoft, Dolby, Adobe, or any media platform.
