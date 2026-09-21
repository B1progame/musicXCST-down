from pathlib import Path
import zipfile

from musicxcst_downloader.backend.downloader import (
    build_format_selector,
    format_supports_dolby_atmos,
    output_filename_from_title,
    sanitize_filename,
    validate_url,
)
from musicxcst_downloader.backend.ffmpeg import probe
from musicxcst_downloader.backend.managed_ffmpeg import extract_managed_ffmpeg
from musicxcst_downloader.backend.external import is_safe_external_url, open_external_url
from musicxcst_downloader.backend.history import HistoryItem, HistoryStore
from musicxcst_downloader.backend.legal import can_download
from musicxcst_downloader.backend.settings import SettingsStore
from musicxcst_downloader.backend.ytdlp_updater import installed_ytdlp_version
from musicxcst_downloader.backend.browser import normalize_browser_url


def test_sanitize_filename_removes_windows_invalid_chars():
    assert sanitize_filename('bad<>:"/\\|?*\x00 name') == "bad__________ name"


def test_output_filename_generation_adds_extension():
    assert output_filename_from_title("Song / Demo", "mp3") == "Song _ Demo.mp3"


def test_url_validation():
    assert validate_url("https://example.com/watch?v=1")
    assert not validate_url("javascript:alert(1)")
    assert not validate_url("not a url")


def test_legal_checkbox_blocks_download():
    assert can_download(True)
    assert not can_download(False)


def test_settings_save_load(tmp_path: Path):
    store = SettingsStore(tmp_path / "settings.json")
    saved = store.save({"default_format": "mp3", "max_duration_warning_minutes": 12})
    loaded = store.load()
    assert saved.default_format == "mp3"
    assert loaded.default_format == "mp3"
    assert loaded.max_duration_warning_minutes == 12


def test_settings_migrates_video_defaults(tmp_path: Path):
    store = SettingsStore(tmp_path / "settings.json")
    saved = store.save({"default_format": "mp4", "default_quality": "720"})
    assert saved.default_format == "mp3"
    assert saved.default_quality == "audio-best"


def test_history_save_load_remove_clear(tmp_path: Path):
    store = HistoryStore(tmp_path / "history.json")
    items = store.add(HistoryItem.now("Title", "https://example.com", "mp3", "C:/x.mp3", "success"))
    assert len(items) == 1
    assert store.load()[0]["title"] == "Title"
    assert store.remove(0) == []
    store.add(HistoryItem.now("Again", "https://example.com", "mp3", "C:/x.mp3", "failed"))
    store.clear()
    assert store.load() == []


def test_ffmpeg_detection_with_mocked_missing_path(tmp_path: Path):
    assert probe("custom", str(tmp_path / "missing" / "ffmpeg.exe"))["ready"] is False


def test_managed_ffmpeg_extracts_required_bins(tmp_path: Path):
    archive_path = tmp_path / "ffmpeg.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("ffmpeg-essentials/bin/ffmpeg.exe", b"ffmpeg")
        archive.writestr("ffmpeg-essentials/bin/ffprobe.exe", b"ffprobe")
        archive.writestr("ffmpeg-essentials/doc/readme.txt", b"ignored")

    install_dir = tmp_path / "managed"
    ffmpeg_path = extract_managed_ffmpeg(archive_path, install_dir)

    assert ffmpeg_path == install_dir / "bin" / "ffmpeg.exe"
    assert (install_dir / "bin" / "ffprobe.exe").exists()
    assert not (install_dir / "doc" / "readme.txt").exists()


def test_managed_ffmpeg_probe_uses_app_folder(tmp_path: Path, monkeypatch):
    bin_dir = tmp_path / "ffmpeg" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "ffmpeg.exe").write_text("", encoding="utf-8")
    (bin_dir / "ffprobe.exe").write_text("", encoding="utf-8")
    monkeypatch.setattr("musicxcst_downloader.backend.ffmpeg.managed_ffmpeg_dir", lambda: tmp_path / "ffmpeg")

    status = probe("managed")

    assert status["ffmpeg_path"].endswith("ffmpeg.exe")
    assert status["ffprobe_path"].endswith("ffprobe.exe")


def test_format_selector_quality():
    assert build_format_selector("mp3", "audio-best") == "bestaudio/best"
    assert build_format_selector("flac", "audio-small") == "bestaudio/best"


def test_dolby_atmos_format_detection():
    assert format_supports_dolby_atmos({"format_note": "Dolby Atmos", "acodec": "ec-3"})
    assert format_supports_dolby_atmos({"acodec": "eac3"})
    assert not format_supports_dolby_atmos({"format_note": "medium", "acodec": "mp4a.40.2"})


def test_external_link_validation_and_open(monkeypatch):
    opened = []
    monkeypatch.setattr("musicxcst_downloader.backend.external.webbrowser.open", lambda url, **_: opened.append(url))
    assert is_safe_external_url("https://github.com/B1progame/musicXCST")
    assert not is_safe_external_url("file:///C:/secret")
    assert open_external_url("https://github.com/B1progame/musicXCST")["ok"]
    assert opened == ["https://github.com/B1progame/musicXCST"]
    assert not open_external_url("javascript:alert(1)")["ok"]


def test_ytdlp_version_status_is_string():
    assert isinstance(installed_ytdlp_version(), str)
    assert installed_ytdlp_version() != "not installed"


def test_browser_url_accepts_urls_and_builds_google_search():
    assert normalize_browser_url("youtube.com/watch?v=1") == "https://youtube.com/watch?v=1"
    assert normalize_browser_url("lofi music") == "https://www.google.com/search?q=lofi+music"
