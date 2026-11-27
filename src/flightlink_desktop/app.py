"""Minimal QGuiApplication + QQmlApplicationEngine entry point."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

QML_DIR = Path(__file__).resolve().parent / "qml"


def build_engine(app: QGuiApplication) -> QQmlApplicationEngine:
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(QML_DIR))
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
        help="Auto-exit cleanly after N milliseconds (P0 startup verification).",
    )
    args, qt_args = parser.parse_known_args(argv)

    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    app = QGuiApplication([sys.argv[0], *qt_args])
    app.setApplicationName("FlightLink Desktop")
    app.setOrganizationName("FlightLink")

    engine = build_engine(app)
    root = engine.rootObjects()[0]

    if args.smoke_exit_ms > 0:
        QTimer.singleShot(args.smoke_exit_ms, app.quit)

    exit_code = app.exec()
    del root
    del engine
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
