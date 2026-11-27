"""Test-only screenshot harness rendering real FlightLink Desktop 1.0 Qt Quick windows via injected httpx.MockTransport.

Produces visual verification PNGs under docs/desktop/screenshots/ at 1280x800, 1440x900, 1600x1000,
plus all required error/role/operation/archive edge states and 125% DPI check.
(Production app has NO mock mode; this script is strictly a test-time visual verification harness.)
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickWindow

from flightlink_desktop.api.auth import AuthCoordinator
from flightlink_desktop.api.client import FlightLinkApiClient
from flightlink_desktop.api.credentials import CredentialStore
from flightlink_desktop.app import DesktopRuntime, build_engine
from flightlink_desktop.archive.sync_engine import ArchiveSyncEngine
from flightlink_desktop.archive.worker import ArchiveSyncWorker
from flightlink_desktop.workers.operation_tracker import TrackedOperation

OUT_DIR = Path(__file__).resolve().parents[1] / "docs" / "desktop" / "screenshots"


class _MemSecrets:
    def __init__(self) -> None:
        self._d: dict[tuple[str, str], str] = {}
    def get_password(self, s: str, u: str) -> str | None: return self._d.get((s, u))
    def set_password(self, s: str, u: str, p: str) -> None: self._d[(s, u)] = p
    def delete_password(self, s: str, u: str) -> None: self._d.pop((s, u), None)


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _build_mock_transport(state: dict[str, Any]) -> httpx.MockTransport:
    b_rtr = b"[2026-11-27T07:01:00Z] INFO mavlink-routerd bound UDP 5760 and TCP 14552\n"
    b_mav = b"[2026-11-27T07:01:02Z] INFO MAVProxy observer connected to SYSID 1\n"
    b_meta = b'{"session_id":"sess_001","group_id":"grp_1"}'

    def handler(request: httpx.Request) -> httpx.Response:
        p = request.url.path
        if p == "/api/v1/health":
            return httpx.Response(200, json={"status": "ok", "version": "1.0.0", "ecs_instance_id": "ecs-vis-01", "observed_at": "2026-11-27T08:00:00Z", "db_ok": True})
        if p == "/api/v1/auth/login":
            role = state.get("role", "admin")
            if state.get("fail_login"):
                return httpx.Response(401, json={"error": {"code": "INVALID_CREDENTIALS", "message": "账号或密码错误。", "retryable": False, "request_id": "req_vis_401"}})
            return httpx.Response(200, json={
                "access_token": "tok_vis", "refresh_token": "ref_vis_123456789012", "token_type": "bearer",
                "expires_at": "2026-11-28T00:00:00Z", "refresh_expires_at": "2026-12-05T00:00:00Z",
                "user": {
                    "user_id": "u_vis",
                    "username": "ops_admin" if role == "admin" else "ops_viewer",
                    "display_name": "运维管理员" if role == "admin" else "值守观测员",
                    "role": role,
                    "created_at": "2026-11-01T00:00:00Z",
                },
            })
        if p == "/api/v1/overview":
            groups = _sample_groups()
            return httpx.Response(200, json={
                "ecs_instance_id": "ecs-vis-01", "observed_at": "2026-11-27T08:00:00Z", "stale": False, "stale_after_seconds": 30,
                "components": [
                    {"name": "flightlink-api", "status": "ok", "observed_at": "2026-11-27T08:00:00Z", "stale": False, "detail": "listening :8000"},
                    {"name": "flightlink-agent", "status": "ok", "observed_at": "2026-11-27T08:00:00Z", "stale": False, "detail": "2 active routers"},
                    {"name": "flightlink-archive", "status": "ok", "observed_at": "2026-11-27T08:00:00Z", "stale": False, "detail": "7d retention"},
                ],
                "metrics": {"group_count": 3, "max_groups": 5, "running_router_count": 2, "online_fc_count": 1, "needs_verification_count": 0},
                "disk": {"archive_dir": "/var/lib/flightlink/archive", "status": "ok", "total_bytes": 42949672960, "free_bytes": 35433480192, "archive_used_bytes": 134217728, "observed_at": "2026-11-27T08:00:00Z"},
                "groups": groups,
            })
        if p == "/api/v1/groups":
            return httpx.Response(200, json={"items": _sample_groups(), "total": 3, "max_groups": 5, "observed_at": "2026-11-27T08:00:00Z"})
        if p == "/api/v1/groups/grp_1":
            g = dict(_sample_groups()[0])
            if state.get("empty_telemetry"):
                g["sysid"] = None
                g["fc_state"] = "offline"
                g["telemetry"] = {
                    k: None for k in (
                        "flight_mode", "armed", "battery_remaining_pct", "battery_voltage_v",
                        "gps_satellites", "gps_fix_type", "gps_hdop", "altitude_msl_m",
                        "relative_altitude_m", "ground_speed_mps", "rx_rate_kbps", "tx_rate_kbps",
                        "packets_lost", "packets_received", "packet_loss_pct", "observed_at",
                    )
                }
                g["telemetry"]["stale"] = False
            else:
                g["telemetry"] = {
                    "flight_mode": "AUTO.LOITER", "armed": True, "battery_remaining_pct": 86,
                    "battery_voltage_v": 24.6, "gps_satellites": 17, "gps_fix_type": "RTK Fixed",
                    "gps_hdop": 0.62, "altitude_msl_m": 512.5, "relative_altitude_m": 118.4,
                    "ground_speed_mps": 6.2, "rx_rate_kbps": 4.74, "tx_rate_kbps": 3.95,
                    "packets_lost": 2, "packets_received": 441, "packet_loss_pct": 0.5,
                    "observed_at": "2026-11-27T08:00:00Z", "stale": False,
                }
            g["recent_gcs_commands"] = [
                {"id": "c1", "observed_at": "2026-11-27T07:59:10Z", "command": "MAV_CMD_NAV_LOITER_UNLIM", "detail": "alt=118m", "status": "ACCEPTED", "source_label": "QGC 10.0.3.21"},
                {"id": "c2", "observed_at": "2026-11-27T07:58:02Z", "command": "MAV_CMD_COMPONENT_ARM_DISARM", "detail": "arm=1", "status": "ACCEPTED", "source_label": "QGC 10.0.3.21"},
            ]
            return httpx.Response(200, headers={"ETag": '"v3"'}, json=g)
        if p == "/api/v1/logs":
            src = request.url.params.get("source", "all")
            items = [
                {"event_id": f"e_{src}_1", "group_id": "grp_1", "source": "router" if src != "mavproxy" else "mavproxy", "level": "INFO", "ts": "2026-11-27T07:59:55.120Z", "text": "DTU UDP 5760 heartbeat active (SYSID 1)"},
                {"event_id": f"e_{src}_2", "group_id": "grp_1", "source": "mavproxy" if src != "router" else "router", "level": "INFO", "ts": "2026-11-27T07:59:56.402Z", "text": "Forwarding telemetry stream to GCS 10.0.3.21:14552"},
                {"event_id": f"e_{src}_3", "group_id": "grp_1", "source": "router" if src != "mavproxy" else "mavproxy", "level": "WARN", "ts": "2026-11-27T07:59:58.015Z", "text": "Transient jitter 42ms on uplink"},
            ]
            return httpx.Response(200, json={"items": items, "next_cursor": "lc_3", "has_more": False, "observed_at": "2026-11-27T08:00:00Z"})
        if p == "/api/v1/archive/groups":
            return httpx.Response(200, json={
                "ecs_instance_id": "ecs-vis-01", "observed_at": "2026-11-27T08:00:00Z",
                "items": [
                    {
                        "group_id": "grp_1", "name_snapshot": "一号机", "dtu_protocol": "udp", "dtu_port_snapshot": 5760,
                        "gcs_protocol_snapshot": "tcp", "gcs_port_snapshot": 14552, "deleted": False,
                        "active_session_count": 0, "sealed_session_count": 3,
                        "latest_session": {"ecs_instance_id": "ecs-vis-01", "session_id": "sess_001", "group_id": "grp_1", "group_name_snapshot": "一号机", "status": "sealed", "first_observed_at": "2026-11-27T07:00:00Z", "last_heartbeat_at": "2026-11-27T07:20:00Z", "ended_at": "2026-11-27T07:21:00Z", "has_gaps": False, "has_missing_sources": False, "files": []},
                    },
                    {
                        "group_id": "grp_old", "name_snapshot": "一号机（旧组）", "dtu_protocol": "udp", "dtu_port_snapshot": 5760,
                        "gcs_protocol_snapshot": "tcp", "gcs_port_snapshot": 14552, "deleted": True,
                        "deleted_at": "2026-11-26T18:00:00Z", "active_session_count": 0, "sealed_session_count": 1,
                        "latest_session": {"ecs_instance_id": "ecs-vis-01", "session_id": "sess_old", "group_id": "grp_old", "group_name_snapshot": "一号机（旧组）", "status": "sealed", "first_observed_at": "2026-11-26T14:00:00Z", "last_heartbeat_at": "2026-11-26T14:30:00Z", "ended_at": "2026-11-26T14:31:00Z", "has_gaps": False, "has_missing_sources": False, "files": []},
                    },
                ],
            })
        if p == "/api/v1/archive/groups/grp_1":
            return httpx.Response(200, json={
                "group_id": "grp_1", "name_snapshot": "一号机", "dtu_protocol": "udp", "dtu_port_snapshot": 5760,
                "gcs_protocol_snapshot": "tcp", "gcs_port_snapshot": 14552, "deleted": False,
                "active_session_count": 0, "sealed_session_count": 3,
            })
        if p == "/api/v1/archive/groups/grp_1/sessions":
            return httpx.Response(200, json={
                "group_id": "grp_1", "next_cursor": None, "has_more": False,
                "items": [
                    {"ecs_instance_id": "ecs-vis-01", "session_id": "sess_saved", "group_id": "grp_1", "group_name_snapshot": "一号机", "status": "sealed", "sysid": 1, "first_observed_at": "2026-11-27T07:00:00Z", "last_heartbeat_at": "2026-11-27T07:20:00Z", "ended_at": "2026-11-27T07:21:00Z", "expires_at": "2026-12-04T07:21:00Z", "close_reason": "fc_heartbeat_timeout", "has_gaps": False, "has_missing_sources": False, "files": []},
                    {"ecs_instance_id": "ecs-vis-01", "session_id": "sess_gap", "group_id": "grp_1", "group_name_snapshot": "一号机", "status": "sealed", "sysid": 1, "first_observed_at": "2026-11-27T06:00:00Z", "last_heartbeat_at": "2026-11-27T06:15:00Z", "ended_at": "2026-11-27T06:16:00Z", "expires_at": "2026-12-04T06:16:00Z", "close_reason": "fc_heartbeat_timeout", "has_gaps": True, "has_missing_sources": True, "files": []},
                    {"ecs_instance_id": "ecs-vis-01", "session_id": "sess_fail", "group_id": "grp_1", "group_name_snapshot": "一号机", "status": "sealed", "sysid": 1, "first_observed_at": "2026-11-27T05:00:00Z", "last_heartbeat_at": "2026-11-27T05:10:00Z", "ended_at": "2026-11-27T05:11:00Z", "expires_at": "2026-12-04T05:11:00Z", "close_reason": "fc_heartbeat_timeout", "has_gaps": False, "has_missing_sources": False, "files": []},
                ],
            })
        if p == "/api/v1/archive/changes":
            return httpx.Response(200, json={"ecs_instance_id": "ecs-vis-01", "retention_seconds": 604800, "items": [], "next_cursor": "c0", "has_more": False, "observed_at": "2026-11-27T08:00:00Z"})
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def _sample_groups() -> list[dict[str, Any]]:
    return [
        {
            "group_id": "grp_1", "name": "一号机", "dtu_protocol": "udp", "dtu_port": 5760,
            "gcs_protocol": "tcp", "gcs_port": 14552, "config_version": 3,
            "desired_state": "running", "lifecycle_state": "running", "operation_generation": 3,
            "sysid": 1, "fc_state": "online", "dtu_peer": "172.22.11.8:51021",
            "gcs_state": "connected", "gcs_peer": "10.0.3.21:54108",
            "link_quality_pct": 99, "rtt_ms": 18, "observed_at": "2026-11-27T08:00:00Z", "stale": False,
            "router": {"state": "running", "pid": 4821, "uptime_seconds": 247, "verified_listening": True, "observed_at": "2026-11-27T08:00:00Z", "stale": False},
            "mavproxy": {"state": "connected", "uptime_seconds": 119, "observed_at": "2026-11-27T08:00:00Z", "stale": False},
            "security_group": {"state": "synced", "owned_rule_count": 2, "observed_at": "2026-11-27T08:00:00Z", "stale": False},
        },
        {
            "group_id": "grp_2", "name": "二号机", "dtu_protocol": "udp", "dtu_port": 5761,
            "gcs_protocol": "udp", "gcs_port": 14553, "config_version": 1,
            "desired_state": "running", "lifecycle_state": "running", "operation_generation": 1,
            "sysid": None, "fc_state": "offline", "dtu_peer": None,
            "gcs_state": "idle", "gcs_peer": None,
            "link_quality_pct": None, "rtt_ms": None, "observed_at": "2026-11-27T07:58:00Z", "stale": True,
            "router": {"state": "running", "pid": 5102, "uptime_seconds": 980, "verified_listening": True, "observed_at": "2026-11-27T07:58:00Z", "stale": True},
            "mavproxy": {"state": "waiting", "observed_at": "2026-11-27T08:00:00Z", "stale": False},
            "security_group": {"state": "synced", "owned_rule_count": 2, "observed_at": "2026-11-27T08:00:00Z", "stale": False},
        },
        {
            "group_id": "grp_3", "name": "三号机（待机）", "dtu_protocol": "udp", "dtu_port": 5762,
            "gcs_protocol": "tcp", "gcs_port": 14554, "config_version": 1,
            "desired_state": "stopped", "lifecycle_state": "configured_stopped", "operation_generation": 1,
            "sysid": None, "fc_state": "offline", "dtu_peer": None,
            "gcs_state": "disconnected", "gcs_peer": None,
            "link_quality_pct": None, "rtt_ms": None, "observed_at": "2026-11-27T08:00:00Z", "stale": False,
            "router": {"state": "stopped", "verified_listening": False, "observed_at": "2026-11-27T08:00:00Z", "stale": False},
            "mavproxy": {"state": "disconnected", "observed_at": "2026-11-27T08:00:00Z", "stale": False},
            "security_group": {"state": "unconfigured", "owned_rule_count": 0, "observed_at": "2026-11-27T08:00:00Z", "stale": False},
        },
    ]


def _pump(app: QCoreApplication, ms: int = 180) -> None:
    deadline = time.monotonic() + ms / 1000.0
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)


def _grab(window, app: QCoreApplication, width: int, height: int, filename: str) -> None:
    window.resize(width, height)
    _pump(app, 220)
    img = window.grabWindow()
    out_path = OUT_DIR / filename
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ok = img.save(str(out_path))
    assert ok, f"Failed to save screenshot {out_path}"
    print(f"CAPTURED {filename} ({img.width()}x{img.height()})")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dpi125", action="store_true", help="Capture 125% DPI subset")
    args = parser.parse_args()

    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    app = QGuiApplication(sys.argv)
    screen = app.primaryScreen()
    if screen is not None:
        print(f"SCREEN_SCALING devicePixelRatio={screen.devicePixelRatio()} logicalDpi={screen.logicalDotsPerInch():.1f}")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        os.environ["FLIGHTLINK_DATA_DIR"] = str(tmp_path / "appdata")
        state: dict[str, Any] = {"role": "admin", "fail_login": False, "empty_telemetry": False}
        transport = _build_mock_transport(state)

        runtime = DesktopRuntime(app)
        # Swap test transport cleanly before any requests
        runtime.credential_store = CredentialStore(config_path=tmp_path / "cfg.json", secret_backend=_MemSecrets())
        runtime.auth = AuthCoordinator(credential_store=runtime.credential_store)
        runtime.api_client = FlightLinkApiClient(runtime.auth, transport=transport)
        runtime.session_vm._api = runtime.api_client
        runtime.session_vm._auth = runtime.auth
        runtime.session_vm._store = runtime.credential_store
        runtime.workspace_vm._api = runtime.api_client
        runtime.workspace_vm._auth = runtime.auth
        runtime.ops_vm._api = runtime.api_client
        runtime.ops_vm._auth = runtime.auth
        runtime.archive_engine = ArchiveSyncEngine(runtime.api_client, logs_root=tmp_path / "Logs", state_db_path=tmp_path / "sync.sqlite3")
        runtime.archive_worker.engine = runtime.archive_engine

        engine = build_engine(app, runtime)
        window = engine.rootObjects()[0]
        window.show()
        _pump(app, 200)

        try:
            if args.dpi125:
                _grab(window, app, 1280, 800, "state_login_1280_dpi125.png")
                runtime.session_vm.login("http://127.0.0.1:8000", "ops_admin", "StrongPass!2026", False)
                _pump(app, 300)
                runtime.workspace_vm.openGroupDetail("grp_1")
                _pump(app, 300)
                _grab(window, app, 1280, 800, "state_detail_1280_dpi125.png")
                return 0

            # 1. Login at 3 sizes + login error state
            runtime.session_vm.probeHealth("http://127.0.0.1:8000")
            _pump(app, 200)
            for w, h in ((1280, 800), (1440, 900), (1600, 1000)):
                _grab(window, app, w, h, f"login_{w}x{h}.png")

            state["fail_login"] = True
            runtime.session_vm.login("http://127.0.0.1:8000", "ops_admin", "wrongpass", False)
            _pump(app, 250)
            _grab(window, app, 1280, 800, "state_login_error_1280.png")

            # 2. Authenticate as admin & capture core views across 1280/1440/1600
            state["fail_login"] = False
            runtime.session_vm.login("http://127.0.0.1:8000", "ops_admin", "StrongPass!2026", False)
            _pump(app, 350)

            for w, h in ((1280, 800), (1440, 900), (1600, 1000)):
                runtime.workspace_vm.navigate("overview")
                _pump(app, 250)
                _grab(window, app, w, h, f"overview_{w}x{h}.png")

                runtime.workspace_vm.navigate("groups")
                _pump(app, 250)
                _grab(window, app, w, h, f"groups_{w}x{h}.png")

                runtime.workspace_vm.openGroupDetail("grp_1")
                _pump(app, 300)
                _grab(window, app, w, h, f"detail_{w}x{h}.png")

                runtime.workspace_vm.navigate("logs")
                _pump(app, 250)
                _grab(window, app, w, h, f"logs_{w}x{h}.png")

                runtime.workspace_vm.navigate("history")
                _pump(app, 250)
                _grab(window, app, w, h, f"history_{w}x{h}.png")

                runtime.workspace_vm.openHistoryGroup("grp_1", "")
                _pump(app, 250)
                runtime.workspace_vm.update_archive_summary(
                    local_root=str(tmp_path / "Logs"),
                    failed_count=0, failed_group_id="", failed_session_id="", failed_message="",
                    status_text="已自动保存 3 个切片", retention_gap_note="",
                    session_states={
                        "sess_saved": {"local_status": "saved", "show_retry_action": False, "last_error_message": ""},
                        "sess_gap": {"local_status": "saved_with_source_gaps", "show_retry_action": False, "last_error_message": "云端缺少或仅含部分来源：mavproxy（mavproxy_not_running）"},
                        "sess_fail": {"local_status": "saved", "show_retry_action": False, "last_error_message": ""},
                    },
                )
                _pump(app, 200)
                _grab(window, app, w, h, f"history_detail_{w}x{h}.png")

            # 3. Required edge states at 1280x800
            # 3a. Empty telemetry (all null -> —)
            state["empty_telemetry"] = True
            runtime.workspace_vm.openGroupDetail("grp_1")
            runtime.workspace_vm.pollGroupDetail()
            _pump(app, 300)
            _grab(window, app, 1280, 800, "state_empty_telemetry_1280.png")
            state["empty_telemetry"] = False

            # 3b. 202 Operation in progress
            runtime.workspace_vm.pollGroupDetail()
            _pump(app, 250)
            runtime.ops_vm._active_op = TrackedOperation.from_api(
                {
                    "operation_id": "op_202_demo", "group_id": "grp_1", "action": "restart",
                    "status": "running", "retryable": False,
                    "steps": [
                        {"step_name": "stop_router", "status": "succeeded"},
                        {"step_name": "start_router", "status": "running", "detail": "verifying port bind"},
                    ],
                },
                epoch=runtime.auth.current_epoch(),
            )
            runtime.ops_vm.operationChanged.emit()
            _grab(window, app, 1280, 800, "state_op_202_running_1280.png")

            # 3c. needs_verification with admin retry button
            runtime.ops_vm._active_op = TrackedOperation.from_api(
                {
                    "operation_id": "op_nv_demo", "group_id": "grp_1", "action": "sync_security_group",
                    "status": "needs_verification", "retryable": True,
                    "retry_hint": "请核实阿里云安全组入方向规则后点击「重试核验」",
                    "steps": [
                        {"step_name": "diff_sg_rules", "status": "succeeded"},
                        {"step_name": "apply_sg_rules", "status": "needs_verification", "detail": "cloud API timeout"},
                    ],
                },
                epoch=runtime.auth.current_epoch(),
            )
            runtime.ops_vm.operationChanged.emit()
            _grab(window, app, 1280, 800, "state_needs_verification_1280.png")
            runtime.ops_vm.dismissActiveOperation()

            # 3d. Cloud source gaps (saved_with_source_gaps — no retry button)
            runtime.workspace_vm.openHistoryGroup("grp_1", "")
            _pump(app, 250)
            runtime.workspace_vm.update_archive_summary(
                local_root=str(tmp_path / "Logs"),
                failed_count=0, failed_group_id="", failed_session_id="", failed_message="",
                status_text="已自动保存 2 个切片", retention_gap_note="",
                session_states={
                    "sess_saved": {"local_status": "saved", "show_retry_action": False, "last_error_message": ""},
                    "sess_gap": {"local_status": "saved_with_source_gaps", "show_retry_action": False, "last_error_message": "云端缺少或仅含部分来源：mavproxy（mavproxy_not_running）"},
                    "sess_fail": {"local_status": "saved", "show_retry_action": False, "last_error_message": ""},
                },
            )
            _grab(window, app, 1280, 800, "state_source_gaps_1280.png")

            # 3e. Local archive download failed (banner + 「重新下载日志」)
            runtime.workspace_vm.update_archive_summary(
                local_root=str(tmp_path / "Logs"),
                failed_count=1, failed_group_id="grp_1", failed_session_id="sess_fail",
                failed_message="下载 mavproxy.log 时网络中断，请恢复网络后点击「重新下载日志」",
                status_text="自动归档失败 1 个切片", retention_gap_note="",
                session_states={
                    "sess_saved": {"local_status": "saved", "show_retry_action": False, "last_error_message": ""},
                    "sess_gap": {"local_status": "saved_with_source_gaps", "show_retry_action": False, "last_error_message": "云端缺少或仅含部分来源：mavproxy（mavproxy_not_running）"},
                    "sess_fail": {"local_status": "failed", "show_retry_action": True, "last_error_message": "下载 mavproxy.log 时网络中断，请恢复网络后点击「重新下载日志」"},
                },
            )
            _grab(window, app, 1280, 800, "state_archive_failed_1280.png")

            # 3f. After retry succeeded (all saved, zero download buttons)
            runtime.workspace_vm.update_archive_summary(
                local_root=str(tmp_path / "Logs"),
                failed_count=0, failed_group_id="", failed_session_id="", failed_message="",
                status_text="已自动保存 3 个切片", retention_gap_note="",
                session_states={
                    "sess_saved": {"local_status": "saved", "show_retry_action": False, "last_error_message": ""},
                    "sess_gap": {"local_status": "saved", "show_retry_action": False, "last_error_message": ""},
                    "sess_fail": {"local_status": "saved", "show_retry_action": False, "last_error_message": ""},
                },
            )
            runtime.workspace_vm.showToast("补下载完成", "info")
            _grab(window, app, 1280, 800, "state_archive_retry_ok_1280.png")
            runtime.workspace_vm.dismissToast()

            # 3g. Viewer role (write actions & FAB hidden)
            runtime.session_vm.logout()
            _pump(app, 150)
            state["role"] = "viewer"
            runtime.session_vm.login("http://127.0.0.1:8000", "ops_viewer", "ViewerPass!1", False)
            _pump(app, 300)
            runtime.workspace_vm.openGroupDetail("grp_1")
            _pump(app, 300)
            _grab(window, app, 1280, 800, "state_viewer_1280.png")
            return 0
        finally:
            del window
            del engine
            runtime.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
