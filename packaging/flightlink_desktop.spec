# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for FlightLink Desktop 1.0 Windows x64 portable bundle.

- Includes Qt Quick / QML modules, Windows platform plugin, and certifi CA bundle.
- Excludes .agent/, docs/, tests/, QtWidgets, QtWebEngine*, PyQt6, Qt3D*, QtPdf*, tkinter.
"""

from pathlib import Path
import certifi
import PySide6

project_root = Path(SPECPATH).resolve().parent
src_dir = project_root / "src"
qml_src = src_dir / "flightlink_desktop" / "qml"
assets_src = src_dir / "flightlink_desktop" / "assets"
ico_path = assets_src / "flightlink.ico"
pyside_dir = Path(PySide6.__file__).resolve().parent

datas = [
    (str(qml_src), "flightlink_desktop/qml"),
    (str(Path(certifi.where())), "certifi"),
]
if assets_src.exists():
    datas.append((str(assets_src), "flightlink_desktop/assets"))

# Include required Qt6 QML modules explicitly (no QtWebEngine / QtWidgets / Qt3D)
qml_root = pyside_dir / "qml"
for mod in ("QtQuick", "QtQml", "QtCore", "Qt"):
    mod_path = qml_root / mod
    if mod_path.exists():
        datas.append((str(mod_path), f"PySide6/qml/{mod}"))

# Include essential Qt platform & TLS plugins
plugins_root = pyside_dir / "plugins"
for plug_group in ("platforms", "tls", "imageformats", "iconengines", "qmltooling"):
    p = plugins_root / plug_group
    if p.exists():
        datas.append((str(p), f"PySide6/plugins/{plug_group}"))

excludes = [
    "PySide6.QtWidgets",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebChannel",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
    "PySide6.QtPdf",
    "PySide6.QtMultimedia",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtQuickTest",
    "PyQt6",
    "tkinter",
    "pytest",
    "freezegun",
]

a = Analysis(
    [str(src_dir / "flightlink_desktop" / "__main__.py")],
    pathex=[str(src_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "keyring.backends.Windows",
        "win32ctypes.pywin32.win32cred",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuickControls2",
        "PySide6.QtNetwork",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

# Filter out any accidental Qt6Widgets / Qt6WebEngine / Qt6Test / .agent artifacts
def _is_forbidden(name: str) -> bool:
    low = name.lower().replace("\\", "/")
    blocked_tokens = (
        "qt6webengine",
        "qtwebengine",
        "qt6widgets",
        "qtwidgets",
        "qt6test",
        "qt6quicktest",
        "qt6pdf",
        "qt63d",
        "qt6multimedia",
        "/.agent/",
        "\\.agent\\",
    )
    return any(tok in low for tok in blocked_tokens)

a.binaries = [b for b in a.binaries if not _is_forbidden(b[0]) and not _is_forbidden(b[1])]
a.datas = [d for d in a.datas if not _is_forbidden(d[0]) and not _is_forbidden(d[1])]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FlightLinkDesktop",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ico_path) if ico_path.is_file() else None,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="FlightLinkDesktop",
)
