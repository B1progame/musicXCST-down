# MusicXCST Downloader 4.1.0

## 4.1.0

- Expanded analysis error handling for unavailable, private, region-restricted, age-restricted, rate-limited, network, unsupported-link, and FFmpeg failures.
- Added actionable guidance plus preserved technical details in the operation log.

## 4.0.9

- Replaced raw yt-dlp unavailable-video errors with a clear message explaining link, region, and privacy checks.
- Added friendly age-restriction guidance for analysis failures.

## 4.0.8

- Added a visible animated analysis state with a circular spinner and indeterminate progress bar while Analyze Link scans streams.
- Added clear Analyzing, complete, and failed states to the workflow status and operation panel.
- Kept reduced-motion support for the new analysis animation.

## 4.0.7

- Restored the legal start screen on every application launch.
- Changed “I Understand” to dismiss the screen for the current session without persisting it as completed.

## 4.0.6

- Fixed the embedded browser staying glued to its old position while the Web page scrolls.
- Repositioned the native WebView2 control on content/window scrolling with animation-frame throttling.

## 4.0.5

- Fixed the first-run notice and download label incorrectly describing the app as audio-only.
- Made the available video and video-plus-audio modes clearly visible.

## 4.0.4

- Fixed startup version fields staying at “unknown” when the pywebview bridge initializes after the page.
- Added bridge-ready startup handling, duplicate-init protection, and visible startup error feedback.

## 4.0.3

- Kept the App Update control enabled when the installed app is already current.
- Changed the current-state action label to “Check for updates”; only active checks and installs disable the button.

## 4.0.2
- Fixed the Settings rainbow border so it is completely neutral unless an app update is actually available.
- Added coordinated fade-out/fade-in page navigation with reduced-motion support.
- Extended Aurora motion with staged panel entrances, smoother hover/focus transitions, and improved select controls.

## 4.0.1
- Fixed startup version reporting so the installed app and yt-dlp versions are always visible immediately.
- Kept yt-dlp version details visible while pip progress updates run.
- Automatically restarts the app after a successful yt-dlp update so the new package activates.
- Made the animated rainbow Settings treatment appear only when a new app update is available.

## 4.0.0
- Reworked the entire desktop interface with a cleaner workspace hierarchy, clearer download steps, stronger navigation, and calmer visual surfaces.
- Added consistent SVG navigation icons, visible keyboard focus states, improved disabled/loading feedback, and reduced-motion handling.
- Improved responsive behavior for narrow windows and made settings, history, web tools, and download actions easier to scan.

## 3.2.2

- Fixed settings persistence for default video quality and flushed pending settings before application updates close the app.
- Improved GitHub CLI discovery for packaged startup checks.
- Startup now compares installed and latest app and yt-dlp versions.
- Update buttons are disabled and labeled up to date when no update is available.

## 3.2.1

- Fixed the visual installer crash caused by parsing `Downloader` from the destination path as a percentage.
- Bundled and explicitly applied the MusicXCST icon to the installer window and taskbar entry.

## 3.2.0

- Replaced the console installer with a windowed visual installer featuring a circular progress indicator and status text.
- Fixed update installation failures caused by the previous app still locking files (`WinError 32`).
- The installer waits for the previous process, retries transient file locks, and automatically launches the updated app after installation.
- Settings, history, FFmpeg, and downloaded files remain untouched.

## 3.1.0

- Added a background GitHub release check at startup without downloading or installing anything automatically.
- Added an animated warning badge in Settings and a topbar reminder when a newer app release is available.
- Added an animated rainbow Settings button with reduced-motion support.

## 3.0.0

- Added the optional Aurora 3.0 interface redesign; Classic remains the default and can be selected in Settings.
- Added a motion/transitions toggle for users who prefer a reduced-motion interface.
- Added a real pip-based yt-dlp updater that installs into an app-managed override without resetting settings, history, FFmpeg, or downloaded files.
- Kept a verified PyPI wheel fallback when pip is unavailable, with visible progress and diagnostics in the app.
- Added explicit Best video + best audio quality selection for combined downloads, alongside Best audio and Best video modes.
- Added real extraction and installation progress bars to the automatic terminal installer.
- Bumped the application release to v3.0.0.

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
