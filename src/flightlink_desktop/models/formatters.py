"""Pure formatting helpers for timestamps, 12 telemetry cards, services, and components."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

DASH = "—"


def format_local_time(iso_str: str | None, *, with_date: bool = False, with_ms: bool = False) -> str:
    """Convert UTC RFC 3339 timestamp to local timezone display string."""
    if not iso_str:
        return DASH
    try:
        raw = iso_str.strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        local_dt = dt.astimezone()
        if with_date:
            return local_dt.strftime("%Y-%m-%d %H:%M:%S")
        if with_ms:
            return local_dt.strftime("%H:%M:%S.") + f"{local_dt.microsecond // 1000:03d}"
        return local_dt.strftime("%H:%M:%S")
    except (ValueError, OSError):
        return iso_str


def format_uptime(seconds: int | None) -> str:
    if seconds is None:
        return DASH
    total = max(0, int(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def format_bytes(num_bytes: int | None) -> str:
    if num_bytes is None:
        return DASH
    val = float(max(0, int(num_bytes)))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if val < 1024.0 or unit == "TB":
            if unit == "B":
                return f"{int(val)} B"
            return f"{val:.1f} {unit}"
        val /= 1024.0
    return f"{val:.1f} TB"


def component_status_meta(status: str | None) -> tuple[str, str]:
    mapping = {
        "ok": ("正常", "ok"),
        "degraded": ("降级", "warn"),
        "stopped": ("已停止", "idle"),
        "unknown": ("未知", "warn"),
    }
    return mapping.get(status or "", (status or "未知", "idle"))


def lifecycle_status_meta(state: str | None) -> tuple[str, str]:
    mapping = {
        "configured_stopped": ("未启动", "idle"),
        "starting": ("启动中", "warn"),
        "running": ("运行中", "ok"),
        "stopping": ("停止中", "warn"),
        "updating": ("变更中", "warn"),
        "deleting": ("删除中", "warn"),
        "cleanup_pending": ("待清理", "warn"),
        "needs_verification": ("待核实", "warn"),
        "error": ("异常", "bad"),
    }
    return mapping.get(state or "", (state or "未知", "idle"))


def router_status_meta(state: str | None) -> tuple[str, str]:
    mapping = {
        "running": ("运行中", "ok"),
        "starting": ("启动中", "warn"),
        "stopped": ("未启动", "idle"),
        "error": ("异常", "bad"),
        "needs_verification": ("待核实", "warn"),
    }
    return mapping.get(state or "", (state or "未知", "idle"))


def mavproxy_status_meta(state: str | None) -> tuple[str, str]:
    mapping = {
        "connected": ("已连接", "ok"),
        "waiting": ("等待心跳", "warn"),
        "disconnected": ("未连接", "idle"),
        "error": ("异常", "bad"),
    }
    return mapping.get(state or "", (state or "未知", "idle"))


def sg_status_meta(state: str | None) -> tuple[str, str]:
    mapping = {
        "synced": ("已同步", "ok"),
        "syncing": ("同步中", "warn"),
        "drift": ("存在漂移", "warn"),
        "needs_verification": ("待核实", "warn"),
        "unconfigured": ("未配置", "idle"),
        "error": ("异常", "bad"),
    }
    return mapping.get(state or "", (state or "未知", "idle"))


def build_telemetry_cards(telemetry: dict[str, Any] | None, sysid: int | None) -> list[dict[str, Any]]:
    """Build the exact 12 telemetry cards aligned with FLightLink1.0-preview.

    Strict contract rules:
    - null / None MUST display as "—"
    - Genuine 0, 0.0, and False MUST be preserved (never treated as missing!)
    """
    t = telemetry if isinstance(telemetry, dict) else {}

    flight_mode = t.get("flight_mode")
    armed = t.get("armed")
    batt_pct = t.get("battery_remaining_pct")
    batt_v = t.get("battery_voltage_v")
    gps_sats = t.get("gps_satellites")
    gps_fix = t.get("gps_fix_type")
    gps_hdop = t.get("gps_hdop")
    alt_msl = t.get("altitude_msl_m")
    alt_rel = t.get("relative_altitude_m")
    ground_speed = t.get("ground_speed_mps")
    rx_kbps = t.get("rx_rate_kbps")
    tx_kbps = t.get("tx_rate_kbps")
    pkt_lost = t.get("packets_lost")
    pkt_recv = t.get("packets_received")
    pkt_loss_pct = t.get("packet_loss_pct")

    def _card(key: str, label: str, value: str, sub: str, tone: str = "default") -> dict[str, Any]:
        return {
            "key": key,
            "label": label,
            "value": value,
            "sub": sub,
            "tone": tone,
            "empty": value == DASH,
        }

    # 1. Flight mode + SYSID
    mode_val = str(flight_mode) if flight_mode is not None else DASH
    sysid_sub = f"SYSID {sysid}" if sysid is not None else ""

    # 2. Armed (preserve False -> "未解锁", True -> "已解锁", None -> "—")
    if armed is None:
        armed_val = DASH
    else:
        armed_val = "已解锁" if bool(armed) else "未解锁"

    # 3. Battery % (preserve 0 -> "0%")
    if batt_pct is None:
        batt_val = DASH
        batt_tone = "default"
    else:
        pct_num = float(batt_pct)
        batt_val = f"{round(pct_num)}%"
        batt_tone = "bad" if pct_num < 15 else ("warn" if pct_num < 30 else "default")

    # 4. Battery Voltage (preserve 0.0 -> "0.0 V")
    if batt_v is None:
        volt_val = DASH
        volt_sub = DASH
    else:
        v_num = float(batt_v)
        volt_val = f"{v_num:.1f} V"
        volt_sub = f"{v_num / 6.0:.2f} V / cell"

    # 5. GPS Satellites (preserve 0 -> "0")
    if gps_sats is None:
        sats_val = DASH
        sats_tone = "default"
    else:
        sats_int = int(gps_sats)
        sats_val = str(sats_int)
        sats_tone = "warn" if sats_int < 10 else "default"

    # 6. GPS Fix + HDOP
    fix_val = str(gps_fix) if gps_fix is not None else DASH
    hdop_sub = f"HDOP {float(gps_hdop):.2f}" if gps_hdop is not None else DASH

    # 7. Altitude MSL (preserve 0.0 -> "0.0 m")
    alt_msl_val = f"{float(alt_msl):.1f} m" if alt_msl is not None else DASH

    # 8. Relative Altitude (preserve 0.0 -> "0.0 m")
    alt_rel_val = f"{float(alt_rel):.1f} m" if alt_rel is not None else DASH

    # 9. Ground Speed + km/h (preserve 0.0 -> "0.0 m/s", "0.0 km/h")
    if ground_speed is None:
        gs_val = DASH
        gs_sub = DASH
    else:
        gs_num = float(ground_speed)
        gs_val = f"{gs_num:.1f} m/s"
        gs_sub = f"{gs_num * 3.6:.1f} km/h"

    # 10. RX rate KB/s (preserve 0.0 -> "0.00 KB/s")
    rx_val = f"{float(rx_kbps):.2f} KB/s" if rx_kbps is not None else DASH

    # 11. TX rate KB/s (preserve 0.0 -> "0.00 KB/s")
    tx_val = f"{float(tx_kbps):.2f} KB/s" if tx_kbps is not None else DASH

    # 12. Packets lost / received + loss %
    if pkt_lost is None and pkt_recv is None:
        pkt_val = DASH
        pkt_sub = DASH
        pkt_tone = "default"
    else:
        l_str = str(int(pkt_lost)) if pkt_lost is not None else DASH
        r_str = str(int(pkt_recv)) if pkt_recv is not None else DASH
        pkt_val = f"{l_str} / {r_str}"
        if pkt_loss_pct is not None:
            loss_num = float(pkt_loss_pct)
            pkt_sub = f"丢包率 {loss_num:.1f}%"
            pkt_tone = "warn" if loss_num > 2.0 else "default"
        else:
            pkt_sub = DASH
            pkt_tone = "default"

    return [
        _card("flight_mode", "飞行模式", mode_val, sysid_sub),
        _card("armed", "解锁状态", armed_val, ""),
        _card("battery_remaining_pct", "电量", batt_val, "", batt_tone),
        _card("battery_voltage_v", "电池电压", volt_val, volt_sub),
        _card("gps_satellites", "GPS 卫星数", sats_val, "", sats_tone),
        _card("gps_fix_type", "GPS 定位类型", fix_val, hdop_sub),
        _card("altitude_msl_m", "海拔", alt_msl_val, "MSL 高度"),
        _card("relative_altitude_m", "相对高度", alt_rel_val, "相对起飞点"),
        _card("ground_speed_mps", "地速", gs_val, gs_sub),
        _card("rx_rate_kbps", "飞控接收速率", rx_val, "从 DTU 到 ECS"),
        _card("tx_rate_kbps", "地面站发送速率", tx_val, "从 ECS 到地面站"),
        _card("packets", "丢包 / 收包", pkt_val, pkt_sub, pkt_tone),
    ]


def format_service_cards(group: dict[str, Any]) -> list[dict[str, Any]]:
    """Build 3 independent service summaries with state, observed_at, and stale kept separate."""
    router = group.get("router") or {}
    mav = group.get("mavproxy") or {}
    sg = group.get("security_group") or {}

    r_state = str(router.get("state") or "stopped")
    r_label, r_tone = router_status_meta(r_state)
    r_stale = bool(router.get("stale", False))
    r_obs = format_local_time(router.get("observed_at"))
    if r_state == "running":
        pid = router.get("pid")
        up = format_uptime(router.get("uptime_seconds"))
        r_meta = f"PID {pid if pid is not None else DASH}，{up}"
    elif router.get("detail"):
        r_meta = str(router["detail"])
    else:
        r_meta = r_label

    m_state = str(mav.get("state") or "disconnected")
    m_label, m_tone = mavproxy_status_meta(m_state)
    m_stale = bool(mav.get("stale", False))
    m_obs = format_local_time(mav.get("observed_at"))
    if m_state == "connected":
        up = format_uptime(mav.get("uptime_seconds"))
        peer = group.get("gcs_peer") or "会话观测中"
        m_meta = f"{up}，{peer}"
    elif mav.get("detail"):
        m_meta = str(mav["detail"])
    else:
        m_meta = m_label

    s_state = str(sg.get("state") or "unconfigured")
    s_label, s_tone = sg_status_meta(s_state)
    s_stale = bool(sg.get("stale", False))
    s_obs = format_local_time(sg.get("observed_at"))
    owned = sg.get("owned_rule_count")
    s_meta = f"{owned if owned is not None else 0} 条入方向规则"
    if sg.get("detail"):
        s_meta = f"{s_meta} · {sg['detail']}"

    return [
        {
            "key": "router",
            "title": "Router",
            "state": r_state,
            "stateLabel": r_label,
            "tone": r_tone,
            "meta": r_meta,
            "observedAt": r_obs,
            "stale": r_stale,
        },
        {
            "key": "mavproxy",
            "title": "MAVProxy 会话",
            "state": m_state,
            "stateLabel": m_label,
            "tone": m_tone,
            "meta": m_meta,
            "observedAt": m_obs,
            "stale": m_stale,
        },
        {
            "key": "security_group",
            "title": "安全组",
            "state": s_state,
            "stateLabel": s_label,
            "tone": s_tone,
            "meta": s_meta,
            "observedAt": s_obs,
            "stale": s_stale,
        },
    ]
