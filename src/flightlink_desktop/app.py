"""FlightLink Desktop 1.0 application bootstrap (QGuiApplication + QQmlApplicationEngine)."""

from __future__ import annotations

import argparse
import ctypes
import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QGuiApplication, QIcon, QWindow
from PySide6.QtQml import QQmlApplicationEngine

from flightlink_desktop.api.auth import AuthCoordinator
from flightlink_desktop.api.client import FlightLinkApiClient
from flightlink_desktop.api.credentials import CredentialStore
from flightlink_desktop.archive.sync_engine import ArchiveSyncEngine
from flightlink_desktop.archive.worker import ArchiveSyncWorker
from flightlink_desktop.models.operations_vm import OperationsViewModel
from flightlink_desktop.models.session_vm import SessionViewModel
from flightlink_desktop.models.workspace_vm import WorkspaceViewModel
from flightlink_desktop.tray import TrayController, bring_window_to_foreground, resolve_app_icon_path
from flightlink_desktop.workers.task_runner import BackgroundTaskRunner

def _resolve_qml_dir() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidate = Path(meipass) / "flightlink_desktop" / "qml"
        if candidate.exists():
            return candidate
    return Path(__file__).resolve().parent / "qml"


QML_DIR = _resolve_qml_dir()


class DesktopRuntime:
    """Owns Python backend services and GUI-thread ViewModels for a single desktop app lifecycle."""

    def __init__(self, app: QGuiApplication) -> None:
        self.app = app
        self.credential_store = CredentialStore()
        self.task_runner = BackgroundTaskRunner(app)
        self.auth = AuthCoordinator(credential_store=self.credential_store)
        self.api_client = FlightLinkApiClient(self.auth)
        self.session_vm = SessionViewModel(
            api_client=self.api_client,
            auth=self.auth,
            credential_store=self.credential_store,
            task_runner=self.task_runner,
            parent=app,
        )
        self.workspace_vm = WorkspaceViewModel(
            api_client=self.api_client,
            auth=self.auth,
            task_runner=self.task_runner,
            parent=app,
        )
        self.ops_vm = OperationsViewModel(
            api_client=self.api_client,
            auth=self.auth,
            task_runner=self.task_runner,
            workspace_vm=self.workspace_vm,
            parent=app,
        )
        self.archive_engine = ArchiveSyncEngine(self.api_client)
        self.archive_worker = ArchiveSyncWorker(self.archive_engine, poll_interval_seconds=15.0, parent=app)
        self.tray_controller = TrayController(parent=app)

        self.auth._on_session_expired = self.session_vm.notify_expired_from_worker
        self.session_vm.sessionStarted.connect(self.workspace_vm.onSessionStarted)
        self.session_vm.sessionEnded.connect(self.workspace_vm.onSessionEnded)
        self.session_vm.sessionStarted.connect(self.ops_vm.onSessionStarted)
        self.session_vm.sessionEnded.connect(self.ops_vm.onSessionEnded)
        self.session_vm.sessionStarted.connect(self.archive_worker.onSessionStarted)
        self.session_vm.sessionEnded.connect(self.archive_worker.onSessionEnded)
        self.workspace_vm.manualArchiveRetryRequested.connect(self.archive_worker.enqueueManualRetry)

        self.archive_worker.snapshotReady.connect(
            self._on_archive_snapshot,
            Qt.ConnectionType.QueuedConnection,
        )
        self.archive_worker.retryFinished.connect(
            self._on_archive_retry_finished,
            Qt.ConnectionType.QueuedConnection,
        )

    def _on_archive_snapshot(self, epoch: int, snap: dict) -> None:
        if epoch != self.auth.current_epoch():
            return
        saved = int(snap.get("saved_count", 0))
        failed = int(snap.get("failed_count", 0))
        status_text = f"已自动保存 {saved} 个切片" if saved > 0 else "自动归档已启用"
        if failed > 0:
            status_text = f"自动归档失败 {failed} 个切片"
        self.workspace_vm.update_archive_summary(
            local_root=str(snap.get("local_root", "")),
            failed_count=failed,
            failed_group_id=str(snap.get("failed_group_id", "")),
            failed_session_id=str(snap.get("failed_session_id", "")),
            failed_message=str(snap.get("failed_message", "")),
            status_text=status_text,
            retention_gap_note=str(snap.get("retention_gap_note", "")),
            session_states=dict(snap.get("session_states") or {}),
        )

    def _on_archive_retry_finished(self, epoch: int, session_id: str, ok: bool, message: str) -> None:
        if epoch != self.auth.current_epoch():
            return
        self.workspace_vm.showToast(message, "info" if ok else "bad")

    def shutdown(self) -> None:
        self.tray_controller.shutdown()
        self.archive_worker.shutdown(timeout_s=3.0)
        self.ops_vm.stop_tracking()
        self.workspace_vm.stop_polling()
        self.auth.clear_session(clear_persisted_refresh=False)
        self.task_runner.shutdown(timeout_ms=3000)
        self.api_client.close()


def detect_system_reduced_motion() -> bool:
    """Query OS reduced-motion accessibility setting (Windows SPI_GETCLIENTAREAANIMATION)."""
    override = os.environ.get("FLIGHTLINK_REDUCED_MOTION", "").strip().lower()
    if override in ("1", "true", "yes", "on"):
        return True
    if override in ("0", "false", "no", "off"):
        return False
    if sys.platform == "win32":
        try:
            SPI_GETCLIENTAREAANIMATION = 0x1042
            animations_enabled = ctypes.c_int(1)
            ok = ctypes.windll.user32.SystemParametersInfoW(
                SPI_GETCLIENTAREAANIMATION,
                0,
                ctypes.byref(animations_enabled),
                0,
            )
            if ok:
                return animations_enabled.value == 0
        except Exception:
            return False
    return False


def build_engine(app: QGuiApplication, runtime: DesktopRuntime) -> QQmlApplicationEngine:
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(QML_DIR))
    engine.setInitialProperties(
        {
            "sessionVm": runtime.session_vm,
            "workspaceVm": runtime.workspace_vm,
            "opsVm": runtime.ops_vm,
            "trayVm": runtime.tray_controller,
            "systemReducedMotion": detect_system_reduced_motion(),
        }
    )

    main_qml = QML_DIR / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(main_qml)))
    if not engine.rootObjects():
        raise RuntimeError(f"Failed to load QML root from {main_qml}")
    return engine


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="flightlink-desktop")
    parser.add_argument(
        "--smoke-exit-ms",
        type=int,
        default=0,
        help="Auto-exit cleanly after N milliseconds (startup verification).",
    )
    parser.add_argument(
        "--skip-restore",
        action="store_true",
        help="Skip automatic startup session restore from OS Credential Manager.",
    )
    args, qt_args = parser.parse_known_args(argv)

    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    app = QGuiApplication([sys.argv[0], *qt_args])
    app.setApplicationName("FlightLink Desktop")
    app.setOrganizationName("FlightLink")
    app.setQuitOnLastWindowClosed(False)
    icon_path = resolve_app_icon_path()
    if icon_path is not None:
        app.setWindowIcon(QIcon(str(icon_path)))

    runtime = DesktopRuntime(app)
    engine = build_engine(app, runtime)
    root = engine.rootObjects()[0]

    def _restore_window() -> None:
        if isinstance(root, QWindow):
            if root.visibility() == QWindow.Visibility.Minimized:
                root.showNormal()
            else:
                root.show()
            root.raise_()
            root.requestActivate()
            try:
                bring_window_to_foreground(int(root.winId()))
            except Exception:
                pass

    def _quit_app() -> None:
        root.setProperty("allowImmediateClose", True)
        if isinstance(root, QWindow):
            root.close()
        app.quit()

    runtime.tray_controller.restoreRequested.connect(_restore_window)
    runtime.tray_controller.quitRequested.connect(_quit_app)

    if not args.skip_restore and args.smoke_exit_ms <= 0:
        QTimer.singleShot(0, runtime.session_vm.tryRestoreSession)

    if args.smoke_exit_ms > 0:
        QTimer.singleShot(args.smoke_exit_ms, _quit_app)

    try:
        exit_code = app.exec()
    finally:
        del root
        del engine
        runtime.shutdown()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
