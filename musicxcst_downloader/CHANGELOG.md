# MusicXCST Downloader 2.0.0

## 2.0.2

- Added a dedicated live progress bar for yt-dlp updates, including percentage and current operation status.
- Download progress is shown immediately when Download is pressed and continues through conversion and finalization.
- Replaced the click-through Inno Setup flow with a self-contained terminal-style installer that installs automatically, preserves app data, and launches the app when finished.
- The release workflow now builds the custom installer without requiring Inno Setup.

## 2.0.1

- Fixed application updates for private GitHub repositories by reusing the authenticated GitHub CLI session automatically.
- Replaced the unhelpful GitHub API 404 with a clear sign-in instruction when no local GitHub CLI session is available.
- Kept installer digest verification and the existing settings/history migration behavior unchanged.

## What is new

- Download audio only, video only, or video with audio.
- Choose from audio formats (`mp3`, `ogg`, `wav`, `flac`, `m4a`, `opus`, `aac`, `alac`) and video formats (`mp4`, `mkv`, `webm`, `mov`, `avi`, `m4v`, `ts`).
- Choose audio quality or scan video quality from 4K down to 360p.
- The media scan now shows the best audio and video streams, codecs, bitrate, frame rate, file sizes, Dolby Atmos availability, and the number of available formats.
- Added a terminal-style progress panel so downloads, yt-dlp updates, and application updates are visible inside the app.
- Added Settings buttons for updating yt-dlp and updating the application from GitHub.
- yt-dlp updates are installed into the app data directory with SHA-256 verification and are used automatically after restarting the app.
- Application updates download the GitHub installer with digest verification, then launch the installer and close the current app.
- Existing settings, output folders, colors, history, and FFmpeg configuration remain in the same app data location and are migrated without being reset.
- Fixed the installer icon by including the application icon in the installed files and both shortcuts.

## Verification

- 18 automated backend tests pass.
- Python compilation and frontend JavaScript syntax checks pass.
- The PyInstaller and Inno Setup build pass.
- Release automation remains enabled: pushing a `v*` tag builds and publishes the Windows installer through GitHub Actions.

## Download

Download `MusicXCST-Downloader-Setup-2.0.0.exe` from the GitHub release assets.
