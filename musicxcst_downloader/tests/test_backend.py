from pathlib import Path
import zipfile
import json
import io
from urllib.error import HTTPError

from musicxcst_downloader.backend.downloader import (
    DownloadWorker,
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
from musicxcst_downloader.backend import app_updater


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


def test_settings_migration_preserves_existing_preferences(tmp_path: Path):
    path = tmp_path / "settings.json"
    path.write_text(
        '{"default_output_folder":"C:/Music","accent_color":"#ff00aa","open_folder_after_download":true}',
        encoding="utf-8",
    )
    loaded = SettingsStore(path).load()
    assert loaded.default_output_folder == "C:/Music"
    assert loaded.accent_color == "#ff00aa"
    assert loaded.open_folder_after_download is True
    assert loaded.default_mode == "audio"


def test_settings_migrates_video_defaults(tmp_path: Path):
    store = SettingsStore(tmp_path / "settings.json")
    saved = store.save({"default_mode": "video-audio", "default_format": "mp4", "default_video_quality": "720"})
    assert saved.default_mode == "video-audio"
    assert saved.default_format == "mp4"
    assert saved.default_video_quality == "720"


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


def test_format_selector_video_modes():
    assert build_format_selector("mp4", "1080", "video") == "bestvideo[height<=1080]/bestvideo/best"
    assert build_format_selector("mkv", "best", "video-audio") == "bestvideo+bestaudio/best"


def test_video_download_builds_merge_options(tmp_path: Path, monkeypatch):
    captured = {}

    class FakeYoutubeDL:
        def __init__(self, options):
            captured.update(options)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def download(self, urls):
            captured["urls"] = urls

    monkeypatch.setattr("musicxcst_downloader.backend.downloader.YoutubeDL", FakeYoutubeDL)
    monkeypatch.setattr(
        "musicxcst_downloader.backend.downloader.probe",
        lambda *_: {"ready": True, "ffmpeg_path": str(tmp_path / "ffmpeg.exe")},
    )
    events = []
    worker = DownloadWorker(events.append)
    worker._download(
        {
            "url": "https://example.com/video",
            "mode": "video-audio",
            "format": "mp4",
            "quality": "1080",
            "output_folder": str(tmp_path),
            "filename": "clip.mp4",
        },
        "custom",
        str(tmp_path / "ffmpeg.exe"),
    )

    assert captured["format"] == "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
    assert captured["merge_output_format"] == "mp4"
    assert captured["postprocessors"][0]["key"] == "FFmpegVideoRemuxer"
    assert events[-1]["type"] == "complete"


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


def test_app_update_retries_private_github_api_with_logged_in_cli(monkeypatch):
    response_data = {
        "tag_name": "v2.0.1",
        "html_url": "https://github.com/B1progame/musicXCST-down/releases/tag/v2.0.1",
        "assets": [],
    }

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps(response_data).encode("utf-8")

    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        if len(requests) == 1:
            raise HTTPError(request.full_url, 404, "Not Found", {}, io.BytesIO())
        return Response()

    monkeypatch.setattr(app_updater.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(
        app_updater,
        "shutil",
        type("Shutil", (), {"which": staticmethod(lambda name: "gh.exe")}),
        raising=False,
    )
    monkeypatch.setattr(
        app_updater.subprocess,
        "run",
        lambda *args, **kwargs: type("Result", (), {"stdout": "github-token\n", "returncode": 0})(),
    )

    result = app_updater.check_for_update("2.0.0")

    assert result["version"] == "2.0.1"
    assert requests[1].get_header("Authorization") == "Bearer github-token"
