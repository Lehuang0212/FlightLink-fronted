"""Build and audit the Windows x64 portable bundle for FlightLink Desktop 1.0."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "packaging" / "flightlink_desktop.spec"
DIST_DIR = ROOT / "dist" / "FlightLinkDesktop"
EXE_PATH = DIST_DIR / "FlightLinkDesktop.exe"


def main() -> int:
    pyinstaller = Path(sys.executable).parent / "pyinstaller.exe"
    if not pyinstaller.exists():
        raise FileNotFoundError(f"PyInstaller not found at {pyinstaller}")

    print(f"Building Windows x64 bundle with {pyinstaller} ...")
    subprocess.run(
        [
            str(pyinstaller),
            "--noconfirm",
            "--clean",
            "--distpath",
            str(ROOT / "dist"),
            "--workpath",
            str(ROOT / "build" / "pyinstaller"),
            str(SPEC),
        ],
        cwd=str(ROOT),
        check=True,
    )

    assert EXE_PATH.exists(), f"Missing executable: {EXE_PATH}"

    all_files = [p.relative_to(DIST_DIR).as_posix() for p in DIST_DIR.rglob("*") if p.is_file()]
    lower_files = [f.lower() for f in all_files]

    # Audit forbidden items
    forbidden_hits = [
        f
        for f in all_files
        if any(
            bad in f.lower()
            for bad in (".agent/", "qt6webengine", "qtwebengine", "qt6widgets", "qtwidgets", "pyqt6")
        )
    ]
    assert not forbidden_hits, f"Forbidden artifacts found in bundle: {forbidden_hits}"

    # Audit required runtime pieces: QML modules, Windows platform plugin, TLS CA bundle
    has_qwindows = any(f.endswith("platforms/qwindows.dll") for f in lower_files)
    has_qtquick = any("qml/qtquick/" in f for f in lower_files)
    has_app_qml = any(f.endswith("flightlink_desktop/qml/main.qml") for f in lower_files)
    has_cacert = any(f.endswith("certifi/cacert.pem") for f in lower_files)

    print(f"Bundle files: {len(all_files)}")
    print(f"  qwindows.dll present : {has_qwindows}")
    print(f"  QtQuick QML present  : {has_qtquick}")
    print(f"  App Main.qml present : {has_app_qml}")
    print(f"  certifi CA present   : {has_cacert}")
    print(f"  Forbidden hits       : {len(forbidden_hits)}")
    assert has_qwindows and has_qtquick and has_app_qml and has_cacert

    # Smoke-launch packaged executable with clean PATH/PYTHONPATH
    with tempfile.TemporaryDirectory() as tmp:
        clean_env = {
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", r"C:\Windows"),
            "WINDIR": os.environ.get("WINDIR", r"C:\Windows"),
            "TEMP": tmp,
            "TMP": tmp,
            "USERPROFILE": os.environ.get("USERPROFILE", tmp),
            "FLIGHTLINK_DATA_DIR": str(Path(tmp) / "appdata"),
        }
        proc = subprocess.run(
            [str(EXE_PATH), "--smoke-exit-ms", "400", "--skip-restore"],
            cwd=str(DIST_DIR),
            env=clean_env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        print(f"Standalone EXE smoke exit code: {proc.returncode}")
        if proc.returncode != 0:
            print("STDOUT:", proc.stdout)
            print("STDERR:", proc.stderr)
            return proc.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
