from pathlib import Path


ROOT = Path(__file__).parents[1]
FRONTEND = ROOT / "src" / "musicxcst_downloader" / "frontend"


def test_update_reminder_and_animated_settings_control_are_present():
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    css = (FRONTEND / "styles.css").read_text(encoding="utf-8")
    js = (FRONTEND / "app.js").read_text(encoding="utf-8")

    assert 'id="updateReminder"' in html
    assert 'class="nav-item settings-nav rainbow-settings"' in html
    assert ".rainbow-settings" in css
    assert "check_app_update" in js
