"""P5 contract & architecture invariants: OpenAPI path alignment, forbidden UI calls, and clean worker thread exit."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import httpx
import yaml
from PySide6.QtCore import QCoreApplication

from flightlink_desktop.api.auth import AuthCoordinator
from flightlink_desktop.api.client import FlightLinkApiClient
from flightlink_desktop.api.credentials import CredentialStore
from flightlink_desktop.archive.sync_engine import ArchiveSyncEngine
from flightlink_desktop.archive.worker import ArchiveSyncWorker

ROOT_DIR = Path(__file__).resolve().parents[1]


class _MemSecrets:
    def __init__(self) -> None:
        self._d: dict[tuple[str, str], str] = {}
    def get_password(self, s: str, u: str) -> str | None: return self._d.get((s, u))
    def set_password(self, s: str, u: str, p: str) -> None: self._d[(s, u)] = p
    def delete_password(self, s: str, u: str) -> None: self._d.pop((s, u), None)


def test_openapi_25_operations_accounted_for_and_forbidden_ui_endpoints_absent() -> None:
    spec = yaml.safe_load((ROOT_DIR / "docs" / "api" / "openapi.yaml").read_text(encoding="utf-8"))
    op_ids: set[str] = set()
    for _path, methods in spec["paths"].items():
        for method, meta in methods.items():
            if method in ("get", "post", "patch", "delete", "put") and isinstance(meta, dict):
                op_ids.add(meta["operationId"])
    assert len(op_ids) == 25

    # Verify desktop source code NEVER calls /logs/export or /archive/sessions/{id}/download
    src_root = ROOT_DIR / "src" / "flightlink_desktop"
    for py_or_qml in list(src_root.rglob("*.py")) + list(src_root.rglob("*.qml")):
        content = py_or_qml.read_text(encoding="utf-8")
        assert "/logs/export" not in content, f"Forbidden /logs/export referenced in {py_or_qml}"
        assert "/download" not in content, f"Forbidden /download referenced in {py_or_qml}"
        assert "QtWidgets" not in content, f"Forbidden QtWidgets referenced in {py_or_qml}"
        assert "QtWebEngine" not in content, f"Forbidden QtWebEngine referenced in {py_or_qml}"
        assert "PyQt6" not in content, f"Forbidden PyQt6 referenced in {py_or_qml}"


def test_archive_worker_starts_on_login_and_exits_thread_cleanly(tmp_path: Path) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QCoreApplication.instance() or QCoreApplication([])

    changes_called = threading.Event()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/health":
            return httpx.Response(200, json={"status": "ok", "version": "1.0.0", "ecs_instance_id": "ecs-w", "observed_at": "2026-11-27T08:00:00Z", "db_ok": True})
        if request.url.path == "/api/v1/auth/login":
            return httpx.Response(200, json={
                "access_token": "tok_w", "refresh_token": "ref_w_123456789012", "token_type": "bearer",
                "expires_at": "2026-11-28T00:00:00Z", "refresh_expires_at": "2026-12-05T00:00:00Z",
                "user": {"user_id": "u1", "username": "viewer1", "display_name": "Viewer", "role": "viewer", "created_at": "2026-11-01T00:00:00Z"},
            })
        if request.url.path == "/api/v1/archive/changes":
            changes_called.set()
            return httpx.Response(200, json={"ecs_instance_id": "ecs-w", "retention_seconds": 604800, "items": [], "next_cursor": "c1", "has_more": False, "observed_at": "2026-11-27T08:00:00Z"})
        return httpx.Response(404)

    store = CredentialStore(config_path=tmp_path / "cfg.json", secret_backend=_MemSecrets())
    auth = AuthCoordinator(credential_store=store)
    client = FlightLinkApiClient(auth, transport=httpx.MockTransport(handler))
    engine = ArchiveSyncEngine(client, logs_root=tmp_path / "Logs", state_db_path=tmp_path / "sync.sqlite3")
    worker = ArchiveSyncWorker(engine, poll_interval_seconds=60.0)

    snapshots: list[dict] = []
    worker.snapshotReady.connect(lambda _ep, snap: snapshots.append(snap))

    try:
        client.login("http://127.0.0.1:8000", "viewer1", "Pass!")
        worker.onSessionStarted(auth.current_epoch(), "ecs-w", "http://127.0.0.1:8000")
        assert changes_called.wait(timeout=3.0), "Archive worker did not start polling on login"

        deadline = time.monotonic() + 2.0
        while not snapshots and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        assert len(snapshots) >= 1
    finally:
        worker.shutdown(timeout_s=3.0)
        assert worker._thread is not None and not worker._thread.is_alive()
        client.close()
