"""PySide6 Qt Quick Test runner (no C++ application skeleton required)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtQuickTest import QUICK_TEST_MAIN


def main() -> int:
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    test_dir = Path(__file__).resolve().parent
    qml_root = test_dir.parents[1] / "src" / "flightlink_desktop" / "qml"
    extra_args = sys.argv[1:]
    argv = [sys.argv[0], "-import", str(qml_root), "-input", str(test_dir), *extra_args]
    return int(QUICK_TEST_MAIN("FlightLinkQmlTests", argv=argv, dir=str(test_dir)))


if __name__ == "__main__":
    raise SystemExit(main())
