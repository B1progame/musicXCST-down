# Third-party notices

MusicXCST Downloader uses the following third-party tools and libraries:

- pywebview: desktop webview window and Python bridge.
- yt-dlp: metadata extraction and download support.
- FFmpeg and ffprobe: media merging, conversion, and probing. Users can provide FFmpeg from PATH, choose a custom path, or download an app-managed LGPL essentials build from gyan.dev.
- PyInstaller: Windows executable packaging.
- Inno Setup: optional Windows installer packaging.

This app does not bundle FFmpeg by default. The optional managed FFmpeg button downloads `ffmpeg-release-essentials.zip` from `https://www.gyan.dev/ffmpeg/builds/`, extracts only `ffmpeg.exe` and `ffprobe.exe`, and stores them under the app data folder at `MusicXCST Downloader\ffmpeg`. The Inno installer removes that managed FFmpeg folder when the app is uninstalled.
