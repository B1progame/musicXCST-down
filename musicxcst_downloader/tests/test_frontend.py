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


def test_update_visuals_are_conditional_and_restart_is_wired():
    css = (FRONTEND / "styles.css").read_text(encoding="utf-8")
    js = (FRONTEND / "app.js").read_text(encoding="utf-8")
    app = (ROOT / "src" / "musicxcst_downloader" / "app.py").read_text(encoding="utf-8")

    assert ".rainbow-settings.rainbow-active" in css
    assert "classList.toggle(\"rainbow-active\"" in js
    assert "Restarting the app" in js
    assert '"restart": True' in app
    assert "restart_application" in app


def test_aurora_has_coordinated_page_and_dropdown_motion():
    css = (FRONTEND / "styles.css").read_text(encoding="utf-8")
    js = (FRONTEND / "app.js").read_text(encoding="utf-8")

    assert "page-exiting" in js
    assert "page-entering" in js
    assert "@keyframes auroraPanelEnter" in css
    assert 'html[data-theme="aurora"] select:hover' in css
    assert "appearance: none" in css
    assert ".rainbow-settings::before" in css


def test_app_update_button_stays_enabled_when_current():
    js = (FRONTEND / "app.js").read_text(encoding="utf-8")

    assert 'event.available === false ? "Check for updates"' in js
    assert 'event.available === false ? "Check for updates" : "Update App"), true' in js


def test_startup_waits_for_pywebview_bridge_and_reports_failures():
    js = (FRONTEND / "app.js").read_text(encoding="utf-8")

    assert 'window.addEventListener("pywebviewready", startInitialization' in js
    assert "if (initStarted) return;" in js
    assert 'Could not connect to the app bridge.' in js


def test_video_download_is_visible_in_first_run_and_download_copy():
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    legal = (ROOT / "src" / "musicxcst_downloader" / "backend" / "legal.py").read_text(encoding="utf-8")

    assert "music, audio, or video" in html
    assert "Music, audio, or video link" in html
    assert "music, audio, or video" in legal
    assert 'value="video"' in html
    assert 'value="video-audio"' in html


def test_embedded_browser_tracks_content_scroll():
    js = (FRONTEND / "app.js").read_text(encoding="utf-8")

    assert 'document.querySelector(".content")' in js
    assert 'addEventListener("scroll", scheduleBrowserLayout' in js
    assert "requestAnimationFrame(() =>" in js


def test_start_screen_is_shown_on_every_launch_and_only_dismissed_for_session():
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    js = (FRONTEND / "app.js").read_text(encoding="utf-8")

    assert 'id="firstRun" class="notice-backdrop">' in html
    assert '$("firstRun").classList.remove("hidden")' in js
    assert '$("firstRun").classList.add("hidden")' in js
    assert 'saveSettingsPatch({ first_run_confirmed: true })' not in js


def test_analyze_link_has_visible_indeterminate_progress_state():
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    css = (FRONTEND / "styles.css").read_text(encoding="utf-8")
    js = (FRONTEND / "app.js").read_text(encoding="utf-8")

    assert 'id="workflowStatusText">Ready</span>' in html
    assert 'class="analyze-btn-content"' in html
    assert ".analyze-spinner" in css
    assert ".analysis-active .progress-bar" in css
    assert "function setAnalysisState" in js
    assert "setAnalysisState(true" in js
    assert "setAnalysisState(false" in js
