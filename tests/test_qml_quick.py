"""Pytest integration for Qt Quick Test (tst_*.qml) and QGuiApplication startup."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
QML_RUNNER = ROOT_DIR / "tests" / "qml" / "run_qml_tests.py"


def test_qml_keyboard_shortcuts_via_qt_quick_test() -> None:
    env = os.environ.copy()
    env.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    proc = subprocess.run(
        [sys.executable, str(QML_RUNNER), "-v2"],
        cwd=str(ROOT_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    output = proc.stdout + "\n" + proc.stderr
    assert proc.returncode == 0, f"Qt Quick Test failed:\n{output}"
    assert "PASS   : FlightLinkQmlTests::KeySmokeView::test_ctrl_k_focuses_search_and_emits_shortcut()" in output
    assert "PASS   : FlightLinkQmlTests::KeySmokeView::test_escape_clears_search_and_emits_shortcut()" in output
    assert "PASS   : FlightLinkQmlTests::LoginPage::test_login_card_width_and_no_prefilled_credentials()" in output
    assert "PASS   : FlightLinkQmlTests::LoginPage::test_keyboard_login_submission_and_password_toggle()" in output
    assert "PASS   : FlightLinkQmlTests::LoginPage::test_escape_clears_login_error()" in output
    assert "PASS   : FlightLinkQmlTests::DetailAndShellResponsive::test_detail_1280_shows_services_12_cards_and_tabbed_logs()" in output
    assert "PASS   : FlightLinkQmlTests::DetailAndShellResponsive::test_detail_1440_and_1600_show_dual_pane_logs()" in output
    assert "PASS   : FlightLinkQmlTests::DetailAndShellResponsive::test_shell_sidebar_narrows_at_1280_and_shortcuts_navigate()" in output
    assert "PASS   : FlightLinkQmlTests::HistorySaveStates::test_retry_button_only_visible_for_failed_and_hidden_for_saved_and_source_gaps()" in output


def test_minimal_qguiapplication_window_launch_and_clean_exit(tmp_path: Path) -> None:
    env = os.environ.copy()
    env.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env["FLIGHTLINK_DATA_DIR"] = str(tmp_path / "appdata")
    proc = subprocess.run(
        [sys.executable, "-m", "flightlink_desktop", "--smoke-exit-ms", "200", "--skip-restore"],
        cwd=str(ROOT_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    output = proc.stdout + "\n" + proc.stderr
    assert proc.returncode == 0, f"App startup failed:\n{output}"


def test_app_excludes_forbidden_qt_modules(tmp_path: Path) -> None:
    env = os.environ.copy()
    env.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env["FLIGHTLINK_DATA_DIR"] = str(tmp_path / "appdata")
    code = (
        "import sys; "
        "from flightlink_desktop import app; "
        "rc = app.main(['--smoke-exit-ms', '100', '--skip-restore']); "
        "forbidden = [m for m in sys.modules if 'QtWidgets' in m or 'QtWebEngine' in m or 'PyQt6' in m]; "
        "assert rc == 0, f'rc={rc}'; "
        "assert not forbidden, f'Forbidden modules loaded: {forbidden}'"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(ROOT_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    output = proc.stdout + "\n" + proc.stderr
    assert proc.returncode == 0, f"Forbidden module check failed:\n{output}"
