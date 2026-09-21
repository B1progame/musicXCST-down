import importlib.util
import zipfile
from pathlib import Path


def load_installer_module():
    source = Path(__file__).parents[1] / "installer" / "terminal_installer.py"
    spec = importlib.util.spec_from_file_location("terminal_installer", source)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_install_payload_copies_app_without_touching_user_data(tmp_path: Path):
    installer = load_installer_module()
    payload = tmp_path / "payload.zip"
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("MusicXCST Downloader/MusicXCST Downloader.exe", b"new app")
        archive.writestr("MusicXCST Downloader/_internal/version.txt", b"2.0.2")

    target = tmp_path / "Programs" / "MusicXCST Downloader"
    user_data = tmp_path / "AppData" / "settings.json"
    user_data.parent.mkdir(parents=True)
    user_data.write_text('{"accent_color":"#ff00aa"}', encoding="utf-8")

    result = installer.install_payload(payload, target, log=lambda _: None)

    assert result == target
    assert (target / "MusicXCST Downloader.exe").read_bytes() == b"new app"
    assert (target / "_internal" / "version.txt").read_text(encoding="utf-8") == "2.0.2"
    assert user_data.read_text(encoding="utf-8") == '{"accent_color":"#ff00aa"}'


def test_terminal_installer_formats_real_progress_bar():
    installer = load_installer_module()
    assert installer.format_progress(50) == "[#####-----] 50%"


def test_installer_uses_visual_progress_and_waits_for_previous_app():
    source = (Path(__file__).parents[1] / "installer" / "terminal_installer.py").read_text(encoding="utf-8")
    assert "tkinter" in source
    assert "--wait-pid" in source
    assert "Circular progress" in source


def test_installer_progress_parser_ignores_install_destination_text():
    installer = load_installer_module()
    assert installer.progress_from_log("Installing to C:\\Users\\test\\MusicXCST Downloader") == 4
    assert installer.progress_from_log("Installing [#####-----] 50%") == 50
