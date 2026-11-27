"""OS-resolved archive storage paths with strict opaque-ID containment and fixed filenames."""

from __future__ import annotations

import ctypes
import os
import platform
import re
from pathlib import Path
from urllib.parse import quote
from uuid import UUID

FIXED_SOURCE_FILENAMES: dict[str, str] = {
    "router": "router.log",
    "mavproxy": "mavproxy.log",
    "metadata": "metadata.json",
}

_WINDOWS_RESERVED = frozenset(
    {
        "CON", "PRN", "AUX", "NUL",
        "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
        "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
    }
)
_SAFE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def resolve_default_logs_root() -> Path:
    """Resolve real local Documents folder via Windows SHGetKnownFolderPath(FOLDERID_Documents).

    Supports redirected Documents folders (OneDrive, D:\\Documents, etc.).
    ECS NEVER dictates client filesystem paths.
    """
    if platform.system() == "Windows":
        try:
            class GUID(ctypes.Structure):
                _fields_ = [
                    ("Data1", ctypes.c_ulong),
                    ("Data2", ctypes.c_ushort),
                    ("Data3", ctypes.c_ushort),
                    ("Data4", ctypes.c_ubyte * 8),
                ]

            # FOLDERID_Documents = {FDD39AD0-238F-46AF-ADB4-6C85480369C7}
            u = UUID("FDD39AD0-238F-46AF-ADB4-6C85480369C7")
            guid = GUID(u.time_low, u.time_mid, u.time_hi_version, (ctypes.c_ubyte * 8)(*u.bytes[8:]))
            path_ptr = ctypes.c_wchar_p()
            hr = ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(path_ptr))
            if hr == 0 and path_ptr.value:
                docs = Path(path_ptr.value)
                ctypes.windll.ole32.CoTaskMemFree(path_ptr)
                return docs / "FlightLink" / "Logs"
        except Exception:
            pass
        return Path.home() / "Documents" / "FlightLink" / "Logs"

    xdg_docs = os.environ.get("XDG_DOCUMENTS_DIR")
    if xdg_docs:
        return Path(xdg_docs).expanduser() / "FlightLink" / "Logs"
    return Path.home() / "Documents" / "FlightLink" / "Logs"


def resolve_default_state_db_path() -> Path:
    """Task SQLite DB lives in %LOCALAPPDATA%\\FlightLink\\archive_sync.sqlite3."""
    override = os.environ.get("FLIGHTLINK_DATA_DIR")
    if override:
        return Path(override) / "archive_sync.sqlite3"
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "FlightLink" / "archive_sync.sqlite3"
    return Path.home() / ".flightlink" / "archive_sync.sqlite3"


def sanitize_opaque_segment(raw_id: str, *, field_name: str) -> str:
    """Convert an opaque server ID into a single collision-free, traversal-proof directory segment."""
    val = (raw_id or "").strip()
    if not val:
        raise ValueError(f"Empty opaque identifier for {field_name}")

    # Fast path for clean ASCII IDs without dot-dot or trailing dots/spaces
    if (
        _SAFE_SEGMENT_RE.match(val)
        and val not in (".", "..")
        and ".." not in val
        and not val.endswith(".")
        and val.upper() not in _WINDOWS_RESERVED
    ):
        return val

    # Percent-encode unsafe characters deterministically so distinct IDs never collide
    encoded = quote(val, safe="")
    if not encoded or encoded in (".", "..") or encoded.upper() in _WINDOWS_RESERVED:
        encoded = f"id_{encoded}"
    return encoded


def safe_archive_file_path(
    logs_root: Path,
    ecs_instance_id: str,
    group_id: str,
    session_id: str,
    source: str,
) -> Path:
    """Build `<logs_root>/<ecs_instance_id>/<group_id>/<session_id>/<fixed_filename>`.

    - Ignores remote filenames/paths completely (fixed filenames only).
    - Guarantees resolved target path strictly stays inside `logs_root`.
    """
    filename = FIXED_SOURCE_FILENAMES.get(source)
    if filename is None:
        raise ValueError(f"Unsupported archive source: {source!r}")

    root_resolved = logs_root.resolve()
    seg_ecs = sanitize_opaque_segment(ecs_instance_id, field_name="ecs_instance_id")
    seg_grp = sanitize_opaque_segment(group_id, field_name="group_id")
    seg_sess = sanitize_opaque_segment(session_id, field_name="session_id")

    candidate = (root_resolved / seg_ecs / seg_grp / seg_sess / filename).resolve()
    if not candidate.is_relative_to(root_resolved):
        raise ValueError(f"Resolved archive path escaped logs root: {candidate}")
    return candidate
