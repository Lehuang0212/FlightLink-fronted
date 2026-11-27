"""GUI-thread QAbstractListModel implementations for incremental UI updates without focus/scroll loss."""

from __future__ import annotations

from collections import deque
from typing import Any

from PySide6.QtCore import Property, QAbstractListModel, QModelIndex, QObject, Qt, Signal, Slot

from flightlink_desktop.models.formatters import (
    DASH,
    format_local_time,
    lifecycle_status_meta,
    mavproxy_status_meta,
    router_status_meta,
    sg_status_meta,
)


class GroupListModel(QAbstractListModel):
    """Port groups list model updating rows in-place by group_id so polling never steals focus."""

    countChanged = Signal()

    GroupIdRole = Qt.ItemDataRole.UserRole + 1
    NameRole = Qt.ItemDataRole.UserRole + 2
    DtuPortRole = Qt.ItemDataRole.UserRole + 3
    GcsProtocolRole = Qt.ItemDataRole.UserRole + 4
    GcsPortRole = Qt.ItemDataRole.UserRole + 5
    LifecycleStateRole = Qt.ItemDataRole.UserRole + 6
    LifecycleLabelRole = Qt.ItemDataRole.UserRole + 7
    LifecycleToneRole = Qt.ItemDataRole.UserRole + 8
    FcStateRole = Qt.ItemDataRole.UserRole + 9
    GcsStateRole = Qt.ItemDataRole.UserRole + 10
    DtuPeerRole = Qt.ItemDataRole.UserRole + 11
    GcsPeerRole = Qt.ItemDataRole.UserRole + 12
    SysidTextRole = Qt.ItemDataRole.UserRole + 13
    LinkQualityTextRole = Qt.ItemDataRole.UserRole + 14
    RttTextRole = Qt.ItemDataRole.UserRole + 15
    RouterLabelRole = Qt.ItemDataRole.UserRole + 16
    RouterToneRole = Qt.ItemDataRole.UserRole + 17
    RouterStaleRole = Qt.ItemDataRole.UserRole + 18
    MavproxyLabelRole = Qt.ItemDataRole.UserRole + 19
    MavproxyToneRole = Qt.ItemDataRole.UserRole + 20
    MavproxyStaleRole = Qt.ItemDataRole.UserRole + 21
    SgLabelRole = Qt.ItemDataRole.UserRole + 22
    SgToneRole = Qt.ItemDataRole.UserRole + 23
    SgStaleRole = Qt.ItemDataRole.UserRole + 24
    ObservedAtRole = Qt.ItemDataRole.UserRole + 25
    StaleRole = Qt.ItemDataRole.UserRole + 26
    ConfigVersionRole = Qt.ItemDataRole.UserRole + 27
    ActiveOperationIdRole = Qt.ItemDataRole.UserRole + 28
    DesiredStateRole = Qt.ItemDataRole.UserRole + 29

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._items: list[dict[str, Any]] = []

    @Property(int, notify=countChanged)
    def count(self) -> int:
        return len(self._items)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._items)

    def roleNames(self) -> dict[int, bytes]:
        return {
            self.GroupIdRole: b"groupId",
            self.NameRole: b"name",
            self.DtuPortRole: b"dtuPort",
            self.GcsProtocolRole: b"gcsProtocol",
            self.GcsPortRole: b"gcsPort",
            self.LifecycleStateRole: b"lifecycleState",
            self.LifecycleLabelRole: b"lifecycleLabel",
            self.LifecycleToneRole: b"lifecycleTone",
            self.FcStateRole: b"fcState",
            self.GcsStateRole: b"gcsState",
            self.DtuPeerRole: b"dtuPeer",
            self.GcsPeerRole: b"gcsPeer",
            self.SysidTextRole: b"sysidText",
            self.LinkQualityTextRole: b"linkQualityText",
            self.RttTextRole: b"rttText",
            self.RouterLabelRole: b"routerLabel",
            self.RouterToneRole: b"routerTone",
            self.RouterStaleRole: b"routerStale",
            self.MavproxyLabelRole: b"mavproxyLabel",
            self.MavproxyToneRole: b"mavproxyTone",
            self.MavproxyStaleRole: b"mavproxyStale",
            self.SgLabelRole: b"sgLabel",
            self.SgToneRole: b"sgTone",
            self.SgStaleRole: b"sgStale",
            self.ObservedAtRole: b"observedAt",
            self.StaleRole: b"stale",
            self.ConfigVersionRole: b"configVersion",
            self.ActiveOperationIdRole: b"activeOperationId",
            self.DesiredStateRole: b"desiredState",
        }

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._items)):
            return None
        row = self._items[index.row()]
        key_map = {
            self.GroupIdRole: "group_id",
            self.NameRole: "name",
            self.DtuPortRole: "dtu_port",
            self.GcsProtocolRole: "gcs_protocol",
            self.GcsPortRole: "gcs_port",
            self.LifecycleStateRole: "lifecycle_state",
            self.LifecycleLabelRole: "lifecycle_label",
            self.LifecycleToneRole: "lifecycle_tone",
            self.FcStateRole: "fc_state",
            self.GcsStateRole: "gcs_state",
            self.DtuPeerRole: "dtu_peer",
            self.GcsPeerRole: "gcs_peer",
            self.SysidTextRole: "sysid_text",
            self.LinkQualityTextRole: "link_quality_text",
            self.RttTextRole: "rtt_text",
            self.RouterLabelRole: "router_label",
            self.RouterToneRole: "router_tone",
            self.RouterStaleRole: "router_stale",
            self.MavproxyLabelRole: "mavproxy_label",
            self.MavproxyToneRole: "mavproxy_tone",
            self.MavproxyStaleRole: "mavproxy_stale",
            self.SgLabelRole: "sg_label",
            self.SgToneRole: "sg_tone",
            self.SgStaleRole: "sg_stale",
            self.ObservedAtRole: "observed_at_local",
            self.StaleRole: "stale",
            self.ConfigVersionRole: "config_version",
            self.ActiveOperationIdRole: "active_operation_id",
            self.DesiredStateRole: "desired_state",
        }
        field = key_map.get(role)
        return row.get(field) if field else None

    @staticmethod
    def _normalize(raw: dict[str, Any]) -> dict[str, Any]:
        lc_label, lc_tone = lifecycle_status_meta(raw.get("lifecycle_state"))
        router = raw.get("router") or {}
        mav = raw.get("mavproxy") or {}
        sg = raw.get("security_group") or {}
        r_label, r_tone = router_status_meta(router.get("state"))
        m_label, m_tone = mavproxy_status_meta(mav.get("state"))
        s_label, s_tone = sg_status_meta(sg.get("state"))
        sysid = raw.get("sysid")
        lq = raw.get("link_quality_pct")
        rtt = raw.get("rtt_ms")
        return {
            "group_id": str(raw.get("group_id", "")),
            "name": str(raw.get("name", "")),
            "dtu_port": int(raw.get("dtu_port", 0)),
            "gcs_protocol": str(raw.get("gcs_protocol", "tcp")).upper(),
            "gcs_port": int(raw.get("gcs_port", 0)),
            "lifecycle_state": str(raw.get("lifecycle_state", "configured_stopped")),
            "lifecycle_label": lc_label,
            "lifecycle_tone": lc_tone,
            "desired_state": str(raw.get("desired_state", "stopped")),
            "fc_state": str(raw.get("fc_state", "offline")),
            "gcs_state": str(raw.get("gcs_state", "disconnected")),
            "dtu_peer": str(raw["dtu_peer"]) if raw.get("dtu_peer") else DASH,
            "gcs_peer": str(raw["gcs_peer"]) if raw.get("gcs_peer") else DASH,
            "sysid_text": f"SYSID {sysid}" if sysid is not None else "SYSID —",
            "link_quality_text": f"{int(lq)}%" if lq is not None else DASH,
            "rtt_text": f"{int(rtt)} ms" if rtt is not None else DASH,
            "router_label": r_label,
            "router_tone": r_tone,
            "router_stale": bool(router.get("stale", False)),
            "mavproxy_label": m_label,
            "mavproxy_tone": m_tone,
            "mavproxy_stale": bool(mav.get("stale", False)),
            "sg_label": s_label,
            "sg_tone": s_tone,
            "sg_stale": bool(sg.get("stale", False)),
            "observed_at_local": format_local_time(raw.get("observed_at")),
            "stale": bool(raw.get("stale", False)),
            "config_version": int(raw.get("config_version", 1)),
            "active_operation_id": str(raw["active_operation_id"]) if raw.get("active_operation_id") else "",
            "_raw": raw,
        }

    def sync_groups(self, raw_groups: list[dict[str, Any]]) -> None:
        normalized = [self._normalize(g) for g in raw_groups]
        old_ids = [item["group_id"] for item in self._items]
        new_ids = [item["group_id"] for item in normalized]

        if old_ids == new_ids:
            # In-place update preserves ListView delegates, focus, and scroll position
            for idx, new_item in enumerate(normalized):
                if self._items[idx] != new_item:
                    self._items[idx] = new_item
                    model_idx = self.index(idx, 0)
                    self.dataChanged.emit(model_idx, model_idx)
            return

        self.beginResetModel()
        self._items = normalized
        self.endResetModel()
        self.countChanged.emit()

    def clear(self) -> None:
        if not self._items:
            return
        self.beginResetModel()
        self._items = []
        self.endResetModel()
        self.countChanged.emit()

    def raw_items(self) -> list[dict[str, Any]]:
        return [item["_raw"] for item in self._items]


class LiveLogListModel(QAbstractListModel):
    """500-row incremental ring buffer model — appends and trims without full model reset."""

    countChanged = Signal()
    followChanged = Signal()
    unreadCountChanged = Signal()

    EventIdRole = Qt.ItemDataRole.UserRole + 1
    GroupIdRole = Qt.ItemDataRole.UserRole + 2
    GroupNameRole = Qt.ItemDataRole.UserRole + 3
    SourceRole = Qt.ItemDataRole.UserRole + 4
    SourceShortRole = Qt.ItemDataRole.UserRole + 5
    LevelRole = Qt.ItemDataRole.UserRole + 6
    TimestampRole = Qt.ItemDataRole.UserRole + 7
    TextRole = Qt.ItemDataRole.UserRole + 8

    MAX_ROWS = 500

    def __init__(self, parent: QObject | None = None, *, max_rows: int = 500) -> None:
        super().__init__(parent)
        self._max_rows = max(1, max_rows)
        self._rows: deque[dict[str, Any]] = deque()
        self._seen_ids: set[str] = set()
        self._follow: bool = True
        self._unread_count: int = 0
        self._cursor: str = ""
        self._cleared_floor_count: int = 0

    @Property(int, notify=countChanged)
    def count(self) -> int:
        return len(self._rows)

    @Property(bool, notify=followChanged)
    def follow(self) -> bool:
        return self._follow

    @Property(int, notify=unreadCountChanged)
    def unreadCount(self) -> int:
        return self._unread_count

    @property
    def cursor(self) -> str:
        return self._cursor

    @cursor.setter
    def cursor(self, value: str) -> None:
        self._cursor = value

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._rows)

    def roleNames(self) -> dict[int, bytes]:
        return {
            self.EventIdRole: b"eventId",
            self.GroupIdRole: b"groupId",
            self.GroupNameRole: b"groupName",
            self.SourceRole: b"source",
            self.SourceShortRole: b"sourceShort",
            self.LevelRole: b"level",
            self.TimestampRole: b"timestamp",
            self.TextRole: b"text",
        }

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None
        row = self._rows[index.row()]
        key_map = {
            self.EventIdRole: "event_id",
            self.GroupIdRole: "group_id",
            self.GroupNameRole: "group_name",
            self.SourceRole: "source",
            self.SourceShortRole: "source_short",
            self.LevelRole: "level",
            self.TimestampRole: "timestamp",
            self.TextRole: "text",
        }
        field = key_map.get(role)
        return row.get(field) if field else None

    @Slot(bool)
    def setFollow(self, enabled: bool) -> None:
        if self._follow == enabled:
            return
        self._follow = enabled
        self.followChanged.emit()
        if enabled and self._unread_count > 0:
            self._unread_count = 0
            self.unreadCountChanged.emit()

    @Slot()
    def toggleFollow(self) -> None:
        self.setFollow(not self._follow)

    @Slot()
    def clearLocalDisplay(self) -> None:
        """Local clear only moves display start; preserves server cursor and never calls backend."""
        if not self._rows:
            return
        count = len(self._rows)
        self.beginRemoveRows(QModelIndex(), 0, count - 1)
        self._rows.clear()
        self.endRemoveRows()
        self._cleared_floor_count += count
        if self._unread_count:
            self._unread_count = 0
            self.unreadCountChanged.emit()
        self.countChanged.emit()

    def reset_for_new_query(self) -> None:
        """Full reset used ONLY when user changes filters, switches group, or logs out."""
        self._cursor = ""
        self._seen_ids.clear()
        self._cleared_floor_count = 0
        if self._unread_count:
            self._unread_count = 0
            self.unreadCountChanged.emit()
        if not self._rows:
            return
        self.beginResetModel()
        self._rows.clear()
        self.endResetModel()
        self.countChanged.emit()

    def append_entries(self, raw_items: list[dict[str, Any]], group_name_map: dict[str, str] | None = None) -> int:
        """Incrementally append new entries and trim oldest beyond MAX_ROWS without resetting model."""
        if not raw_items:
            return 0
        names = group_name_map or {}
        fresh: list[dict[str, Any]] = []
        for item in raw_items:
            ev_id = str(item.get("event_id", ""))
            if ev_id and ev_id in self._seen_ids:
                continue
            if ev_id:
                self._seen_ids.add(ev_id)
            gid = str(item.get("group_id", ""))
            src = str(item.get("source", "router"))
            fresh.append(
                {
                    "event_id": ev_id,
                    "group_id": gid,
                    "group_name": names.get(gid, gid),
                    "source": src,
                    "source_short": "RT" if src == "router" else "MP",
                    "level": str(item.get("level", "INFO")).upper(),
                    "timestamp": format_local_time(item.get("ts"), with_ms=True),
                    "text": str(item.get("text", "")),
                }
            )
        if not fresh:
            return 0

        # If more than max_rows arrived in one batch, keep only the tail max_rows
        if len(fresh) > self._max_rows:
            fresh = fresh[-self._max_rows :]

        start_row = len(self._rows)
        end_row = start_row + len(fresh) - 1
        self.beginInsertRows(QModelIndex(), start_row, end_row)
        self._rows.extend(fresh)
        self.endInsertRows()

        overflow = len(self._rows) - self._max_rows
        if overflow > 0:
            self.beginRemoveRows(QModelIndex(), 0, overflow - 1)
            for _ in range(overflow):
                self._rows.popleft()
            self.endRemoveRows()

        # Cap seen_ids set so memory stays bounded during long sessions
        if len(self._seen_ids) > self._max_rows * 4:
            self._seen_ids = {r["event_id"] for r in self._rows if r["event_id"]}

        if not self._follow:
            self._unread_count += len(fresh)
            self.unreadCountChanged.emit()

        self.countChanged.emit()
        return len(fresh)


class ArchiveGroupListModel(QAbstractListModel):
    """Archive groups list model preserving deleted groups and empty active groups."""

    countChanged = Signal()

    GroupIdRole = Qt.ItemDataRole.UserRole + 1
    NameSnapshotRole = Qt.ItemDataRole.UserRole + 2
    DtuPortRole = Qt.ItemDataRole.UserRole + 3
    GcsProtocolRole = Qt.ItemDataRole.UserRole + 4
    GcsPortRole = Qt.ItemDataRole.UserRole + 5
    DeletedRole = Qt.ItemDataRole.UserRole + 6
    ActiveSessionCountRole = Qt.ItemDataRole.UserRole + 7
    SealedSessionCountRole = Qt.ItemDataRole.UserRole + 8
    LatestRangeRole = Qt.ItemDataRole.UserRole + 9
    LatestStatusRole = Qt.ItemDataRole.UserRole + 10

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._items: list[dict[str, Any]] = []

    @Property(int, notify=countChanged)
    def count(self) -> int:
        return len(self._items)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._items)

    def roleNames(self) -> dict[int, bytes]:
        return {
            self.GroupIdRole: b"groupId",
            self.NameSnapshotRole: b"nameSnapshot",
            self.DtuPortRole: b"dtuPort",
            self.GcsProtocolRole: b"gcsProtocol",
            self.GcsPortRole: b"gcsPort",
            self.DeletedRole: b"deleted",
            self.ActiveSessionCountRole: b"activeSessionCount",
            self.SealedSessionCountRole: b"sealedSessionCount",
            self.LatestRangeRole: b"latestRange",
            self.LatestStatusRole: b"latestStatus",
        }

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._items)):
            return None
        row = self._items[index.row()]
        key_map = {
            self.GroupIdRole: "group_id",
            self.NameSnapshotRole: "name_snapshot",
            self.DtuPortRole: "dtu_port_snapshot",
            self.GcsProtocolRole: "gcs_protocol_snapshot",
            self.GcsPortRole: "gcs_port_snapshot",
            self.DeletedRole: "deleted",
            self.ActiveSessionCountRole: "active_session_count",
            self.SealedSessionCountRole: "sealed_session_count",
            self.LatestRangeRole: "latest_range",
            self.LatestStatusRole: "latest_status",
        }
        field = key_map.get(role)
        return row.get(field) if field else None

    def set_items(self, raw_items: list[dict[str, Any]]) -> None:
        normalized: list[dict[str, Any]] = []
        for item in raw_items:
            latest = item.get("latest_session")
            if isinstance(latest, dict):
                start_s = format_local_time(latest.get("first_observed_at"), with_date=True)
                end_s = format_local_time(latest.get("ended_at"), with_date=True) if latest.get("ended_at") else DASH
                latest_range = f"{start_s} 至 {end_s}"
                status_val = str(latest.get("status", ""))
                latest_status = "进行中" if status_val == "active" else ("封存中" if status_val == "sealing" else "已封存")
            else:
                latest_range = DASH
                latest_status = DASH

            normalized.append(
                {
                    "group_id": str(item.get("group_id", "")),
                    "name_snapshot": str(item.get("name_snapshot", "")),
                    "dtu_port_snapshot": int(item.get("dtu_port_snapshot", 0)),
                    "gcs_protocol_snapshot": str(item.get("gcs_protocol_snapshot", "tcp")).upper(),
                    "gcs_port_snapshot": int(item.get("gcs_port_snapshot", 0)),
                    "deleted": bool(item.get("deleted", False)),
                    "active_session_count": int(item.get("active_session_count", 0)),
                    "sealed_session_count": int(item.get("sealed_session_count", 0)),
                    "latest_range": latest_range,
                    "latest_status": latest_status,
                }
            )
        self.beginResetModel()
        self._items = normalized
        self.endResetModel()
        self.countChanged.emit()

    def clear(self) -> None:
        if not self._items:
            return
        self.beginResetModel()
        self._items = []
        self.endResetModel()
        self.countChanged.emit()


class ArchiveSessionListModel(QAbstractListModel):
    """Archive sessions model preserving expanded slice state and displaying local save status."""

    countChanged = Signal()

    SessionIdRole = Qt.ItemDataRole.UserRole + 1
    GroupIdRole = Qt.ItemDataRole.UserRole + 2
    StatusRole = Qt.ItemDataRole.UserRole + 3
    StatusLabelRole = Qt.ItemDataRole.UserRole + 4
    CloseReasonRole = Qt.ItemDataRole.UserRole + 5
    TimeRangeRole = Qt.ItemDataRole.UserRole + 6
    ExpiresAtRole = Qt.ItemDataRole.UserRole + 7
    SysidTextRole = Qt.ItemDataRole.UserRole + 8
    HasGapsRole = Qt.ItemDataRole.UserRole + 9
    HasMissingSourcesRole = Qt.ItemDataRole.UserRole + 10
    ExpandedRole = Qt.ItemDataRole.UserRole + 11
    LocalStatusRole = Qt.ItemDataRole.UserRole + 12
    LocalStatusLabelRole = Qt.ItemDataRole.UserRole + 13
    LocalStatusToneRole = Qt.ItemDataRole.UserRole + 14
    LocalDetailRole = Qt.ItemDataRole.UserRole + 15
    ShowRetryRole = Qt.ItemDataRole.UserRole + 16
    ActiveSourceRole = Qt.ItemDataRole.UserRole + 17
    EntriesLoadingRole = Qt.ItemDataRole.UserRole + 18
    EntriesHasMoreRole = Qt.ItemDataRole.UserRole + 19
    EntriesTextRole = Qt.ItemDataRole.UserRole + 20
    EntriesCountRole = Qt.ItemDataRole.UserRole + 21

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._items: list[dict[str, Any]] = []
        self._expanded_ids: set[str] = set()
        self._local_states: dict[str, dict[str, Any]] = {}
        self._entries_cache: dict[tuple[str, str], dict[str, Any]] = {}
        self._active_source: dict[str, str] = {}

    @Property(int, notify=countChanged)
    def count(self) -> int:
        return len(self._items)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._items)

    def roleNames(self) -> dict[int, bytes]:
        return {
            self.SessionIdRole: b"sessionId",
            self.GroupIdRole: b"groupId",
            self.StatusRole: b"sessionStatus",
            self.StatusLabelRole: b"statusLabel",
            self.CloseReasonRole: b"closeReason",
            self.TimeRangeRole: b"timeRange",
            self.ExpiresAtRole: b"expiresAt",
            self.SysidTextRole: b"sysidText",
            self.HasGapsRole: b"hasGaps",
            self.HasMissingSourcesRole: b"hasMissingSources",
            self.ExpandedRole: b"expanded",
            self.LocalStatusRole: b"localStatus",
            self.LocalStatusLabelRole: b"localStatusLabel",
            self.LocalStatusToneRole: b"localStatusTone",
            self.LocalDetailRole: b"localDetail",
            self.ShowRetryRole: b"showRetryAction",
            self.ActiveSourceRole: b"activeSource",
            self.EntriesLoadingRole: b"entriesLoading",
            self.EntriesHasMoreRole: b"entriesHasMore",
            self.EntriesTextRole: b"entriesText",
            self.EntriesCountRole: b"entriesCount",
        }

    @staticmethod
    def _local_status_display(
        session_status: str,
        local_state: dict[str, Any] | None,
        has_missing_sources: bool,
    ) -> tuple[str, str, str, str, bool]:
        if session_status != "sealed":
            return ("in_progress", "会话进行中", "idle", "切片封存后将自动保存到本机文档目录", False)
        if not local_state:
            return ("pending", "等待本机自动保存", "idle", "", False)
        st = str(local_state.get("local_status", "pending"))
        msg = str(local_state.get("last_error_message") or "")
        show_retry = bool(local_state.get("show_retry_action", False))
        if st == "saved":
            return ("saved", "已自动保存", "ok", "", False)
        if st == "saved_with_source_gaps":
            return ("saved_with_source_gaps", "已保存（云端缺源）", "warn", msg or "云端缺少部分日志来源", False)
        if st == "failed":
            return ("failed", "本机保存失败", "bad", msg or "自动保存失败，请点击重新下载日志", show_retry)
        if st == "expired_on_server":
            return ("expired_on_server", "云端已过期", "warn", msg or "云端已超过 7 天保留期，已停止重试", False)
        if st == "downloading":
            return ("downloading", "正在自动保存…", "warn", "", False)
        if has_missing_sources:
            return ("pending", "等待保存（云端含缺源）", "warn", "", False)
        return ("pending", "等待本机自动保存", "idle", "", False)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._items)):
            return None
        row = self._items[index.row()]
        sid = row["session_id"]
        src = self._active_source.get(sid, "router")
        cache = self._entries_cache.get((sid, src), {})
        local_code, local_label, local_tone, local_detail, show_retry = self._local_status_display(
            row["status"], self._local_states.get(sid), row["has_missing_sources"]
        )

        if role == self.SessionIdRole:
            return sid
        if role == self.GroupIdRole:
            return row["group_id"]
        if role == self.StatusRole:
            return row["status"]
        if role == self.StatusLabelRole:
            return row["status_label"]
        if role == self.CloseReasonRole:
            return row["close_reason"]
        if role == self.TimeRangeRole:
            return row["time_range"]
        if role == self.ExpiresAtRole:
            return row["expires_at"]
        if role == self.SysidTextRole:
            return row["sysid_text"]
        if role == self.HasGapsRole:
            return row["has_gaps"]
        if role == self.HasMissingSourcesRole:
            return row["has_missing_sources"]
        if role == self.ExpandedRole:
            return sid in self._expanded_ids
        if role == self.LocalStatusRole:
            return local_code
        if role == self.LocalStatusLabelRole:
            return local_label
        if role == self.LocalStatusToneRole:
            return local_tone
        if role == self.LocalDetailRole:
            return local_detail
        if role == self.ShowRetryRole:
            return show_retry
        if role == self.ActiveSourceRole:
            return src
        if role == self.EntriesLoadingRole:
            return bool(cache.get("loading", False))
        if role == self.EntriesHasMoreRole:
            return bool(cache.get("has_more", False))
        if role == self.EntriesTextRole:
            return str(cache.get("rendered_text", ""))
        if role == self.EntriesCountRole:
            return int(cache.get("count", 0))
        return None

    def set_sessions(self, raw_sessions: list[dict[str, Any]], *, preserve_expanded: bool = True) -> None:
        if not preserve_expanded:
            self._expanded_ids.clear()
        normalized: list[dict[str, Any]] = []
        for s in raw_sessions:
            status_val = str(s.get("status", "sealed"))
            status_label = "进行中" if status_val == "active" else ("封存中" if status_val == "sealing" else "已封存")
            start_s = format_local_time(s.get("first_observed_at"), with_date=True)
            end_s = format_local_time(s.get("ended_at"), with_date=True) if s.get("ended_at") else DASH
            sysid = s.get("sysid")
            normalized.append(
                {
                    "session_id": str(s.get("session_id", "")),
                    "group_id": str(s.get("group_id", "")),
                    "status": status_val,
                    "status_label": status_label,
                    "close_reason": str(s.get("close_reason") or DASH),
                    "time_range": f"{start_s} 至 {end_s}",
                    "expires_at": format_local_time(s.get("expires_at"), with_date=True) if s.get("expires_at") else DASH,
                    "sysid_text": f"SYSID {sysid}" if sysid is not None else "SYSID —",
                    "has_gaps": bool(s.get("has_gaps", False)),
                    "has_missing_sources": bool(s.get("has_missing_sources", False)),
                }
            )
        self.beginResetModel()
        self._items = normalized
        self.endResetModel()
        self.countChanged.emit()

    def set_expanded(self, session_id: str, expanded: bool) -> None:
        if expanded:
            self._expanded_ids.add(session_id)
        else:
            self._expanded_ids.discard(session_id)
        self._emit_row_changed(session_id)

    def is_expanded(self, session_id: str) -> bool:
        return session_id in self._expanded_ids

    def set_active_source(self, session_id: str, source: str) -> None:
        self._active_source[session_id] = source
        self._emit_row_changed(session_id)

    def get_active_source(self, session_id: str) -> str:
        return self._active_source.get(session_id, "router")

    def get_entries_cursor(self, session_id: str, source: str) -> str:
        return str(self._entries_cache.get((session_id, source), {}).get("next_cursor") or "")

    def has_entries_loaded(self, session_id: str, source: str) -> bool:
        return bool(self._entries_cache.get((session_id, source), {}).get("loaded", False))

    def set_entries_loading(self, session_id: str, source: str, loading: bool) -> None:
        entry = self._entries_cache.setdefault((session_id, source), {"lines": [], "rendered_text": "", "count": 0})
        entry["loading"] = loading
        self._emit_row_changed(session_id)

    def append_entries_page(
        self,
        session_id: str,
        source: str,
        items: list[dict[str, Any]],
        *,
        next_cursor: str | None,
        has_more: bool,
        source_availability: str = "available",
        missing_reason: str | None = None,
    ) -> None:
        entry = self._entries_cache.setdefault((session_id, source), {"lines": [], "rendered_text": "", "count": 0})
        lines: list[str] = entry["lines"]
        for it in items:
            ts = format_local_time(it.get("ts"), with_ms=True)
            lvl = str(it.get("level", "INFO")).upper()
            txt = str(it.get("text", ""))
            lines.append(f"{ts}  {lvl:<5}  {txt}")
        if not lines:
            if source_availability in ("missing_on_server", "degraded_quota_exceeded"):
                reason = missing_reason or source_availability
                rendered = f"（云端缺少该来源日志：{reason}）"
            else:
                rendered = "（该来源暂无日志正文）"
        else:
            rendered = "\n".join(lines)
        entry["rendered_text"] = rendered
        entry["count"] = len(lines)
        entry["next_cursor"] = next_cursor or ""
        entry["has_more"] = has_more
        entry["loading"] = False
        entry["loaded"] = True
        self._emit_row_changed(session_id)

    def update_local_states(self, states_by_session: dict[str, dict[str, Any]]) -> None:
        self._local_states = dict(states_by_session)
        if self._items:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self._items) - 1, 0))

    def clear(self) -> None:
        self._expanded_ids.clear()
        self._entries_cache.clear()
        self._active_source.clear()
        if not self._items:
            return
        self.beginResetModel()
        self._items = []
        self.endResetModel()
        self.countChanged.emit()

    def _emit_row_changed(self, session_id: str) -> None:
        for idx, item in enumerate(self._items):
            if item["session_id"] == session_id:
                mi = self.index(idx, 0)
                self.dataChanged.emit(mi, mi)
                break
