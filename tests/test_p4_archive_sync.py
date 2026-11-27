"""P4 comprehensive regression suite for durable local auto-archive engine."""

from __future__ import annotations

import errno
import hashlib
import os
import threading
import time
from pathlib import Path
from typing import Any

import httpx
import pytest

from flightlink_desktop.api.auth import AuthCoordinator
from flightlink_desktop.api.client import FlightLinkApiClient
from flightlink_desktop.api.credentials import CredentialStore
from flightlink_desktop.archive.paths import resolve_default_logs_root, safe_archive_file_path
from flightlink_desktop.archive.sync_engine import ArchiveSyncEngine
from flightlink_desktop.archive.worker import ArchiveSyncWorker


class _MemSecrets:
    def __init__(self) -> None:
        self._d: dict[tuple[str, str], str] = {}
    def get_password(self, s: str, u: str) -> str | None: return self._d.get((s, u))
    def set_password(self, s: str, u: str, p: str) -> None: self._d[(s, u)] = p
    def delete_password(self, s: str, u: str) -> None: self._d.pop((s, u), None)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _make_change_item(
    *,
    ecs_id: str,
    group_id: str,
    session_id: str,
    group_name: str = "一号机",
    group_deleted: bool = False,
    files: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "change_seq": 1,
        "ecs_instance_id": ecs_id,
        "group_id": group_id,
        "group_name_snapshot": group_name,
        "dtu_port_snapshot": 5760,
        "gcs_protocol_snapshot": "tcp",
        "gcs_port_snapshot": 14552,
        "group_deleted": group_deleted,
        "session_id": session_id,
        "sysid": 1,
        "first_observed_at": "2026-11-27T07:00:00Z",
        "last_heartbeat_at": "2026-11-27T07:10:00Z",
        "ended_at": "2026-11-27T07:11:00Z",
        "sealed_at": "2026-11-27T07:11:05Z",
        "expires_at": "2026-12-04T07:11:05Z",
        "close_reason": "fc_heartbeat_timeout",
        "files": files,
        "gaps": [],
    }


def _file_desc(
    source: str,
    file_id: str | None,
    content: bytes | None,
    *,
    availability: str = "available",
    logical_name: str | None = None,
    missing_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "source": source,
        "availability": availability,
        "file_id": file_id,
        "logical_name": logical_name or f"{source}.log",
        "content_type": "application/json" if source == "metadata" else "text/plain",
        "size_bytes": len(content) if content is not None else None,
        "sha256": _sha(content) if content is not None else None,
        "missing_reason": missing_reason,
    }


def _auth_routes(path: str, ecs_id: str, token: str = "tok_1") -> httpx.Response | None:
    if path == "/api/v1/health":
        return httpx.Response(200, json={"status": "ok", "version": "1.0.0", "ecs_instance_id": ecs_id, "observed_at": "2026-11-27T08:00:00Z", "db_ok": True})
    if path == "/api/v1/auth/login":
        return httpx.Response(200, json={
            "access_token": token, "refresh_token": f"ref_{token}_1234567890", "token_type": "bearer",
            "expires_at": "2026-11-28T00:00:00Z", "refresh_expires_at": "2026-12-05T00:00:00Z",
            "user": {"user_id": "u1", "username": "viewer1", "display_name": "Viewer", "role": "viewer", "created_at": "2026-11-01T00:00:00Z"},
        })
    return None


def test_windows_known_folder_and_path_traversal_containment(tmp_path: Path) -> None:
    default_root = resolve_default_logs_root()
    assert default_root.parts[-2:] == ("FlightLink", "Logs")

    # Malicious opaque IDs containing path traversal MUST remain strictly inside logs_root
    p = safe_archive_file_path(tmp_path, "../../ecs:bad", "../grp/1", "..\\sess\\9", "router")
    assert p.resolve().is_relative_to(tmp_path.resolve())
    assert p.name == "router.log"
    assert safe_archive_file_path(tmp_path, "ecs-1", "grp-1", "sess-1", "mavproxy").name == "mavproxy.log"
    assert safe_archive_file_path(tmp_path, "ecs-1", "grp-1", "sess-1", "metadata").name == "metadata.json"


def test_two_ecs_instances_with_duplicate_session_id_never_cross_contaminate(tmp_path: Path) -> None:
    logs_root = tmp_path / "Logs"
    db_path = tmp_path / "app" / "archive_sync.sqlite3"
    seen_cursors: dict[str, list[str | None]] = {"ecs-A": [], "ecs-B": []}

    content_a = b"instance A router log\n"
    content_b = b"instance B router log (DIFFERENT)\n"
    meta_a = b'{"instance":"A"}'
    meta_b = b'{"instance":"B"}'

    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        ecs_id = "ecs-A" if host == "ecs-a.internal" else "ecs-B"
        base = _auth_routes(request.url.path, ecs_id, token=f"tok_{ecs_id}")
        if base is not None:
            return base
        if request.url.path == "/api/v1/archive/changes":
            seen_cursors[ecs_id].append(request.url.params.get("cursor"))
            r_bytes, m_bytes = (content_a, meta_a) if ecs_id == "ecs-A" else (content_b, meta_b)
            # Notice remote logical_name tries traversal — client MUST ignore and use fixed filenames!
            item = _make_change_item(
                ecs_id=ecs_id,
                group_id="grp_same",
                session_id="sess_dup_001",
                files=[
                    _file_desc("router", f"f_r_{ecs_id}", r_bytes, logical_name="../../../evil.txt"),
                    _file_desc("mavproxy", f"f_m_{ecs_id}", b"", availability="empty"),  # Legal 0-byte empty file!
                    _file_desc("metadata", f"f_j_{ecs_id}", m_bytes, logical_name="bad/meta.json"),
                ],
            )
            return httpx.Response(200, json={"ecs_instance_id": ecs_id, "retention_seconds": 604800, "items": [item], "next_cursor": f"cur_{ecs_id}_1", "has_more": False, "observed_at": "2026-11-27T08:00:00Z"})
        if request.url.path == "/api/v1/archive/sessions/sess_dup_001/files/f_r_ecs-A":
            return httpx.Response(200, content=content_a, headers={"X-Content-SHA256": _sha(content_a)})
        if request.url.path == "/api/v1/archive/sessions/sess_dup_001/files/f_m_ecs-A":
            return httpx.Response(200, content=b"", headers={"X-Content-SHA256": _sha(b"")})
        if request.url.path == "/api/v1/archive/sessions/sess_dup_001/files/f_j_ecs-A":
            return httpx.Response(200, content=meta_a, headers={"X-Content-SHA256": _sha(meta_a)})
        if request.url.path == "/api/v1/archive/sessions/sess_dup_001/files/f_r_ecs-B":
            return httpx.Response(200, content=content_b, headers={"X-Content-SHA256": _sha(content_b)})
        if request.url.path == "/api/v1/archive/sessions/sess_dup_001/files/f_m_ecs-B":
            return httpx.Response(200, content=b"", headers={"X-Content-SHA256": _sha(b"")})
        if request.url.path == "/api/v1/archive/sessions/sess_dup_001/files/f_j_ecs-B":
            return httpx.Response(200, content=meta_b, headers={"X-Content-SHA256": _sha(meta_b)})
        return httpx.Response(404)

    store = CredentialStore(config_path=tmp_path / "cfg.json", secret_backend=_MemSecrets())
    auth = AuthCoordinator(credential_store=store)
    client = FlightLinkApiClient(auth, transport=httpx.MockTransport(handler))
    engine = ArchiveSyncEngine(client, logs_root=logs_root, state_db_path=db_path)

    try:
        # Sync Instance A (as viewer! viewer CAN sync local archive)
        client.login("https://ecs-a.internal", "viewer1", "PassA!")
        res_a = engine.sync_once(ecs_instance_id="ecs-A", expected_epoch=auth.current_epoch())
        assert res_a.files_downloaded == 3
        assert seen_cursors["ecs-A"] == [None]

        # Switch to Instance B with duplicate session_id -> MUST start with cursor=None (NOT cur_ecs-A_1!)
        auth.switch_server("https://ecs-b.internal")
        client.login("https://ecs-b.internal", "viewer1", "PassB!")
        res_b = engine.sync_once(ecs_instance_id="ecs-B", expected_epoch=auth.current_epoch())
        assert res_b.files_downloaded == 3
        assert seen_cursors["ecs-B"] == [None]

        # Both saved cleanly under isolated instance directories with fixed filenames & 0-byte empty file treated as `saved`!
        path_a = logs_root / "ecs-A" / "grp_same" / "sess_dup_001"
        path_b = logs_root / "ecs-B" / "grp_same" / "sess_dup_001"
        assert (path_a / "router.log").read_bytes() == content_a
        assert (path_a / "mavproxy.log").read_bytes() == b""
        assert (path_a / "metadata.json").read_bytes() == meta_a
        assert (path_b / "router.log").read_bytes() == content_b
        assert (path_b / "metadata.json").read_bytes() == meta_b

        st_a = engine.get_session_state("ecs-A", "sess_dup_001")
        st_b = engine.get_session_state("ecs-B", "sess_dup_001")
        assert st_a is not None and st_a["local_status"] == "saved" and st_a["show_retry_action"] is False
        assert st_b is not None and st_b["local_status"] == "saved" and st_b["show_retry_action"] is False
    finally:
        client.close()


def test_acceptance_interrupted_second_file_restart_recovery_and_crash_before_commit(tmp_path: Path) -> None:
    """End-to-end acceptance case: interrupt on 2nd file -> reopen -> 1st file NOT re-downloaded, missing files completed, saved has no download button."""
    logs_root = tmp_path / "Logs"
    db_path = tmp_path / "app" / "archive_sync.sqlite3"
    dl_counts: dict[str, int] = {"f_mav": 0, "f_meta": 0, "f_rtr": 0}
    fail_meta = True

    b_mav = b"mavproxy session lines\n"
    b_meta = b'{"session":"sess_acc"}'
    b_rtr = b"router systemd lines\n"

    def handler(request: httpx.Request) -> httpx.Response:
        base = _auth_routes(request.url.path, "ecs-1")
        if base is not None:
            return base
        if request.url.path == "/api/v1/archive/changes":
            if request.url.params.get("cursor") == "cur_1":
                return httpx.Response(200, json={"ecs_instance_id": "ecs-1", "retention_seconds": 604800, "items": [], "next_cursor": "cur_1", "has_more": False, "observed_at": "2026-11-27T08:00:00Z"})
            item = _make_change_item(
                ecs_id="ecs-1",
                group_id="grp_old_1",
                session_id="sess_acc",
                group_name="一号机",
                files=[
                    _file_desc("mavproxy", "f_mav", b_mav),
                    _file_desc("metadata", "f_meta", b_meta),
                    _file_desc("router", "f_rtr", b_rtr),
                ],
            )
            return httpx.Response(200, json={"ecs_instance_id": "ecs-1", "retention_seconds": 604800, "items": [item], "next_cursor": "cur_1", "has_more": False, "observed_at": "2026-11-27T08:00:00Z"})
        if request.url.path.endswith("/f_mav"):
            dl_counts["f_mav"] += 1
            return httpx.Response(200, content=b_mav, headers={"X-Content-SHA256": _sha(b_mav)})
        if request.url.path.endswith("/f_meta"):
            dl_counts["f_meta"] += 1
            if fail_meta:
                raise httpx.ReadError("Network dropped during 2nd file")
            return httpx.Response(200, content=b_meta, headers={"X-Content-SHA256": _sha(b_meta)})
        if request.url.path.endswith("/f_rtr"):
            dl_counts["f_rtr"] += 1
            return httpx.Response(200, content=b_rtr, headers={"X-Content-SHA256": _sha(b_rtr)})
        return httpx.Response(404)

    store = CredentialStore(config_path=tmp_path / "cfg.json", secret_backend=_MemSecrets())
    auth = AuthCoordinator(credential_store=store)
    client = FlightLinkApiClient(auth, transport=httpx.MockTransport(handler))
    engine1 = ArchiveSyncEngine(client, logs_root=logs_root, state_db_path=db_path, max_auto_attempts=1)

    try:
        client.login("http://127.0.0.1:8000", "viewer1", "Pass!")
        ep = auth.current_epoch()
        res1 = engine1.sync_once(ecs_instance_id="ecs-1", expected_epoch=ep)
        assert res1.files_failed == 1
        assert dl_counts["f_mav"] == 1
        st1 = engine1.get_session_state("ecs-1", "sess_acc")
        assert st1 is not None and st1["local_status"] == "failed" and st1["show_retry_action"] is True

        # Also simulate crash where router.log was already renamed on disk before SQLite commit!
        rtr_path = logs_root / "ecs-1" / "grp_old_1" / "sess_acc" / "router.log"
        assert rtr_path.exists()
        conn = engine1._connect()
        conn.execute("UPDATE local_files SET status = 'pending', local_path = NULL WHERE source = 'router'")
        conn.close()

        # Reopen client (fresh ArchiveSyncEngine) after network recovers
        fail_meta = False
        engine2 = ArchiveSyncEngine(client, logs_root=logs_root, state_db_path=db_path, max_auto_attempts=1)
        res2 = engine2.retry_session(ecs_instance_id="ecs-1", session_id="sess_acc", expected_epoch=ep)
        assert res2.files_failed == 0
        assert res2.files_recovered_from_disk == 1  # router.log verified on disk without re-downloading!
        assert dl_counts["f_mav"] == 1  # 1st file NOT re-downloaded!
        assert dl_counts["f_rtr"] == 1  # crash-recovered file NOT re-downloaded!
        assert dl_counts["f_meta"] == 2  # only missing 2nd file downloaded!

        st2 = engine2.get_session_state("ecs-1", "sess_acc")
        assert st2 is not None
        assert st2["local_status"] == "saved"
        assert st2["show_retry_action"] is False  # No download button after success!
    finally:
        client.close()


def test_source_gaps_disk_failures_checksum_mismatch_410_and_cursor_reset_cap(tmp_path: Path) -> None:
    logs_root = tmp_path / "Logs"
    db_path = tmp_path / "app" / "archive_sync.sqlite3"
    b_rtr = b"router ok\n"
    b_partial = b"partial mavproxy due to quota\n"
    b_meta = b'{"ok":true}'

    expired_hits = 0
    cursor_expired_hits = 0
    bad_checksum_mode = True

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal expired_hits, cursor_expired_hits
        base = _auth_routes(request.url.path, "ecs-edge")
        if base is not None:
            return base
        if request.url.path == "/api/v1/archive/changes":
            if request.url.params.get("cursor") == "cur_stale_7d":
                cursor_expired_hits += 1
                return httpx.Response(410, json={"error": {"code": "CURSOR_EXPIRED", "message": "cursor too old", "retryable": False, "request_id": "r_cur"}})
            if request.url.params.get("cursor") == "cur_done":
                return httpx.Response(200, json={"ecs_instance_id": "ecs-edge", "retention_seconds": 604800, "items": [], "next_cursor": "cur_done", "has_more": False, "observed_at": "2026-11-27T08:00:00Z"})
            items = [
                # 1. Cloud missing_on_server + degraded_quota_exceeded partial file -> saved_with_source_gaps (NO retry prompt)
                _make_change_item(
                    ecs_id="ecs-edge", group_id="grp_1", session_id="sess_gap",
                    files=[
                        _file_desc("router", None, None, availability="missing_on_server", missing_reason="journald_unavailable"),
                        _file_desc("mavproxy", "f_partial", b_partial, availability="degraded_quota_exceeded", missing_reason="disk_quota"),
                        _file_desc("metadata", "f_meta_gap", b_meta),
                    ],
                ),
                # 2. HTTP 200 checksum mismatch -> NEVER marked saved!
                _make_change_item(
                    ecs_id="ecs-edge", group_id="grp_1", session_id="sess_badsha",
                    files=[_file_desc("router", "f_badsha", b_rtr)],
                ),
                # 3. 410 ARCHIVE_EXPIRED on file 2 -> stops retrying & preserves already-saved file 1
                _make_change_item(
                    ecs_id="ecs-edge", group_id="grp_1", session_id="sess_exp",
                    files=[
                        _file_desc("router", "f_exp_ok", b_rtr),
                        _file_desc("mavproxy", "f_exp_410", b_partial),
                    ],
                ),
            ]
            return httpx.Response(200, json={"ecs_instance_id": "ecs-edge", "retention_seconds": 604800, "items": items, "next_cursor": "cur_done", "has_more": False, "observed_at": "2026-11-27T08:00:00Z"})
        if request.url.path.endswith("/f_partial"):
            return httpx.Response(200, content=b_partial, headers={"X-Content-SHA256": _sha(b_partial)})
        if request.url.path.endswith("/f_meta_gap"):
            return httpx.Response(200, content=b_meta, headers={"X-Content-SHA256": _sha(b_meta)})
        if request.url.path.endswith("/f_badsha"):
            body = b"CORRUPTED!" if bad_checksum_mode else b_rtr
            return httpx.Response(200, content=body, headers={"X-Content-SHA256": _sha(b_rtr)})
        if request.url.path.endswith("/f_exp_ok"):
            return httpx.Response(200, content=b_rtr, headers={"X-Content-SHA256": _sha(b_rtr)})
        if request.url.path.endswith("/f_exp_410"):
            expired_hits += 1
            return httpx.Response(410, json={"error": {"code": "ARCHIVE_EXPIRED", "message": "expired", "retryable": False, "request_id": "r410"}})
        return httpx.Response(404)

    store = CredentialStore(config_path=tmp_path / "cfg.json", secret_backend=_MemSecrets())
    auth = AuthCoordinator(credential_store=store)
    client = FlightLinkApiClient(auth, transport=httpx.MockTransport(handler))
    engine = ArchiveSyncEngine(client, logs_root=logs_root, state_db_path=db_path, max_auto_attempts=1)

    try:
        client.login("http://127.0.0.1:8000", "viewer1", "Pass!")
        ep = auth.current_epoch()

        # Seed expired cursor to test 410 CURSOR_EXPIRED gap + empty-cursor reconciliation
        conn = engine._connect()
        conn.execute("INSERT INTO sync_cursors(ecs_instance_id, cursor, last_sync_at) VALUES ('ecs-edge', 'cur_stale_7d', '2026-11-01T00:00:00Z')")
        conn.close()

        res = engine.sync_once(ecs_instance_id="ecs-edge", expected_epoch=ep)
        assert cursor_expired_hits == 1
        assert res.retention_gap_detected is True

        # Check 1: saved_with_source_gaps (partial file saved, missing_on_server noted, NO retry button!)
        st_gap = engine.get_session_state("ecs-edge", "sess_gap")
        assert st_gap is not None
        assert st_gap["local_status"] == "saved_with_source_gaps"
        assert st_gap["show_retry_action"] is False
        assert (logs_root / "ecs-edge" / "grp_1" / "sess_gap" / "mavproxy.log").read_bytes() == b_partial

        # Check 2: HTTP 200 checksum mismatch is NEVER marked saved!
        st_bad = engine.get_session_state("ecs-edge", "sess_badsha")
        assert st_bad is not None
        assert st_bad["local_status"] == "failed"
        assert st_bad["last_error_category"] == "checksum_mismatch"
        assert st_bad["show_retry_action"] is True
        assert not (logs_root / "ecs-edge" / "grp_1" / "sess_badsha" / "router.log").exists()

        # Check 3: 410 ARCHIVE_EXPIRED stops retrying & keeps local file 1 intact!
        st_exp = engine.get_session_state("ecs-edge", "sess_exp")
        assert st_exp is not None
        assert st_exp["local_status"] == "expired_on_server"
        assert st_exp["show_retry_action"] is False
        assert (logs_root / "ecs-edge" / "grp_1" / "sess_exp" / "router.log").read_bytes() == b_rtr
        assert expired_hits == 1
        engine.sync_once(ecs_instance_id="ecs-edge", expected_epoch=ep)
        assert expired_hits == 1  # NEVER looped!

        # Check 4: Disk PermissionError & ENOSPC classification via write_hook
        bad_checksum_mode = False
        def raise_perm(_p: Path, _b: bytes) -> None:
            raise PermissionError(errno.EACCES, "Access denied")
        engine_perm = ArchiveSyncEngine(client, logs_root=logs_root, state_db_path=db_path, write_hook=raise_perm)
        engine_perm.retry_session(ecs_instance_id="ecs-edge", session_id="sess_badsha", expected_epoch=ep)
        st_perm = engine_perm.get_session_state("ecs-edge", "sess_badsha")
        assert st_perm is not None and st_perm["last_error_category"] == "disk_permission_denied"

        def raise_enospc(_p: Path, _b: bytes) -> None:
            raise OSError(errno.ENOSPC, "No space left on device")
        engine_full = ArchiveSyncEngine(client, logs_root=logs_root, state_db_path=db_path, write_hook=raise_enospc)
        engine_full.retry_session(ecs_instance_id="ecs-edge", session_id="sess_badsha", expected_epoch=ep)
        st_full = engine_full.get_session_state("ecs-edge", "sess_badsha")
        assert st_full is not None and st_full["last_error_category"] == "disk_full"
    finally:
        client.close()


def test_archive_stream_and_ui_concurrent_401_single_flight_refresh(tmp_path: Path) -> None:
    logs_root = tmp_path / "Logs"
    db_path = tmp_path / "app" / "archive_sync.sqlite3"
    b_rtr = b"streamed after single-flight refresh\n"
    lock = threading.Lock()
    refresh_calls = 0
    barrier = threading.Barrier(2)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal refresh_calls
        p = request.url.path
        auth_h = request.headers.get("Authorization", "")
        if p == "/api/v1/health":
            return httpx.Response(200, json={"status": "ok", "version": "1.0.0", "ecs_instance_id": "ecs-sf", "observed_at": "2026-11-27T08:00:00Z", "db_ok": True})
        if p == "/api/v1/auth/login":
            return httpx.Response(200, json={
                "access_token": "tok_exp", "refresh_token": "ref_sf_123456789012", "token_type": "bearer",
                "expires_at": "2026-11-28T00:00:00Z", "refresh_expires_at": "2026-12-05T00:00:00Z",
                "user": {"user_id": "u1", "username": "viewer1", "display_name": "Viewer", "role": "viewer", "created_at": "2026-11-01T00:00:00Z"},
            })
        if p == "/api/v1/auth/refresh":
            time.sleep(0.05)
            with lock:
                refresh_calls += 1
            return httpx.Response(200, json={
                "access_token": "tok_new", "refresh_token": "ref_sf_new_123456789", "token_type": "bearer",
                "expires_at": "2026-11-28T00:00:00Z", "refresh_expires_at": "2026-12-05T00:00:00Z",
                "user": {"user_id": "u1", "username": "viewer1", "display_name": "Viewer", "role": "viewer", "created_at": "2026-11-01T00:00:00Z"},
            })
        if p == "/api/v1/archive/changes":
            item = _make_change_item(ecs_id="ecs-sf", group_id="grp_1", session_id="sess_sf", files=[_file_desc("router", "f_sf", b_rtr)])
            return httpx.Response(200, json={"ecs_instance_id": "ecs-sf", "retention_seconds": 604800, "items": [item], "next_cursor": "c1", "has_more": False, "observed_at": "2026-11-27T08:00:00Z"})
        if p == "/api/v1/archive/sessions/sess_sf/files/f_sf":
            if auth_h == "Bearer tok_exp":
                barrier.wait(timeout=3.0)
                return httpx.Response(401, json={"error": {"code": "TOKEN_EXPIRED", "message": "expired", "retryable": False, "request_id": "r1"}})
            assert auth_h == "Bearer tok_new"
            return httpx.Response(200, content=b_rtr, headers={"X-Content-SHA256": _sha(b_rtr)})
        if p == "/api/v1/groups/grp_1":
            if auth_h == "Bearer tok_exp":
                barrier.wait(timeout=3.0)
                return httpx.Response(401, json={"error": {"code": "TOKEN_EXPIRED", "message": "expired", "retryable": False, "request_id": "r2"}})
            assert auth_h == "Bearer tok_new"
            return httpx.Response(200, json={"group_id": "grp_1"})
        return httpx.Response(404)

    store = CredentialStore(config_path=tmp_path / "cfg.json", secret_backend=_MemSecrets())
    auth = AuthCoordinator(credential_store=store)
    client = FlightLinkApiClient(auth, transport=httpx.MockTransport(handler))
    engine = ArchiveSyncEngine(client, logs_root=logs_root, state_db_path=db_path)

    try:
        client.login("http://127.0.0.1:8000", "viewer1", "Pass!")
        ep = auth.current_epoch()
        # First discover manifest so both threads collide right on file stream vs group detail!
        engine.poll_manifest(ecs_instance_id="ecs-sf", expected_epoch=ep)

        errs: list[Exception] = []
        def run_archive() -> None:
            try:
                engine.retry_session(ecs_instance_id="ecs-sf", session_id="sess_sf", expected_epoch=ep)
            except Exception as exc:
                errs.append(exc)

        def run_detail() -> None:
            try:
                client.get_group("grp_1", expected_epoch=ep)
            except Exception as exc:
                errs.append(exc)

        t1 = threading.Thread(target=run_archive)
        t2 = threading.Thread(target=run_detail)
        t1.start(); t2.start()
        t1.join(timeout=5.0); t2.join(timeout=5.0)

        assert not errs
        assert refresh_calls == 1
        assert (logs_root / "ecs-sf" / "grp_1" / "sess_sf" / "router.log").read_bytes() == b_rtr
    finally:
        client.close()
