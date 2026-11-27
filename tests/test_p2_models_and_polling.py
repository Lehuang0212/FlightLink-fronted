"""P2 tests: 12 telemetry cards (null vs 0/false), independent stale services, 500-row incremental logs, 404->archive fallback, lazy /entries."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
import pytest
from PySide6.QtCore import QCoreApplication

from flightlink_desktop.api.auth import AuthCoordinator
from flightlink_desktop.api.client import FlightLinkApiClient
from flightlink_desktop.api.credentials import CredentialStore
from flightlink_desktop.models.formatters import build_telemetry_cards, format_service_cards
from flightlink_desktop.models.list_models import LiveLogListModel
from flightlink_desktop.models.workspace_vm import WorkspaceViewModel
from flightlink_desktop.workers.task_runner import BackgroundTaskRunner


class _MemSecrets:
    def __init__(self) -> None:
        self._d: dict[tuple[str, str], str] = {}
    def get_password(self, s: str, u: str) -> str | None: return self._d.get((s, u))
    def set_password(self, s: str, u: str, p: str) -> None: self._d[(s, u)] = p
    def delete_password(self, s: str, u: str) -> None: self._d.pop((s, u), None)


def test_telemetry_cards_null_displays_dash_and_preserves_zero_and_false() -> None:
    all_null = build_telemetry_cards(
        {
            "flight_mode": None,
            "armed": None,
            "battery_remaining_pct": None,
            "battery_voltage_v": None,
            "gps_satellites": None,
            "gps_fix_type": None,
            "gps_hdop": None,
            "altitude_msl_m": None,
            "relative_altitude_m": None,
            "ground_speed_mps": None,
            "rx_rate_kbps": None,
            "tx_rate_kbps": None,
            "packets_lost": None,
            "packets_received": None,
            "packet_loss_pct": None,
            "observed_at": None,
            "stale": False,
        },
        sysid=None,
    )
    assert len(all_null) == 12
    assert all(card["value"] == "—" for card in all_null)

    # Real 0, 0.0, and False MUST be preserved!
    zeros_and_false = build_telemetry_cards(
        {
            "flight_mode": "MANUAL",
            "armed": False,
            "battery_remaining_pct": 0,
            "battery_voltage_v": 0.0,
            "gps_satellites": 0,
            "gps_fix_type": "NO_FIX",
            "gps_hdop": 0.0,
            "altitude_msl_m": 0.0,
            "relative_altitude_m": 0.0,
            "ground_speed_mps": 0.0,
            "rx_rate_kbps": 0.0,
            "tx_rate_kbps": 0.0,
            "packets_lost": 0,
            "packets_received": 0,
            "packet_loss_pct": 0.0,
            "observed_at": "2026-11-27T08:00:00Z",
            "stale": False,
        },
        sysid=1,
    )
    by_key = {c["key"]: c for c in zeros_and_false}
    assert by_key["flight_mode"]["value"] == "MANUAL"
    assert by_key["flight_mode"]["sub"] == "SYSID 1"
    assert by_key["armed"]["value"] == "未解锁"
    assert by_key["battery_remaining_pct"]["value"] == "0%"
    assert by_key["battery_voltage_v"]["value"] == "0.0 V"
    assert by_key["gps_satellites"]["value"] == "0"
    assert by_key["altitude_msl_m"]["value"] == "0.0 m"
    assert by_key["relative_altitude_m"]["value"] == "0.0 m"
    assert by_key["ground_speed_mps"]["value"] == "0.0 m/s"
    assert by_key["rx_rate_kbps"]["value"] == "0.00 KB/s"
    assert by_key["tx_rate_kbps"]["value"] == "0.00 KB/s"
    assert by_key["packets"]["value"] == "0 / 0"
    assert by_key["packets"]["sub"] == "丢包率 0.0%"


def test_group_services_distinguish_stale_from_offline() -> None:
    services = format_service_cards(
        {
            "gcs_peer": "10.0.0.5:14552",
            "router": {"state": "running", "pid": 4210, "uptime_seconds": 120, "observed_at": "2026-11-27T08:00:00Z", "stale": True},
            "mavproxy": {"state": "disconnected", "observed_at": "2026-11-27T08:00:00Z", "stale": False},
            "security_group": {"state": "synced", "owned_rule_count": 2, "observed_at": "2026-11-27T08:00:00Z", "stale": True},
        }
    )
    by_key = {s["key"]: s for s in services}
    # Stale running router is STILL labeled "运行中" with stale=True separately (NOT offline/stopped!)
    assert by_key["router"]["stateLabel"] == "运行中"
    assert by_key["router"]["stale"] is True
    assert by_key["mavproxy"]["title"] == "MAVProxy 会话"
    assert by_key["mavproxy"]["stateLabel"] == "未连接"
    assert by_key["mavproxy"]["stale"] is False
    assert by_key["security_group"]["stateLabel"] == "已同步"
    assert by_key["security_group"]["stale"] is True


def test_live_log_model_500_row_incremental_append_trim_and_local_clear() -> None:
    model = LiveLogListModel(max_rows=500)
    reset_count = 0
    insert_count = 0
    remove_count = 0

    model.modelReset.connect(lambda: globals().setdefault("_", None))
    def on_reset() -> None:
        nonlocal reset_count
        reset_count += 1
    def on_insert(_p: Any, _first: int, _last: int) -> None:
        nonlocal insert_count
        insert_count += 1
    def on_remove(_p: Any, _first: int, _last: int) -> None:
        nonlocal remove_count
        remove_count += 1

    model.modelReset.connect(on_reset)
    model.rowsInserted.connect(on_insert)
    model.rowsRemoved.connect(on_remove)

    batch1 = [
        {"event_id": f"ev_{i}", "group_id": "grp_1", "source": "router", "level": "INFO", "ts": "2026-11-27T08:00:00Z", "text": f"line {i}"}
        for i in range(450)
    ]
    model.cursor = "cur_450"
    model.append_entries(batch1)
    assert model.rowCount() == 450
    assert reset_count == 0
    assert insert_count == 1

    # Pause scroll & append 100 more -> trims oldest 50 via rowsRemoved, NO modelReset, increments unreadCount
    model.setFollow(False)
    batch2 = [
        {"event_id": f"ev_{i}", "group_id": "grp_1", "source": "router", "level": "WARN", "ts": "2026-11-27T08:00:01Z", "text": f"line {i}"}
        for i in range(450, 550)
    ]
    model.append_entries(batch2)
    assert model.rowCount() == 500
    assert reset_count == 0
    assert insert_count == 2
    assert remove_count == 1
    assert model.unreadCount == 100
    assert model.data(model.index(0, 0), LiveLogListModel.EventIdRole) == "ev_50"
    assert model.data(model.index(499, 0), LiveLogListModel.EventIdRole) == "ev_549"

    # Local clear moves display start only — keeps server cursor intact and does not reset
    model.clearLocalDisplay()
    assert model.rowCount() == 0
    assert model.cursor == "cur_450"
    assert reset_count == 0


def test_deleted_group_404_redirects_to_archive_only_when_archive_200_and_lazy_entries(tmp_path: Path) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QCoreApplication.instance() or QCoreApplication([])
    called_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        called_paths.append(request.url.path)
        p = request.url.path
        if p == "/api/v1/health":
            return httpx.Response(200, json={"status": "ok", "version": "1.0.0", "ecs_instance_id": "ecs-1", "observed_at": "2026-11-27T08:00:00Z", "db_ok": True})
        if p == "/api/v1/auth/login":
            return httpx.Response(200, json={
                "access_token": "tok_1", "refresh_token": "ref_1_1234567890", "token_type": "bearer",
                "expires_at": "2026-11-28T00:00:00Z", "refresh_expires_at": "2026-12-05T00:00:00Z",
                "user": {"user_id": "u1", "username": "ops", "display_name": "Ops", "role": "admin", "created_at": "2026-11-01T00:00:00Z"},
            })
        if p == "/api/v1/overview":
            return httpx.Response(200, json={
                "ecs_instance_id": "ecs-1", "observed_at": "2026-11-27T08:00:00Z", "stale": False, "stale_after_seconds": 30,
                "components": [], "metrics": {"group_count": 0, "max_groups": 5, "running_router_count": 0, "online_fc_count": 0, "needs_verification_count": 0},
                "disk": {"archive_dir": "/var/lib/flightlink/archive", "status": "ok", "observed_at": "2026-11-27T08:00:00Z"},
                "groups": [],
            })
        if p == "/api/v1/groups/grp_deleted":
            return httpx.Response(404, json={"error": {"code": "GROUP_NOT_FOUND", "message": "deleted", "retryable": False, "request_id": "r404"}})
        if p == "/api/v1/archive/groups/grp_deleted":
            return httpx.Response(200, json={
                "group_id": "grp_deleted", "name_snapshot": "一号机", "dtu_protocol": "udp",
                "dtu_port_snapshot": 5760, "gcs_protocol_snapshot": "tcp", "gcs_port_snapshot": 14552,
                "deleted": True, "deleted_at": "2026-11-27T07:50:00Z", "active_session_count": 0, "sealed_session_count": 1,
            })
        if p == "/api/v1/archive/groups/grp_deleted/sessions":
            return httpx.Response(200, json={
                "group_id": "grp_deleted", "next_cursor": None, "has_more": False,
                "items": [{
                    "ecs_instance_id": "ecs-1", "session_id": "sess_001", "group_id": "grp_deleted",
                    "group_name_snapshot": "一号机", "status": "sealed", "sysid": 1,
                    "first_observed_at": "2026-11-27T07:00:00Z", "last_heartbeat_at": "2026-11-27T07:40:00Z",
                    "ended_at": "2026-11-27T07:45:00Z", "expires_at": "2026-12-04T07:45:00Z",
                    "close_reason": "admin_group_deleted", "has_gaps": False, "has_missing_sources": False, "files": [],
                }],
            })
        if p == "/api/v1/archive/sessions/sess_001/entries":
            return httpx.Response(200, json={
                "session_id": "sess_001", "source": "router", "source_availability": "available",
                "items": [{"event_id": "e1", "group_id": "grp_deleted", "source": "router", "level": "INFO", "ts": "2026-11-27T07:01:00Z", "text": "router started"}],
                "gaps": [], "next_cursor": None, "has_more": False,
            })
        if p == "/api/v1/logs":
            return httpx.Response(200, json={"items": [], "next_cursor": None, "has_more": False, "observed_at": "2026-11-27T08:00:00Z"})
        return httpx.Response(404)

    store = CredentialStore(config_path=tmp_path / "cfg.json", secret_backend=_MemSecrets())
    auth = AuthCoordinator(credential_store=store)
    client = FlightLinkApiClient(auth, transport=httpx.MockTransport(handler))
    runner = BackgroundTaskRunner()
    vm = WorkspaceViewModel(client, auth, runner, overview_interval_ms=60000, detail_interval_ms=60000)

    def pump(predicate, timeout_s: float = 3.0) -> None:
        import time
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            app.processEvents()
            if predicate():
                return
            time.sleep(0.01)
        raise AssertionError("Timed out waiting for condition")

    try:
        client.login("http://127.0.0.1:8000", "ops", "Pass123!")
        vm.onSessionStarted(auth.current_epoch(), "ecs-1", "http://127.0.0.1:8000")
        vm.openGroupDetail("grp_deleted")

        # Wait for 404 GROUP_NOT_FOUND -> GET /archive/groups/grp_deleted (200) -> redirect to historyDetail
        pump(lambda: vm.route == "historyDetail" and vm.archiveSessionsModel.rowCount() == 1)
        assert vm.historyGroupId == "grp_deleted"
        assert vm.historyGroupMeta["deleted"] is True
        # Metadata first: /entries MUST NOT have been called before expanding slice!
        assert "/api/v1/archive/sessions/sess_001/entries" not in called_paths

        # Now expand slice -> lazy loads /entries
        vm.toggleHistorySlice("sess_001")
        pump(lambda: "/api/v1/archive/sessions/sess_001/entries" in called_paths and vm.archiveSessionsModel.data(vm.archiveSessionsModel.index(0, 0), vm.archiveSessionsModel.EntriesCountRole) == 1)
        assert vm.archiveSessionsModel.is_expanded("sess_001") is True
    finally:
        vm.stop_polling()
        runner.shutdown()
        client.close()
