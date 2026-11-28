"""Build the Windows x64 single-file Setup executable and SHA256SUMS for release."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST_BUNDLE = ROOT / "dist" / "FlightLinkDesktop"
RELEASE_DIR = ROOT / "dist" / "release"
ISS_PATH = ROOT / "packaging" / "flightlink_installer.iss"


def find_iscc() -> Path:
    candidates = [
        shutil.which("iscc"),
        shutil.which("ISCC"),
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe"),
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
    ]
    for cand in candidates:
        if cand and Path(cand).is_file():
            return Path(cand)
    raise FileNotFoundError("Inno Setup 6 compiler (ISCC.exe) not found.")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def main() -> int:
    tag = sys.argv[1] if len(sys.argv) > 1 else "FlightLinkDesktop-v1.0"
    version = sys.argv[2] if len(sys.argv) > 2 else "1.0.0"

    if not (DIST_BUNDLE / "FlightLinkDesktop.exe").is_file():
        raise FileNotFoundError(
            f"Portable bundle missing at {DIST_BUNDLE}. Run scripts/build_windows.py first."
        )

    iscc = find_iscc()
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Compiling installer with {iscc} (tag={tag}, version={version}) ...")
    subprocess.run(
        [
            str(iscc),
            f"/DMyReleaseTag={tag}",
            f"/DMyAppVersion={version}",
            str(ISS_PATH),
        ],
        cwd=str(ROOT),
        check=True,
    )

    setup_exe = RELEASE_DIR / f"{tag}-Setup.exe"
    assert setup_exe.is_file(), f"Expected installer missing: {setup_exe}"

    digest = sha256_file(setup_exe)
    checksums = RELEASE_DIR / "SHA256SUMS.txt"
    checksums.write_text(f"{digest}  {setup_exe.name}\n", encoding="utf-8")

    size_mb = setup_exe.stat().st_size / (1024 * 1024)
    print(f"Installer built: {setup_exe} ({size_mb:.2f} MiB)")
    print(f"SHA-256        : {digest}")
    print(f"Checksums file : {checksums}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
