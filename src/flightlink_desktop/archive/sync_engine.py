"""Durable, instance-isolated local archive auto-save engine with streaming .part verification and crash recovery."""

from __future__ import annotations

import errno
import hashlib
import os
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx

from flightlink_desktop.api.client import FlightLinkApiClient
from flightlink_desktop.api.errors import ApiError, NetworkError, SessionInvalidatedError
from flightlink_desktop.archive.paths import (
    FIXED_SOURCE_FILENAMES,
    resolve_default_logs_root,
    resolve_default_state_db_path,
    safe_archive_file_path,
)

CHUNK_SIZE = 65536

ARCHIVE_SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sync_cursors (
    ecs_instance_id TEXT PRIMARY KEY,
    cursor TEXT,
    last_sync_at TEXT,
    retention_gap_detected INTEGER NOT NULL DEFAULT 0,
    retention_gap_note TEXT
);

CREATE TABLE IF NOT EXISTS local_sessions (
    ecs_instance_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    group_id TEXT NOT NULL,
    group_name_snapshot TEXT NOT NULL,
    group_deleted INTEGER NOT NULL DEFAULT 0,
    ended_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    close_reason TEXT NOT NULL,
    local_status TEXT NOT NULL CHECK (local_status IN (
        'pending', 'downloading', 'saved', 'saved_with_source_gaps', 'failed', 'expired_on_server'
    )),
    last_error_category TEXT,
    last_error_message TEXT,
    show_retry_action INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (ecs_instance_id, session_id)
);

CREATE TABLE IF NOT EXISTS local_files (
    ecs_instance_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('router', 'mavproxy', 'metadata')),
    file_id TEXT,
    logical_name TEXT NOT NULL,
    server_availability TEXT NOT NULL,
    server_missing_reason TEXT,
    expected_size INTEGER,
    expected_sha256 TEXT,
    local_path TEXT,
    status TEXT NOT NULL CHECK (status IN (
        'pending', 'verified', 'missing_on_server', 'failed', 'expired_on_server'
    )),
    error_category TEXT,
    error_message TEXT,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (ecs_instance_id, session_id, source),
    FOREIGN KEY (ecs_instance_id, session_id) REFERENCES local_sessions(ecs_instance_id, session_id) ON DELETE CASCADE
);
"""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def sha256_file(path: Path) -> tuple[str, int]:
    h = hashlib.sha256()
    total = 0
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(CHUNK_SIZE)
            if not chunk:
                break
            h.update(chunk)
            total += len(chunk)
    return h.hexdigest(), total


def classify_os_error(exc: OSError) -> tuple[str, str]:
    if isinstance(exc, PermissionError) or exc.errno in (errno.EACCES, errno.EPERM):
        return "disk_permission_denied", f"本机目录无写权限，请检查文档目录权限：{exc}"
    if exc.errno == errno.ENOSPC:
        return "disk_full", f"本机磁盘空间不足，请清理空间后重试：{exc}"
    return "disk_io_error", f"本机磁盘写入异常：{exc}"


@dataclass
class SyncCycleSummary:
    discovered_sessions: int = 0
    files_downloaded: int = 0
    files_recovered_from_disk: int = 0
    files_skipped_verified: int = 0
    files_failed: int = 0
    files_expired: int = 0
    retention_gap_detected: bool = False
    retention_gap_note: str | None = None
    cancelled: bool = False


class ArchiveSyncEngine:
    """Instance-isolated local auto-save engine sharing FlightLinkApiClient / AuthCoordinator.

    Guarantees:
    - Cursor & pending tasks strictly scoped by `ecs_instance_id` (NEVER global latest cursor).
    - Single SQLite transaction inserts deduplicated tasks BEFORE advancing `next_cursor`.
    - Streams via `httpx.stream()` to `.part`, checks length + manifest SHA-256 + `X-Content-SHA256`,
      then `os.replace()` + SQLite commit.
    - Crash recovery checks already-renamed verified files on disk before re-downloading.
    - Per-file mutex guarantees no concurrent writes to the same target file.
    - Cancellable mid-stream on logout/close.
    """

    def __init__(
        self,
        api_client: FlightLinkApiClient,
        *,
        logs_root: Path | None = None,
        state_db_path: Path | None = None,
        max_auto_attempts: int = 2,
        max_cursor_resets_per_cycle: int = 1,
        write_hook: Callable[[Path, bytes], None] | None = None,
    ) -> None:
        self._api = api_client
        self.logs_root = Path(logs_root) if logs_root is not None else resolve_default_logs_root()
        self.state_db_path = Path(state_db_path) if state_db_path is not None else resolve_default_state_db_path()
        self.max_auto_attempts = max(1, max_auto_attempts)
        self.max_cursor_resets_per_cycle = max(1, max_cursor_resets_per_cycle)
        self._write_hook = write_hook
        self._file_locks_guard = threading.Lock()
        self._file_locks: dict[tuple[str, str, str], threading.Lock] = {}
        self._db_init_lock = threading.Lock()
        self._db_initialized = False

    def _connect(self) -> sqlite3.Connection:
        self.state_db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.state_db_path), isolation_level=None, timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        if not self._db_initialized:
            with self._db_init_lock:
                if not self._db_initialized:
                    conn.executescript(ARCHIVE_SCHEMA_SQL)
                    self._db_initialized = True
        return conn

    def _get_file_lock(self, ecs_instance_id: str, session_id: str, source: str) -> threading.Lock:
        key = (ecs_instance_id, session_id, source)
        with self._file_locks_guard:
            lock = self._file_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._file_locks[key] = lock
            return lock

    def get_instance_cursor(self, ecs_instance_id: str) -> str | None:
        """Strictly select cursor for THIS ecs_instance_id only (never global latest)."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT cursor FROM sync_cursors WHERE ecs_instance_id = ?",
                (ecs_instance_id,),
            ).fetchone()
            return str(row["cursor"]) if (row is not None and row["cursor"]) else None
        finally:
            conn.close()

    def _persist_batch_and_advance_cursor(
        self,
        *,
        ecs_instance_id: str,
        items: list[dict[str, Any]],
        next_cursor: str | None,
        retention_gap_detected: bool,
        retention_gap_note: str | None,
    ) -> int:
        now_iso = utc_now_iso()
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            for item in items:
                session_id = str(item["session_id"])
                group_id = str(item["group_id"])
                existing_sess = conn.execute(
                    "SELECT local_status FROM local_sessions WHERE ecs_instance_id = ? AND session_id = ?",
                    (ecs_instance_id, session_id),
                ).fetchone()
                if existing_sess is None:
                    conn.execute(
                        """
                        INSERT INTO local_sessions(
                            ecs_instance_id, session_id, group_id, group_name_snapshot,
                            group_deleted, ended_at, expires_at, close_reason,
                            local_status, show_retry_action, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', 0, ?)
                        """,
                        (
                            ecs_instance_id,
                            session_id,
                            group_id,
                            str(item.get("group_name_snapshot", group_id)),
                            1 if item.get("group_deleted") else 0,
                            str(item.get("ended_at", "")),
                            str(item.get("expires_at", "")),
                            str(item.get("close_reason", "")),
                            now_iso,
                        ),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE local_sessions
                        SET group_deleted = ?, group_name_snapshot = ?, updated_at = ?
                        WHERE ecs_instance_id = ? AND session_id = ?
                        """,
                        (
                            1 if item.get("group_deleted") else 0,
                            str(item.get("group_name_snapshot", group_id)),
                            now_iso,
                            ecs_instance_id,
                            session_id,
                        ),
                    )

                for fdesc in item.get("files") or []:
                    src = str(fdesc.get("source", ""))
                    if src not in FIXED_SOURCE_FILENAMES:
                        continue
                    avail = str(fdesc.get("availability", "missing_on_server"))
                    fixed_name = FIXED_SOURCE_FILENAMES[src]

                    existing_f = conn.execute(
                        "SELECT status FROM local_files WHERE ecs_instance_id = ? AND session_id = ? AND source = ?",
                        (ecs_instance_id, session_id, src),
                    ).fetchone()
                    if existing_f is not None and existing_f["status"] == "verified":
                        continue  # Already verified locally -> never re-queue!

                    # Legal zero-byte `empty` files are valid available files (NOT missing sources)
                    if avail in ("available", "empty", "degraded_quota_exceeded") and fdesc.get("file_id"):
                        init_status = "pending"
                        err_cat = None
                        err_msg = None
                    else:
                        init_status = "missing_on_server"
                        err_cat = "cloud_source_missing"
                        err_msg = str(fdesc.get("missing_reason") or avail or "missing_on_server")

                    conn.execute(
                        """
                        INSERT INTO local_files(
                            ecs_instance_id, session_id, source, file_id, logical_name,
                            server_availability, server_missing_reason, expected_size, expected_sha256,
                            status, error_category, error_message, attempt_count, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                        ON CONFLICT(ecs_instance_id, session_id, source) DO UPDATE SET
                            file_id = COALESCE(excluded.file_id, local_files.file_id),
                            logical_name = excluded.logical_name,
                            server_availability = excluded.server_availability,
                            server_missing_reason = excluded.server_missing_reason,
                            expected_size = excluded.expected_size,
                            expected_sha256 = excluded.expected_sha256,
                            updated_at = excluded.updated_at
                        WHERE local_files.status != 'verified'
                        """,
                        (
                            ecs_instance_id,
                            session_id,
                            src,
                            fdesc.get("file_id"),
                            fixed_name,  # Fixed filename only — never remote path!
                            avail,
                            fdesc.get("missing_reason"),
                            fdesc.get("size_bytes"),
                            fdesc.get("sha256"),
                            init_status,
                            err_cat,
                            err_msg,
                            now_iso,
                        ),
                    )

            # Advance cursor ONLY after all discovered tasks are persisted in the same transaction
            conn.execute(
                """
                INSERT INTO sync_cursors(ecs_instance_id, cursor, last_sync_at, retention_gap_detected, retention_gap_note)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(ecs_instance_id) DO UPDATE SET
                    cursor = excluded.cursor,
                    last_sync_at = excluded.last_sync_at,
                    retention_gap_detected = MAX(sync_cursors.retention_gap_detected, excluded.retention_gap_detected),
                    retention_gap_note = COALESCE(excluded.retention_gap_note, sync_cursors.retention_gap_note)
                """,
                (
                    ecs_instance_id,
                    next_cursor,
                    now_iso,
                    1 if retention_gap_detected else 0,
                    retention_gap_note,
                ),
            )
            conn.execute("COMMIT")
            return len(items)
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def poll_manifest(
        self,
        *,
        ecs_instance_id: str,
        expected_epoch: int,
        cancel_event: threading.Event | None = None,
    ) -> tuple[int, bool, str | None]:
        """Poll `/api/v1/archive/changes` scoped strictly to `ecs_instance_id`."""
        cursor = self.get_instance_cursor(ecs_instance_id)
        discovered = 0
        retention_gap = False
        retention_note: str | None = None
        cursor_resets = 0

        while True:
            if cancel_event and cancel_event.is_set():
                break
            try:
                data = self._api.list_archive_changes(
                    cursor=cursor or "",
                    limit=50,
                    expected_epoch=expected_epoch,
                )
            except ApiError as exc:
                if exc.status_code == 410 and exc.code == "CURSOR_EXPIRED":
                    retention_gap = True
                    retention_note = "客户端离线超过云端 7 天保留期，可能缺失早期未同步切片，已从空游标重新对账。"
                    cursor_resets += 1
                    if cursor_resets > self.max_cursor_resets_per_cycle:
                        # Record gap & stop cycle — prevent infinite loop!
                        self._persist_batch_and_advance_cursor(
                            ecs_instance_id=ecs_instance_id,
                            items=[],
                            next_cursor="",
                            retention_gap_detected=True,
                            retention_gap_note=retention_note,
                        )
                        break
                    cursor = ""
                    continue
                raise

            resp_ecs_id = str(data.get("ecs_instance_id") or "")
            if resp_ecs_id and resp_ecs_id != ecs_instance_id:
                raise SessionInvalidatedError(
                    f"Instance mismatch: expected {ecs_instance_id}, got {resp_ecs_id}"
                )

            items = list(data.get("items") or [])
            next_cursor = data.get("next_cursor")
            discovered += self._persist_batch_and_advance_cursor(
                ecs_instance_id=ecs_instance_id,
                items=items,
                next_cursor=str(next_cursor) if next_cursor is not None else cursor,
                retention_gap_detected=retention_gap,
                retention_gap_note=retention_note,
            )
            cursor = str(next_cursor) if next_cursor is not None else cursor
            if not data.get("has_more"):
                break

        return discovered, retention_gap, retention_note

    @staticmethod
    def _matches_expected_on_disk(path: Path, expected_size: int | None, expected_sha256: str | None) -> bool:
        if not path.exists() or not path.is_file():
            return False
        try:
            got_sha, got_size = sha256_file(path)
        except OSError:
            return False
        if expected_size is not None and got_size != int(expected_size):
            return False
        if expected_sha256 and got_sha.lower() != str(expected_sha256).lower():
            return False
        # Without expected_sha256 or expected_size, cannot prove crash-recovered file integrity safely
        return bool(expected_sha256) or (expected_size is not None)

    def _recompute_session_status(self, conn: sqlite3.Connection, ecs_instance_id: str, session_id: str) -> None:
        files = conn.execute(
            "SELECT * FROM local_files WHERE ecs_instance_id = ? AND session_id = ?",
            (ecs_instance_id, session_id),
        ).fetchall()
        now_iso = utc_now_iso()

        has_pending = any(f["status"] == "pending" for f in files)
        failed_files = [f for f in files if f["status"] == "failed"]
        expired_files = [f for f in files if f["status"] == "expired_on_server"]
        server_gaps = [
            f
            for f in files
            if f["status"] == "missing_on_server"
            or f["server_availability"] in ("missing_on_server", "degraded_quota_exceeded")
        ]

        if failed_files:
            first = failed_files[0]
            local_status = "failed"
            show_retry = 1
            err_cat = first["error_category"]
            err_msg = first["error_message"]
        elif expired_files:
            first = expired_files[0]
            local_status = "expired_on_server"
            show_retry = 0  # NEVER loop retry expired files
            err_cat = "cloud_expired"
            err_msg = first["error_message"] or "云端归档已超过 7 天保留期（HTTP 410 ARCHIVE_EXPIRED）"
        elif has_pending:
            local_status = "pending"
            show_retry = 0
            err_cat = None
            err_msg = None
        elif server_gaps:
            missing_desc = "、".join(
                f"{f['source']}（{f['server_missing_reason'] or f['server_availability']}）" for f in server_gaps
            )
            local_status = "saved_with_source_gaps"
            show_retry = 0  # Cloud source missing/degraded -> NEVER prompt user to retry!
            err_cat = "cloud_source_missing"
            err_msg = f"云端缺少或仅含部分来源：{missing_desc}"
        else:
            local_status = "saved"
            show_retry = 0
            err_cat = None
            err_msg = None

        conn.execute(
            """
            UPDATE local_sessions
            SET local_status = ?, last_error_category = ?, last_error_message = ?,
                show_retry_action = ?, updated_at = ?
            WHERE ecs_instance_id = ? AND session_id = ?
            """,
            (local_status, err_cat, err_msg, show_retry, now_iso, ecs_instance_id, session_id),
        )

    def _record_file_verified(
        self,
        ecs_instance_id: str,
        session_id: str,
        source: str,
        dest_path: Path,
        *,
        increment_attempt: bool,
    ) -> None:
        now_iso = utc_now_iso()
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            inc = "attempt_count + 1" if increment_attempt else "attempt_count"
            conn.execute(
                f"""
                UPDATE local_files
                SET local_path = ?, status = 'verified', error_category = NULL, error_message = NULL,
                    attempt_count = {inc}, updated_at = ?
                WHERE ecs_instance_id = ? AND session_id = ? AND source = ?
                """,
                (str(dest_path), now_iso, ecs_instance_id, session_id, source),
            )
            conn.execute("COMMIT")
        finally:
            conn.close()

    def _record_file_error(
        self,
        ecs_instance_id: str,
        session_id: str,
        source: str,
        *,
        status: str,
        error_category: str,
        error_message: str,
    ) -> None:
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                UPDATE local_files
                SET status = ?, error_category = ?, error_message = ?,
                    attempt_count = attempt_count + 1, updated_at = ?
                WHERE ecs_instance_id = ? AND session_id = ? AND source = ?
                """,
                (status, error_category, error_message, utc_now_iso(), ecs_instance_id, session_id, source),
            )
            conn.execute("COMMIT")
        finally:
            conn.close()

    def _download_and_verify_one(
        self,
        *,
        ecs_instance_id: str,
        group_id: str,
        session_id: str,
        source: str,
        file_id: str,
        expected_size: int | None,
        expected_sha256: str | None,
        expected_epoch: int,
        summary: SyncCycleSummary,
        cancel_event: threading.Event | None,
    ) -> tuple[bool, bool]:
        """Stream file to `.part`, verify length + manifest SHA-256 + `X-Content-SHA256`, then `os.replace()`.

        Returns `(succeeded, stop_trying)`.
        """
        file_lock = self._get_file_lock(ecs_instance_id, session_id, source)
        with file_lock:
            if cancel_event and cancel_event.is_set():
                summary.cancelled = True
                return False, True

            dest_path = safe_archive_file_path(self.logs_root, ecs_instance_id, group_id, session_id, source)

            # Crash-recovery check: if file was already os.replace()'d before SQLite commit, verify on disk & skip download!
            if self._matches_expected_on_disk(dest_path, expected_size, expected_sha256):
                self._record_file_verified(ecs_instance_id, session_id, source, dest_path, increment_attempt=False)
                summary.files_recovered_from_disk += 1
                return True, True

            url = f"/api/v1/archive/sessions/{session_id}/files/{file_id}"
            tmp_path = dest_path.parent / f".{dest_path.name}.part"

            try:
                with self._api.stream_authenticated("GET", url, expected_epoch=expected_epoch) as resp:
                    if resp.status_code == 410:
                        self._record_file_error(
                            ecs_instance_id, session_id, source,
                            status="expired_on_server",
                            error_category="cloud_expired",
                            error_message="云端归档已超过 7 天保留期（HTTP 410 ARCHIVE_EXPIRED），已停止重试。",
                        )
                        summary.files_expired += 1
                        return False, True  # Terminal — never retry expired files!

                    if resp.status_code == 404:
                        resp.read()
                        code = ""
                        try:
                            code = str(resp.json().get("error", {}).get("code", ""))
                        except Exception:
                            pass
                        if code == "ARCHIVE_SOURCE_MISSING":
                            self._record_file_error(
                                ecs_instance_id, session_id, source,
                                status="missing_on_server",
                                error_category="cloud_source_missing",
                                error_message="云端本身缺少该路日志（HTTP 404 ARCHIVE_SOURCE_MISSING）。",
                            )
                            return False, True
                        self._record_file_error(
                            ecs_instance_id, session_id, source,
                            status="failed",
                            error_category="network_error",
                            error_message=f"下载 {source} 返回 404（{code}）。",
                        )
                        summary.files_failed += 1
                        return False, False

                    if resp.status_code != 200:
                        self._record_file_error(
                            ecs_instance_id, session_id, source,
                            status="failed",
                            error_category="network_error",
                            error_message=f"下载 {source} 返回异常状态码 HTTP {resp.status_code}。",
                        )
                        summary.files_failed += 1
                        return False, False

                    header_sha = resp.headers.get("X-Content-SHA256")
                    content_length_hdr = resp.headers.get("Content-Length")
                    expected_hdr_len = int(content_length_hdr) if (content_length_hdr and content_length_hdr.isdigit()) else None

                    # Stream chunks directly to .part file on disk while hashing incrementally
                    hasher = hashlib.sha256()
                    total_bytes = 0
                    try:
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        if self._write_hook is not None:
                            chunks: list[bytes] = []
                            for chunk in resp.iter_bytes(CHUNK_SIZE):
                                if cancel_event and cancel_event.is_set():
                                    summary.cancelled = True
                                    return False, True
                                hasher.update(chunk)
                                total_bytes += len(chunk)
                                chunks.append(chunk)
                            self._write_hook(tmp_path, b"".join(chunks))
                        else:
                            with open(tmp_path, "wb") as fh:
                                for chunk in resp.iter_bytes(CHUNK_SIZE):
                                    if cancel_event and cancel_event.is_set():
                                        summary.cancelled = True
                                        fh.close()
                                        try:
                                            tmp_path.unlink(missing_ok=True)
                                        except OSError:
                                            pass
                                        return False, True
                                    fh.write(chunk)
                                    hasher.update(chunk)
                                    total_bytes += len(chunk)
                                fh.flush()
                                os.fsync(fh.fileno())
                    except OSError as exc:
                        try:
                            tmp_path.unlink(missing_ok=True)
                        except OSError:
                            pass
                        cat, msg = classify_os_error(exc)
                        self._record_file_error(
                            ecs_instance_id, session_id, source,
                            status="failed", error_category=cat, error_message=msg,
                        )
                        summary.files_failed += 1
                        # Disk permission / full errors are terminal for this auto cycle
                        return False, True

                    # Verify session epoch didn't change mid-stream
                    if not self._api.auth.is_epoch_current(expected_epoch):
                        try:
                            tmp_path.unlink(missing_ok=True)
                        except OSError:
                            pass
                        raise SessionInvalidatedError("Session switched during file stream")

                    got_sha = hasher.hexdigest()
                    size_mismatch = (
                        (expected_size is not None and total_bytes != int(expected_size))
                        or (expected_hdr_len is not None and total_bytes != expected_hdr_len)
                    )
                    manifest_sha_mismatch = bool(expected_sha256 and got_sha.lower() != str(expected_sha256).lower())
                    header_sha_mismatch = bool(header_sha and got_sha.lower() != str(header_sha).lower())

                    if size_mismatch or manifest_sha_mismatch or header_sha_mismatch:
                        try:
                            tmp_path.unlink(missing_ok=True)
                        except OSError:
                            pass
                        self._record_file_error(
                            ecs_instance_id, session_id, source,
                            status="failed",
                            error_category="checksum_mismatch",
                            error_message=f"文件 {dest_path.name} 完整性校验失败（长度或 SHA-256 不一致），请重试下载。",
                        )
                        summary.files_failed += 1
                        return False, False

                    # Verify written .part file on disk before atomic rename
                    try:
                        disk_sha, disk_size = sha256_file(tmp_path)
                        if disk_sha != got_sha or disk_size != total_bytes:
                            raise OSError("Written .part file verification failed")
                        os.replace(tmp_path, dest_path)
                    except OSError as exc:
                        try:
                            tmp_path.unlink(missing_ok=True)
                        except OSError:
                            pass
                        cat, msg = classify_os_error(exc)
                        self._record_file_error(
                            ecs_instance_id, session_id, source,
                            status="failed", error_category=cat, error_message=msg,
                        )
                        summary.files_failed += 1
                        return False, True

            except SessionInvalidatedError:
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError:
                    pass
                summary.cancelled = True
                return False, True
            except (NetworkError, httpx.HTTPError) as exc:
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError:
                    pass
                self._record_file_error(
                    ecs_instance_id, session_id, source,
                    status="failed",
                    error_category="network_error",
                    error_message=f"下载 {dest_path.name} 时网络中断：{exc}",
                )
                summary.files_failed += 1
                return False, False
            except ApiError as exc:
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError:
                    pass
                self._record_file_error(
                    ecs_instance_id, session_id, source,
                    status="failed",
                    error_category="network_error",
                    error_message=f"下载 {dest_path.name} 失败：{exc.message}",
                )
                summary.files_failed += 1
                return False, exc.status_code == 401

            # Record verified ONLY after atomic os.replace() succeeded!
            self._record_file_verified(ecs_instance_id, session_id, source, dest_path, increment_attempt=True)
            summary.files_downloaded += 1
            return True, True

    def _sync_single_session(
        self,
        *,
        ecs_instance_id: str,
        session_id: str,
        expected_epoch: int,
        summary: SyncCycleSummary,
        manual_retry: bool,
        cancel_event: threading.Event | None,
    ) -> None:
        conn = self._connect()
        try:
            sess = conn.execute(
                "SELECT * FROM local_sessions WHERE ecs_instance_id = ? AND session_id = ?",
                (ecs_instance_id, session_id),
            ).fetchone()
            if sess is None:
                return
            group_id = str(sess["group_id"])
            files = conn.execute(
                "SELECT * FROM local_files WHERE ecs_instance_id = ? AND session_id = ? ORDER BY source ASC",
                (ecs_instance_id, session_id),
            ).fetchall()
        finally:
            conn.close()

        for frow in files:
            if cancel_event and cancel_event.is_set():
                summary.cancelled = True
                break

            if frow["status"] in ("missing_on_server", "expired_on_server"):
                continue

            # Already verified on disk -> NEVER re-download!
            if frow["status"] == "verified" and frow["local_path"]:
                if self._matches_expected_on_disk(Path(str(frow["local_path"])), frow["expected_size"], frow["expected_sha256"]):
                    summary.files_skipped_verified += 1
                    continue

            if not manual_retry and frow["status"] == "failed" and int(frow["attempt_count"]) >= self.max_auto_attempts:
                continue

            file_id = frow["file_id"]
            if not file_id:
                continue

            max_tries = 1 if manual_retry else max(1, self.max_auto_attempts - int(frow["attempt_count"]))
            for _ in range(max_tries):
                ok, stop = self._download_and_verify_one(
                    ecs_instance_id=ecs_instance_id,
                    group_id=group_id,
                    session_id=session_id,
                    source=str(frow["source"]),
                    file_id=str(file_id),
                    expected_size=frow["expected_size"],
                    expected_sha256=frow["expected_sha256"],
                    expected_epoch=expected_epoch,
                    summary=summary,
                    cancel_event=cancel_event,
                )
                if ok or stop:
                    break

        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            self._recompute_session_status(conn, ecs_instance_id, session_id)
            conn.execute("COMMIT")
        finally:
            conn.close()

    def sync_once(
        self,
        *,
        ecs_instance_id: str,
        expected_epoch: int,
        cancel_event: threading.Event | None = None,
    ) -> SyncCycleSummary:
        """Run one discovery + non-blocking download pass scoped strictly to `ecs_instance_id`."""
        summary = SyncCycleSummary()
        discovered, gap, note = self.poll_manifest(
            ecs_instance_id=ecs_instance_id,
            expected_epoch=expected_epoch,
            cancel_event=cancel_event,
        )
        summary.discovered_sessions = discovered
        summary.retention_gap_detected = gap
        summary.retention_gap_note = note

        if cancel_event and cancel_event.is_set():
            summary.cancelled = True
            return summary

        conn = self._connect()
        try:
            # Strictly select pending/failed sessions ONLY for THIS ecs_instance_id!
            rows = conn.execute(
                """
                SELECT session_id
                FROM local_sessions
                WHERE ecs_instance_id = ? AND local_status IN ('pending', 'downloading', 'failed')
                ORDER BY ended_at ASC
                """,
                (ecs_instance_id,),
            ).fetchall()
        finally:
            conn.close()

        for row in rows:
            if cancel_event and cancel_event.is_set():
                summary.cancelled = True
                break
            self._sync_single_session(
                ecs_instance_id=ecs_instance_id,
                session_id=str(row["session_id"]),
                expected_epoch=expected_epoch,
                summary=summary,
                manual_retry=False,
                cancel_event=cancel_event,
            )
        return summary

    def retry_session(
        self,
        *,
        ecs_instance_id: str,
        session_id: str,
        expected_epoch: int,
        cancel_event: threading.Event | None = None,
    ) -> SyncCycleSummary:
        """Manual retry ('重新下载日志') sharing the exact same task model — downloads ONLY missing files."""
        summary = SyncCycleSummary()
        self._sync_single_session(
            ecs_instance_id=ecs_instance_id,
            session_id=session_id,
            expected_epoch=expected_epoch,
            summary=summary,
            manual_retry=True,
            cancel_event=cancel_event,
        )
        return summary

    def get_instance_snapshot(self, ecs_instance_id: str) -> dict[str, Any]:
        """Return UI-ready local save states scoped strictly to `ecs_instance_id`."""
        conn = self._connect()
        try:
            cursor_row = conn.execute(
                "SELECT * FROM sync_cursors WHERE ecs_instance_id = ?",
                (ecs_instance_id,),
            ).fetchone()
            sessions = conn.execute(
                "SELECT * FROM local_sessions WHERE ecs_instance_id = ? ORDER BY ended_at DESC",
                (ecs_instance_id,),
            ).fetchall()
            session_map: dict[str, dict[str, Any]] = {}
            failed_sessions: list[dict[str, Any]] = []
            saved_count = 0
            for s in sessions:
                sd = dict(s)
                sd["show_retry_action"] = bool(sd["show_retry_action"])
                sd["group_deleted"] = bool(sd["group_deleted"])
                session_map[sd["session_id"]] = sd
                if sd["local_status"] == "failed":
                    failed_sessions.append(sd)
                elif sd["local_status"] in ("saved", "saved_with_source_gaps"):
                    saved_count += 1

            gap_note = ""
            if cursor_row and cursor_row["retention_gap_detected"]:
                gap_note = str(cursor_row["retention_gap_note"] or "检测到云端 7 天留存窗口缺口")

            first_failed = failed_sessions[0] if failed_sessions else None
            return {
                "local_root": str(self.logs_root),
                "session_states": session_map,
                "failed_count": len(failed_sessions),
                "failed_group_id": str(first_failed["group_id"]) if first_failed else "",
                "failed_session_id": str(first_failed["session_id"]) if first_failed else "",
                "failed_message": str(first_failed["last_error_message"] or "") if first_failed else "",
                "saved_count": saved_count,
                "retention_gap_note": gap_note,
            }
        finally:
            conn.close()

    def get_session_state(self, ecs_instance_id: str, session_id: str) -> dict[str, Any] | None:
        conn = self._connect()
        try:
            sess = conn.execute(
                "SELECT * FROM local_sessions WHERE ecs_instance_id = ? AND session_id = ?",
                (ecs_instance_id, session_id),
            ).fetchone()
            if sess is None:
                return None
            files = conn.execute(
                "SELECT * FROM local_files WHERE ecs_instance_id = ? AND session_id = ? ORDER BY source ASC",
                (ecs_instance_id, session_id),
            ).fetchall()
            return {
                **dict(sess),
                "show_retry_action": bool(sess["show_retry_action"]),
                "group_deleted": bool(sess["group_deleted"]),
                "files": [dict(f) for f in files],
            }
        finally:
            conn.close()
