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
    assert '"setVideoQuality"' in js
    assert "current_version" in js
    assert "latest_version" in js
    assert "Update available" in js
    assert "flushSettingsSave" in js


def test_v4_interface_has_clear_navigation_and_accessible_feedback():
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    css = (FRONTEND / "styles.css").read_text(encoding="utf-8")

    assert 'aria-label="Primary navigation"' in html
    assert 'class="eyebrow"' in html
    assert 'class="section-kicker">STEP 1' in html
    assert '<svg aria-hidden="true" viewBox="0 0 24 24"><path d="M12 4 21 20H3L12 4Z"' in html
    assert "--line-strong" in css
    assert "button:focus-visible" in css
    assert "button:disabled" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
