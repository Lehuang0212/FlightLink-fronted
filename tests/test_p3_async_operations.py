"""P3 tests: double-click guard, lost-response Idempotency-Key reuse, 412 draft preservation, dry-run vs 202, needs_verification retry, network recovery, page switch."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import httpx
from PySide6.QtCore import QCoreApplication

from flightlink_desktop.api.auth import AuthCoordinator
from flightlink_desktop.api.client import FlightLinkApiClient
from flightlink_desktop.api.credentials import CredentialStore
from flightlink_desktop.models.operations_vm import OperationsViewModel
from flightlink_desktop.models.workspace_vm import WorkspaceViewModel
from flightlink_desktop.workers.operation_tracker import IntentKeyManager, TrackedOperation
from flightlink_desktop.workers.task_runner import BackgroundTaskRunner


class _MemSecrets:
    def __init__(self) -> None:
        self._d: dict[tuple[str, str], str] = {}
    def get_password(self, s: str, u: str) -> str | None: return self._d.get((s, u))
    def set_password(self, s: str, u: str, p: str) -> None: self._d[(s, u)] = p
    def delete_password(self, s: str, u: str) -> None: self._d.pop((s, u), None)


def _pump(app: QCoreApplication, predicate, timeout_s: float = 4.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Timed out waiting for async Qt condition")


def _base_auth_responses(path: str, role: str = "admin") -> httpx.Response | None:
    if path == "/api/v1/health":
        return httpx.Response(200, json={"status": "ok", "version": "1.0.0", "ecs_instance_id": "ecs-1", "observed_at": "2026-11-27T08:00:00Z", "db_ok": True})
    if path == "/api/v1/auth/login":
        return httpx.Response(200, json={
            "access_token": "tok_p3", "refresh_token": "ref_p3_123456789012", "token_type": "bearer",
            "expires_at": "2026-11-28T00:00:00Z", "refresh_expires_at": "2026-12-05T00:00:00Z",
            "user": {"user_id": "u1", "username": "ops", "display_name": "Ops", "role": role, "created_at": "2026-11-01T00:00:00Z"},
        })
    if path == "/api/v1/overview":
        return httpx.Response(200, json={
            "ecs_instance_id": "ecs-1", "observed_at": "2026-11-27T08:00:00Z", "stale": False, "stale_after_seconds": 30,
            "components": [], "metrics": {"group_count": 1, "max_groups": 5, "running_router_count": 0, "online_fc_count": 0, "needs_verification_count": 0},
            "disk": {"archive_dir": "/var/lib/flightlink/archive", "status": "ok", "observed_at": "2026-11-27T08:00:00Z"},
            "groups": [],
        })
    if path == "/api/v1/groups":
        return None
    if path == "/api/v1/logs":
        return httpx.Response(200, json={"items": [], "next_cursor": None, "has_more": False, "observed_at": "2026-11-27T08:00:00Z"})
    return None


def test_intent_key_manager_and_operation_polling_cadence() -> None:
    counter = 0
    def next_key() -> str:
        nonlocal counter
        counter += 1
        return f"00000000-0000-4000-8000-{counter:012d}"

    mgr = IntentKeyManager(key_factory=next_key)
    payload_a = {"name": "一号机", "dtu_port": 5760, "gcs_protocol": "tcp", "gcs_port": 14552}
    k1 = mgr.key_for("create_group", payload_a)
    # Same intent + same payload reuses key
    assert mgr.key_for("create_group", payload_a) == k1
    # Modifying any field rotates key
    payload_b = {**payload_a, "gcs_port": 14553}
    k2 = mgr.key_for("create_group", payload_b)
    assert k2 != k1

    # Polling cadence: 500ms during first 5s, 1500ms after 5s
    op = TrackedOperation.from_api(
        {"operation_id": "op_1", "group_id": "grp_1", "action": "create", "status": "pending", "retryable": False, "steps": []},
        epoch=1,
        now_monotonic=100.0,
    )
    assert op.next_poll_interval_ms(100.0) == 500
    assert op.next_poll_interval_ms(104.9) == 500
    assert op.next_poll_interval_ms(105.0) == 1500
    assert op.next_poll_interval_ms(120.0) == 1500


def test_double_click_and_lost_response_reuse_same_idempotency_key_and_page_switch(tmp_path: Path) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QCoreApplication.instance() or QCoreApplication([])

    post_keys: list[str] = []
    op_polls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal op_polls
        base = _base_auth_responses(request.url.path)
        if base is not None:
            return base
        if request.url.path == "/api/v1/groups" and request.method == "GET":
            return httpx.Response(200, json={"items": [], "total": 0, "max_groups": 5, "observed_at": "2026-11-27T08:00:00Z"})
        if request.url.path == "/api/v1/groups" and request.method == "POST":
            key = request.headers.get("Idempotency-Key", "")
            post_keys.append(key)
            if len(post_keys) == 1:
                raise httpx.ReadTimeout("Simulated lost response after server accepted")
            return httpx.Response(
                202,
                json={
                    "operation": {
                        "operation_id": "op_create_1",
                        "group_id": "grp_new_1",
                        "action": "create",
                        "status": "pending",
                        "generation": 1,
                        "retryable": False,
                        "steps": [{"step_name": "reserve_ports", "status": "succeeded"}],
                        "created_at": "2026-11-27T08:00:00Z",
                        "updated_at": "2026-11-27T08:00:00Z",
                    }
                },
            )
        if request.url.path == "/api/v1/operations/op_create_1":
            op_polls += 1
            if op_polls == 1:
                # Simulate transient network outage during operation poll -> must NOT recreate write!
                raise httpx.ConnectError("Transient outage")
            return httpx.Response(
                200,
                json={
                    "operation_id": "op_create_1",
                    "group_id": "grp_new_1",
                    "action": "create",
                    "status": "succeeded",
                    "generation": 1,
                    "retryable": False,
                    "steps": [{"step_name": "reserve_ports", "status": "succeeded"}],
                    "created_at": "2026-11-27T08:00:00Z",
                    "updated_at": "2026-11-27T08:00:02Z",
                },
            )
        return httpx.Response(404)

    store = CredentialStore(config_path=tmp_path / "cfg.json", secret_backend=_MemSecrets())
    auth = AuthCoordinator(credential_store=store)
    client = FlightLinkApiClient(auth, transport=httpx.MockTransport(handler))
    runner = BackgroundTaskRunner()
    ws = WorkspaceViewModel(client, auth, runner, overview_interval_ms=60000, detail_interval_ms=60000)
    ops = OperationsViewModel(client, auth, runner, ws)

    try:
        client.login("http://127.0.0.1:8000", "ops", "Pass123!")
        ep = auth.current_epoch()
        ws.onSessionStarted(ep, "ecs-1", "http://127.0.0.1:8000")
        ops.onSessionStarted(ep, "ecs-1", "http://127.0.0.1:8000")

        ops.openCreateDialog()
        ops.updateDraft("一号机", "5760", "tcp", "14552")

        # Double-click: second call immediately ignored while submitting
        ops.submitDialog()
        ops.submitDialog()
        _pump(app, lambda: not ops.submitting and bool(ops.formError))
        assert len(post_keys) == 1

        # User retries after lost response -> reuses EXACT SAME Idempotency-Key!
        ops.submitDialog()
        _pump(app, lambda: ops.activeOperationId == "op_create_1")
        assert len(post_keys) == 2
        assert post_keys[0] == post_keys[1]
        assert "尚未生效" in ops.activeSummaryText

        # Pause UI live updates AND switch pages -> operation tracking MUST continue uninterrupted!
        ws.toggleLiveUpdates()
        assert ws.liveUpdatesEnabled is False
        ws.navigate("logs")
        ws.navigate("groups")

        # Wait for outage recovery poll -> succeeded, with ZERO duplicate POST /groups!
        _pump(app, lambda: ops.activeStatus == "succeeded", timeout_s=5.0)
        assert op_polls >= 2
        assert len(post_keys) == 2
    finally:
        ops.stop_tracking()
        ws.stop_polling()
        runner.shutdown()
        client.close()


def test_dry_run_200_and_412_preserves_draft_and_reloads_etag(tmp_path: Path) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QCoreApplication.instance() or QCoreApplication([])

    get_count = 0
    seen_if_matches: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal get_count
        base = _base_auth_responses(request.url.path)
        if base is not None:
            return base
        if request.url.path == "/api/v1/groups/grp_1" and request.method == "GET":
            get_count += 1
            ver = 1 if get_count == 1 else 2
            return httpx.Response(
                200,
                headers={"ETag": f'"v{ver}"'},
                json={
                    "group_id": "grp_1", "name": "一号机", "dtu_protocol": "udp", "dtu_port": 5760,
                    "gcs_protocol": "tcp", "gcs_port": 14552, "config_version": ver,
                    "desired_state": "running", "lifecycle_state": "running", "operation_generation": 1,
                    "fc_state": "offline", "gcs_state": "disconnected",
                    "router": {"state": "running", "verified_listening": True, "observed_at": "2026-11-27T08:00:00Z", "stale": False},
                    "mavproxy": {"state": "waiting", "observed_at": "2026-11-27T08:00:00Z", "stale": False},
                    "security_group": {"state": "synced", "owned_rule_count": 2, "observed_at": "2026-11-27T08:00:00Z", "stale": False},
                    "observed_at": "2026-11-27T08:00:00Z", "stale": False,
                },
            )
        if request.url.path == "/api/v1/groups/grp_1" and request.method == "PATCH":
            if request.url.params.get("dry_run") == "true":
                return httpx.Response(
                    200,
                    json={
                        "group_id": "grp_1", "valid": True, "requires_restart": True, "requires_sg_sync": True,
                        "planned_steps": ["prepare_candidate", "sync_sg", "switch_router"], "diff": {"gcs_port": [14552, 14554]},
                    },
                )
            im = request.headers.get("If-Match", "")
            seen_if_matches.append(im)
            if im == '"v1"':
                return httpx.Response(
                    412,
                    json={"error": {"code": "CONFIG_VERSION_MISMATCH", "message": "version changed", "retryable": False, "details": [{"field": "config_version", "message": "expected=1, current=2"}], "request_id": "req_412"}},
                )
            assert im == '"v2"'
            return httpx.Response(
                202,
                json={"operation": {"operation_id": "op_upd_2", "group_id": "grp_1", "action": "update", "status": "succeeded", "generation": 2, "retryable": False, "steps": [], "created_at": "2026-11-27T08:00:00Z", "updated_at": "2026-11-27T08:00:00Z"}},
            )
        return httpx.Response(404)

    store = CredentialStore(config_path=tmp_path / "cfg.json", secret_backend=_MemSecrets())
    auth = AuthCoordinator(credential_store=store)
    client = FlightLinkApiClient(auth, transport=httpx.MockTransport(handler))
    runner = BackgroundTaskRunner()
    ws = WorkspaceViewModel(client, auth, runner, overview_interval_ms=60000, detail_interval_ms=60000)
    ops = OperationsViewModel(client, auth, runner, ws)

    try:
        client.login("http://127.0.0.1:8000", "ops", "Pass123!")
        ep = auth.current_epoch()
        ws.onSessionStarted(ep, "ecs-1", "http://127.0.0.1:8000")
        ops.onSessionStarted(ep, "ecs-1", "http://127.0.0.1:8000")

        ops.openEditDialog("grp_1")
        _pump(app, lambda: ops.draftName == "一号机" and ops.dialogConfigVersion == 1)

        # Modify draft & run dry_run=true -> 200 preview, dialog stays open, no active operation
        ops.updateDraft("一号机-改", "5760", "udp", "14554")
        ops.runEditDryRun()
        _pump(app, lambda: not ops.dryRunning and "预演结果" in ops.dryRunSummary)
        assert ops.dialogOpen is True
        assert ops.hasActiveOperation is False

        # Formal submit with stale ETag "v1" -> 412 -> MUST preserve user's draft AND reload to v2!
        ops.submitDialog()
        _pump(app, lambda: not ops.submitting and ops.dialogConfigVersion == 2 and bool(ops.versionReloadedNotice))
        assert ops.draftName == "一号机-改"
        assert ops.draftGcsProtocol == "udp"
        assert ops.draftGcsPort == "14554"

        # Resubmit with reloaded ETag "v2" -> 202 accepted!
        ops.submitDialog()
        _pump(app, lambda: not ops.dialogOpen and ops.activeOperationId == "op_upd_2")
        assert seen_if_matches == ['"v1"', '"v2"']
    finally:
        ops.stop_tracking()
        ws.stop_polling()
        runner.shutdown()
        client.close()


def test_needs_verification_stops_auto_poll_and_allows_admin_retry(tmp_path: Path) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QCoreApplication.instance() or QCoreApplication([])

    op1_polls = 0
    retry_called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal op1_polls, retry_called
        base = _base_auth_responses(request.url.path)
        if base is not None:
            return base
        if request.url.path == "/api/v1/groups/grp_1/actions/sync-security-group":
            return httpx.Response(
                202,
                json={"operation": {"operation_id": "op_sg_1", "group_id": "grp_1", "action": "sync_security_group", "status": "running", "generation": 1, "retryable": False, "steps": [], "created_at": "2026-11-27T08:00:00Z", "updated_at": "2026-11-27T08:00:00Z"}},
            )
        if request.url.path == "/api/v1/operations/op_sg_1":
            op1_polls += 1
            return httpx.Response(
                200,
                json={
                    "operation_id": "op_sg_1", "group_id": "grp_1", "action": "sync_security_group",
                    "status": "needs_verification", "generation": 1, "retryable": True,
                    "retry_hint": "请核对阿里云安全组规则后点击重试核验",
                    "steps": [{"step_name": "apply_sg_rules", "status": "needs_verification", "detail": "timeout"}],
                    "created_at": "2026-11-27T08:00:00Z", "updated_at": "2026-11-27T08:00:01Z",
                },
            )
        if request.url.path == "/api/v1/operations/op_sg_1/retry":
            retry_called = True
            return httpx.Response(
                202,
                json={"operation": {"operation_id": "op_sg_2", "group_id": "grp_1", "action": "sync_security_group", "status": "succeeded", "generation": 1, "retryable": False, "steps": [{"step_name": "verify_sg", "status": "succeeded"}], "created_at": "2026-11-27T08:00:02Z", "updated_at": "2026-11-27T08:00:03Z"}},
            )
        return httpx.Response(404)

    store = CredentialStore(config_path=tmp_path / "cfg.json", secret_backend=_MemSecrets())
    auth = AuthCoordinator(credential_store=store)
    client = FlightLinkApiClient(auth, transport=httpx.MockTransport(handler))
    runner = BackgroundTaskRunner()
    ws = WorkspaceViewModel(client, auth, runner, overview_interval_ms=60000, detail_interval_ms=60000)
    ops = OperationsViewModel(client, auth, runner, ws)

    try:
        client.login("http://127.0.0.1:8000", "ops", "Pass123!")
        ep = auth.current_epoch()
        ws.onSessionStarted(ep, "ecs-1", "http://127.0.0.1:8000")
        ops.onSessionStarted(ep, "ecs-1", "http://127.0.0.1:8000")

        ops.triggerGroupAction("grp_1", "sync-security-group")
        _pump(app, lambda: ops.activeStatus == "needs_verification", timeout_s=4.0)
        assert ops.canRetryActive is True
        assert "核验建议" in ops.activeStepsText
        polls_at_stop = op1_polls

        # Verify auto-polling truly stopped on needs_verification
        time.sleep(0.7)
        app.processEvents()
        assert op1_polls == polls_at_stop

        # Admin clicks retry -> POST /operations/op_sg_1/retry -> 202 -> succeeded
        ops.retryActiveOperation()
        _pump(app, lambda: ops.activeOperationId == "op_sg_2" and ops.activeStatus == "succeeded", timeout_s=4.0)
        assert retry_called is True
    finally:
        ops.stop_tracking()
        ws.stop_polling()
        runner.shutdown()
        client.close()


def test_paused_live_updates_freezes_detail_refresh_on_operation_terminal(tmp_path: Path) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QCoreApplication.instance() or QCoreApplication([])

    detail_gets = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal detail_gets
        base = _base_auth_responses(request.url.path)
        if base is not None:
            return base
        if request.url.path == "/api/v1/groups/grp_1" and request.method == "GET":
            detail_gets += 1
            return httpx.Response(
                200,
                headers={"ETag": '"v1"'},
                json={
                    "group_id": "grp_1", "name": "一号机", "dtu_protocol": "udp", "dtu_port": 5760,
                    "gcs_protocol": "tcp", "gcs_port": 14552, "config_version": 1,
                    "desired_state": "running", "lifecycle_state": "running", "operation_generation": 1,
                    "fc_state": "offline", "gcs_state": "disconnected",
                    "router": {"state": "running", "verified_listening": True, "observed_at": "2026-11-27T08:00:00Z", "stale": False},
                    "mavproxy": {"state": "waiting", "observed_at": "2026-11-27T08:00:00Z", "stale": False},
                    "security_group": {"state": "synced", "owned_rule_count": 2, "observed_at": "2026-11-27T08:00:00Z", "stale": False},
                    "observed_at": "2026-11-27T08:00:00Z", "stale": False,
                },
            )
        if request.url.path == "/api/v1/groups/grp_1/actions/restart":
            return httpx.Response(
                202,
                json={"operation": {"operation_id": "op_rst_1", "group_id": "grp_1", "action": "restart", "status": "succeeded", "generation": 2, "retryable": False, "steps": [], "created_at": "2026-11-27T08:00:00Z", "updated_at": "2026-11-27T08:00:01Z"}},
            )
        return httpx.Response(200, json={"items": [], "next_cursor": None})

    store = CredentialStore(config_path=tmp_path / "cfg.json", secret_backend=_MemSecrets())
    auth = AuthCoordinator(credential_store=store)
    client = FlightLinkApiClient(auth, transport=httpx.MockTransport(handler))
    runner = BackgroundTaskRunner()
    ws = WorkspaceViewModel(client, auth, runner, overview_interval_ms=60000, detail_interval_ms=60000)
    ops = OperationsViewModel(client, auth, runner, ws)

    try:
        client.login("http://127.0.0.1:8000", "ops", "Pass123!")
        ep = auth.current_epoch()
        ws.onSessionStarted(ep, "ecs-1", "http://127.0.0.1:8000")
        ops.onSessionStarted(ep, "ecs-1", "http://127.0.0.1:8000")

        ws.openGroupDetail("grp_1")
        _pump(app, lambda: detail_gets >= 1)

        # Pause live updates -> detail page reads MUST stay frozen even when an operation reaches terminal state
        ws.toggleLiveUpdates()
        assert ws.liveUpdatesEnabled is False
        gets_before_op = detail_gets

        ops.triggerGroupAction("grp_1", "restart")
        _pump(app, lambda: ops.activeOperationId == "op_rst_1" and ops.activeStatus == "succeeded", timeout_s=4.0)
        time.sleep(0.15)
        app.processEvents()
        assert detail_gets == gets_before_op

        # Resuming live updates immediately refreshes the paused detail view
        ws.toggleLiveUpdates()
        assert ws.liveUpdatesEnabled is True
        _pump(app, lambda: detail_gets > gets_before_op, timeout_s=4.0)
    finally:
        ops.stop_tracking()
        ws.stop_polling()
        runner.shutdown()
        client.close()
