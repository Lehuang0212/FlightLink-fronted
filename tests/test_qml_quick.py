"""Pytest integration for Qt Quick Test (tst_*.qml) and QGuiApplication startup."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
QML_RUNNER = ROOT_DIR / "tests" / "qml" / "run_qml_tests.py"


def test_qml_keyboard_shortcuts_via_qt_quick_test(tmp_path: Path) -> None:
    env = os.environ.copy()
    env.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env.setdefault("PYTHONUTF8", "1")
    out_file = tmp_path / "qml_quick_results.txt"
    proc = subprocess.run(
        [sys.executable, str(QML_RUNNER), "-v2", "-o", f"{out_file},txt"],
        cwd=str(ROOT_DIR),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    file_out = out_file.read_text(encoding="utf-8", errors="replace") if out_file.exists() else ""
    output = "\n".join(part for part in (file_out, proc.stdout, proc.stderr) if part)
    assert proc.returncode == 0, f"Qt Quick Test failed:\n{output}"
    assert "PASS   : FlightLinkQmlTests::KeySmokeView::test_ctrl_k_focuses_search_and_emits_shortcut()" in output
    assert "PASS   : FlightLinkQmlTests::KeySmokeView::test_escape_clears_search_and_emits_shortcut()" in output
    assert "PASS   : FlightLinkQmlTests::LoginPage::test_login_card_width_and_no_prefilled_credentials()" in output
    assert "PASS   : FlightLinkQmlTests::LoginPage::test_keyboard_login_submission_and_password_toggle()" in output
    assert "PASS   : FlightLinkQmlTests::LoginPage::test_escape_clears_login_error()" in output
    assert "PASS   : FlightLinkQmlTests::LoginPage::test_overflowing_disconnect_error_activates_marquee_scrolling()" in output
    assert "PASS   : FlightLinkQmlTests::LoginPage::test_credentials_and_show_password_cleared_on_auth_and_logout()" in output
    assert "PASS   : FlightLinkQmlTests::LoginPage::test_minimum_size_error_does_not_overlap_top_edge()" in output
    assert "PASS   : FlightLinkQmlTests::DetailAndShellResponsive::test_detail_1280_shows_services_12_cards_and_tabbed_logs()" in output
    assert "PASS   : FlightLinkQmlTests::DetailAndShellResponsive::test_detail_1440_and_1600_show_dual_pane_logs()" in output
    assert "PASS   : FlightLinkQmlTests::DetailAndShellResponsive::test_shell_sidebar_narrows_at_1280_and_shortcuts_navigate()" in output
    assert "PASS   : FlightLinkQmlTests::HistorySaveStates::test_retry_button_only_visible_for_failed_and_hidden_for_saved_and_source_gaps()" in output
    assert "PASS   : FlightLinkQmlTests::CloseConfirmDialog::test_close_dialog_fits_compact_window_and_emits_actions()" in output


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


def test_close_button_opens_confirm_dialog_and_tray_lifecycle_without_qtwidgets(tmp_path: Path) -> None:
    env = os.environ.copy()
    env.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env["FLIGHTLINK_DATA_DIR"] = str(tmp_path / "appdata")
    code = (
        "import sys; "
        "from PySide6.QtGui import QGuiApplication; "
        "from PySide6.QtQuick import QQuickWindow; "
        "from flightlink_desktop.app import DesktopRuntime, build_engine; "
        "app = QGuiApplication(['test']); "
        "app.setQuitOnLastWindowClosed(False); "
        "rt = DesktopRuntime(app); "
        "eng = build_engine(app, rt); "
        "win = eng.rootObjects()[0]; "
        "restored = []; quit_hits = []; "
        "rt.tray_controller.restoreRequested.connect(lambda: restored.append(1)); "
        "rt.tray_controller.quitRequested.connect(lambda: quit_hits.append(1)); "
        "win.close(); app.processEvents(); "
        "assert win.property('closeDialogOpen') is True, 'close() must open confirm dialog'; "
        "assert win.isVisible() is True, 'window must stay visible until user chooses'; "
        "win.hideToBackgroundTray(); app.processEvents(); "
        "assert win.property('closeDialogOpen') is False; "
        "assert win.isVisible() is False, 'hideToBackgroundTray must hide main window'; "
        "assert rt.tray_controller.inTray is True; "
        "rt.tray_controller.restoreFromTray(); app.processEvents(); "
        "assert rt.tray_controller.inTray is False; "
        "assert len(restored) == 1; "
        "win.performFullQuit(); app.processEvents(); "
        "assert win.property('allowImmediateClose') is True; "
        "assert len(quit_hits) == 1; "
        "forbidden = [m for m in sys.modules if 'QtWidgets' in m or 'QtWebEngine' in m or 'PyQt6' in m]; "
        "assert not forbidden, f'Forbidden modules loaded: {forbidden}'; "
        "rt.shutdown()"
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
    assert proc.returncode == 0, f"Tray/close lifecycle check failed:\n{output}"
