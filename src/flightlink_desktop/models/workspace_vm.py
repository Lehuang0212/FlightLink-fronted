"""GUI-thread WorkspaceViewModel coordinating navigation, page-scoped polling, detail/logs/history, and 404->archive fallback."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from flightlink_desktop.api.auth import AuthCoordinator
from flightlink_desktop.api.client import FlightLinkApiClient
from flightlink_desktop.api.errors import ApiError, NetworkError, SessionInvalidatedError
from flightlink_desktop.models.formatters import (
    DASH,
    build_telemetry_cards,
    component_status_meta,
    format_bytes,
    format_local_time,
    format_service_cards,
    lifecycle_status_meta,
)
from flightlink_desktop.models.list_models import (
    ArchiveGroupListModel,
    ArchiveSessionListModel,
    GroupListModel,
    LiveLogListModel,
)
from flightlink_desktop.workers.task_runner import BackgroundTaskRunner


class WorkspaceViewModel(QObject):
    """Owns all page ViewModel state and non-overlapping page-scoped pollers on the GUI thread.

    Three independent switches enforced by design:
    1. Per-log-pane `follow` (pause scroll): affects only viewport auto-scroll.
    2. `liveUpdatesEnabled` (pause live updates): pauses page read polling (overview/groups/detail/logs)
       and link pulse animation; NEVER pauses background archive sync or operation tracking.
    3. Background archive & async operation tracking run independently.
    """

    routeChanged = Signal()
    liveUpdatesChanged = Signal()
    overviewChanged = Signal()
    groupsFilterChanged = Signal()
    detailChanged = Signal()
    logsFilterChanged = Signal()
    historyChanged = Signal()
    searchChanged = Signal()
    toastChanged = Signal()
    archiveStatusSummaryChanged = Signal()

    # Signal for P4 archive engine to wire manual retry cleanly
    manualArchiveRetryRequested = Signal(str)  # session_id

    def __init__(
        self,
        api_client: FlightLinkApiClient,
        auth: AuthCoordinator,
        task_runner: BackgroundTaskRunner,
        parent: QObject | None = None,
        *,
        overview_interval_ms: int = 2500,
        detail_interval_ms: int = 1500,
    ) -> None:
        super().__init__(parent)
        self._api = api_client
        self._auth = auth
        self._runner = task_runner

        self._active_epoch: int = 0
        self._authenticated: bool = False
        self._route: str = "overview"  # overview | groups | detail | logs | history | historyDetail
        self._active_group_id: str = ""
        self._history_group_id: str = ""
        self._highlight_slice_id: str = ""

        # Switch #2: Pause live updates (only affects UI read polling, NEVER archive/operations)
        self._live_updates_enabled: bool = True
        self._last_sync_text: str = "--:--:--"

        # Overview state
        self._overview_stale: bool = False
        self._overview_observed_at: str = DASH
        self._components: list[dict[str, Any]] = []
        self._components_ok_count: int = 0
        self._components_total_count: int = 3
        self._disk_status: str = "ok"
        self._disk_summary: str = DASH
        self._metrics: dict[str, Any] = {
            "group_count": 0,
            "max_groups": 5,
            "running_router_count": 0,
            "online_fc_count": 0,
            "needs_verification_count": 0,
        }

        # Groups state
        self._group_list_model = GroupListModel(self)
        self._overview_groups_model = GroupListModel(self)
        self._group_query: str = ""
        self._group_filter: str = "all"
        self._groups_total: int = 0
        self._max_groups: int = 5
        self._group_name_map: dict[str, str] = {}

        # Group Detail state
        self._detail_seq: int = 0
        self._detail_etag: str = ""
        self._detail_raw: dict[str, Any] = {}
        self._detail_name: str = ""
        self._detail_lifecycle_state: str = ""
        self._detail_lifecycle_label: str = ""
        self._detail_lifecycle_tone: str = "idle"
        self._detail_config_version: int = 1
        self._detail_dtu_port: int = 0
        self._detail_gcs_protocol: str = "tcp"
        self._detail_gcs_port: int = 0
        self._detail_dtu_peer: str = DASH
        self._detail_gcs_peer: str = DASH
        self._detail_fc_state: str = "offline"
        self._detail_gcs_state: str = "disconnected"
        self._detail_stale: bool = False
        self._detail_observed_at: str = DASH
        self._detail_services: list[dict[str, Any]] = []
        self._detail_telemetry: list[dict[str, Any]] = build_telemetry_cards(None, None)
        self._detail_telemetry_note: str = "暂无遥测"
        self._detail_commands: list[dict[str, Any]] = []
        self._detail_log_tab: str = "router"
        self._detail_router_logs = LiveLogListModel(self)
        self._detail_mavproxy_logs = LiveLogListModel(self)

        # Combined Live Logs state
        self._live_logs_model = LiveLogListModel(self)
        self._logs_group_filter: str = ""
        self._logs_source_filter: str = "all"
        self._logs_level_filter: str = "all"
        self._logs_query_filter: str = ""
        self._logs_seq: int = 0

        # History state
        self._archive_groups_model = ArchiveGroupListModel(self)
        self._archive_sessions_model = ArchiveSessionListModel(self)
        self._history_group_meta: dict[str, Any] = {}
        self._history_seq: int = 0

        # Global search
        self._global_search_query: str = ""
        self._global_search_results: list[dict[str, Any]] = []

        # Archive auto-save summary for statusbar & notice banner (populated by P4 worker)
        self._archive_local_root: str = ""
        self._archive_failed_count: int = 0
        self._archive_failed_group_id: str = ""
        self._archive_failed_session_id: str = ""
        self._archive_failed_message: str = ""
        self._archive_status_text: str = "自动归档就绪"
        self._archive_retention_gap_note: str = ""

        # Toast banner
        self._toast_message: str = ""
        self._toast_tone: str = "info"
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self.dismissToast)

        # In-flight non-overlapping guards
        self._in_flight: dict[str, bool] = {
            "overview": False,
            "groups": False,
            "detail": False,
            "detail_router_logs": False,
            "detail_mavproxy_logs": False,
            "live_logs": False,
        }

        # Page-scoped poll timers
        self._overview_timer = QTimer(self)
        self._overview_timer.setInterval(overview_interval_ms)
        self._overview_timer.timeout.connect(self.pollOverview)

        self._groups_timer = QTimer(self)
        self._groups_timer.setInterval(overview_interval_ms)
        self._groups_timer.timeout.connect(self.pollGroups)

        self._detail_timer = QTimer(self)
        self._detail_timer.setInterval(detail_interval_ms)
        self._detail_timer.timeout.connect(self._poll_detail_tick)

        self._logs_timer = QTimer(self)
        self._logs_timer.setInterval(detail_interval_ms)
        self._logs_timer.timeout.connect(self.pollLiveLogs)

    # ---- Session lifecycle hooks ----

    @Slot(int, str, str)
    def onSessionStarted(self, epoch: int, ecs_instance_id: str, server_url: str) -> None:
        self._active_epoch = epoch
        self._authenticated = True
        self._route = "overview"
        self._active_group_id = ""
        self._history_group_id = ""
        self._highlight_slice_id = ""
        self._live_updates_enabled = True
        self.routeChanged.emit()
        self.liveUpdatesChanged.emit()
        self._sync_poll_timers(immediate=True)

    @Slot(int, str)
    def onSessionEnded(self, new_epoch: int, reason: str) -> None:
        self._active_epoch = new_epoch
        self._authenticated = False
        self._stop_all_timers()
        for k in self._in_flight:
            self._in_flight[k] = False
        self._detail_seq += 1
        self._logs_seq += 1
        self._history_seq += 1
        self._components = []
        self._overview_groups_model.clear()
        self._group_list_model.clear()
        self._detail_router_logs.reset_for_new_query()
        self._detail_mavproxy_logs.reset_for_new_query()
        self._live_logs_model.reset_for_new_query()
        self._archive_groups_model.clear()
        self._archive_sessions_model.clear()
        self._detail_raw = {}
        self._detail_etag = ""
        self._detail_services = []
        self._detail_telemetry = build_telemetry_cards(None, None)
        self._detail_commands = []
        self._global_search_query = ""
        self._global_search_results = []
        self.overviewChanged.emit()
        self.detailChanged.emit()
        self.historyChanged.emit()
        self.searchChanged.emit()

    def stop_polling(self) -> None:
        self._stop_all_timers()

    # ---- Properties ----

    @Property(str, notify=routeChanged)
    def route(self) -> str:
        return self._route

    @Property(str, notify=routeChanged)
    def activeGroupId(self) -> str:
        return self._active_group_id

    @Property(str, notify=routeChanged)
    def historyGroupId(self) -> str:
        return self._history_group_id

    @Property(bool, notify=liveUpdatesChanged)
    def liveUpdatesEnabled(self) -> bool:
        return self._live_updates_enabled

    @Property(str, notify=liveUpdatesChanged)
    def lastSyncText(self) -> str:
        return self._last_sync_text

    @Property(bool, notify=overviewChanged)
    def overviewStale(self) -> bool:
        return self._overview_stale

    @Property(str, notify=overviewChanged)
    def overviewObservedAt(self) -> str:
        return self._overview_observed_at

    @Property("QVariantList", notify=overviewChanged)
    def components(self) -> list[dict[str, Any]]:
        return self._components

    @Property(int, notify=overviewChanged)
    def componentsOkCount(self) -> int:
        return self._components_ok_count

    @Property(int, notify=overviewChanged)
    def componentsTotalCount(self) -> int:
        return self._components_total_count

    @Property(str, notify=overviewChanged)
    def diskStatus(self) -> str:
        return self._disk_status

    @Property(str, notify=overviewChanged)
    def diskSummary(self) -> str:
        return self._disk_summary

    @Property("QVariantMap", notify=overviewChanged)
    def overviewMetrics(self) -> dict[str, Any]:
        return self._metrics

    @Property(QObject, constant=True)
    def overviewGroupsModel(self) -> GroupListModel:
        return self._overview_groups_model

    @Property(QObject, constant=True)
    def groupListModel(self) -> GroupListModel:
        return self._group_list_model

    @Property(str, notify=groupsFilterChanged)
    def groupQuery(self) -> str:
        return self._group_query

    @Property(str, notify=groupsFilterChanged)
    def groupFilter(self) -> str:
        return self._group_filter

    @Property(int, notify=groupsFilterChanged)
    def groupsTotal(self) -> int:
        return self._groups_total

    @Property(int, notify=groupsFilterChanged)
    def maxGroups(self) -> int:
        return self._max_groups

    @Property(bool, notify=groupsFilterChanged)
    def atGroupLimit(self) -> bool:
        return self._groups_total >= self._max_groups

    # Detail properties
    @Property(str, notify=detailChanged)
    def detailName(self) -> str:
        return self._detail_name

    @Property(str, notify=detailChanged)
    def detailLifecycleState(self) -> str:
        return self._detail_lifecycle_state

    @Property(str, notify=detailChanged)
    def detailLifecycleLabel(self) -> str:
        return self._detail_lifecycle_label

    @Property(str, notify=detailChanged)
    def detailLifecycleTone(self) -> str:
        return self._detail_lifecycle_tone

    @Property(int, notify=detailChanged)
    def detailConfigVersion(self) -> int:
        return self._detail_config_version

    @Property(str, notify=detailChanged)
    def detailEtag(self) -> str:
        return self._detail_etag

    @Property(int, notify=detailChanged)
    def detailDtuPort(self) -> int:
        return self._detail_dtu_port

    @Property(str, notify=detailChanged)
    def detailGcsProtocol(self) -> str:
        return self._detail_gcs_protocol

    @Property(int, notify=detailChanged)
    def detailGcsPort(self) -> int:
        return self._detail_gcs_port

    @Property(str, notify=detailChanged)
    def detailDtuPeer(self) -> str:
        return self._detail_dtu_peer

    @Property(str, notify=detailChanged)
    def detailGcsPeer(self) -> str:
        return self._detail_gcs_peer

    @Property(str, notify=detailChanged)
    def detailFcState(self) -> str:
        return self._detail_fc_state

    @Property(str, notify=detailChanged)
    def detailGcsState(self) -> str:
        return self._detail_gcs_state

    @Property(bool, notify=detailChanged)
    def detailStale(self) -> bool:
        return self._detail_stale

    @Property(str, notify=detailChanged)
    def detailObservedAt(self) -> str:
        return self._detail_observed_at

    @Property("QVariantList", notify=detailChanged)
    def detailServices(self) -> list[dict[str, Any]]:
        return self._detail_services

    @Property("QVariantList", notify=detailChanged)
    def detailTelemetryCards(self) -> list[dict[str, Any]]:
        return self._detail_telemetry

    @Property(str, notify=detailChanged)
    def detailTelemetryNote(self) -> str:
        return self._detail_telemetry_note

    @Property("QVariantList", notify=detailChanged)
    def detailGcsCommands(self) -> list[dict[str, Any]]:
        return self._detail_commands

    @Property(str, notify=detailChanged)
    def detailLogTab(self) -> str:
        return self._detail_log_tab

    @Property(QObject, constant=True)
    def detailRouterLogsModel(self) -> LiveLogListModel:
        return self._detail_router_logs

    @Property(QObject, constant=True)
    def detailMavproxyLogsModel(self) -> LiveLogListModel:
        return self._detail_mavproxy_logs

    # Live logs properties
    @Property(QObject, constant=True)
    def liveLogsModel(self) -> LiveLogListModel:
        return self._live_logs_model

    @Property(str, notify=logsFilterChanged)
    def logsGroupFilter(self) -> str:
        return self._logs_group_filter

    @Property(str, notify=logsFilterChanged)
    def logsSourceFilter(self) -> str:
        return self._logs_source_filter

    @Property(str, notify=logsFilterChanged)
    def logsLevelFilter(self) -> str:
        return self._logs_level_filter

    @Property(str, notify=logsFilterChanged)
    def logsQueryFilter(self) -> str:
        return self._logs_query_filter

    # History properties
    @Property(QObject, constant=True)
    def archiveGroupsModel(self) -> ArchiveGroupListModel:
        return self._archive_groups_model

    @Property(QObject, constant=True)
    def archiveSessionsModel(self) -> ArchiveSessionListModel:
        return self._archive_sessions_model

    @Property("QVariantMap", notify=historyChanged)
    def historyGroupMeta(self) -> dict[str, Any]:
        return self._history_group_meta

    # Global search properties
    @Property(str, notify=searchChanged)
    def globalSearchQuery(self) -> str:
        return self._global_search_query

    @Property("QVariantList", notify=searchChanged)
    def globalSearchResults(self) -> list[dict[str, Any]]:
        return self._global_search_results

    # Archive auto-save summary properties
    @Property(str, notify=archiveStatusSummaryChanged)
    def archiveLocalRoot(self) -> str:
        return self._archive_local_root

    @Property(int, notify=archiveStatusSummaryChanged)
    def archiveFailedCount(self) -> int:
        return self._archive_failed_count

    @Property(str, notify=archiveStatusSummaryChanged)
    def archiveFailedGroupId(self) -> str:
        return self._archive_failed_group_id

    @Property(str, notify=archiveStatusSummaryChanged)
    def archiveFailedSessionId(self) -> str:
        return self._archive_failed_session_id

    @Property(str, notify=archiveStatusSummaryChanged)
    def archiveFailedMessage(self) -> str:
        return self._archive_failed_message

    @Property(str, notify=archiveStatusSummaryChanged)
    def archiveStatusText(self) -> str:
        return self._archive_status_text

    @Property(str, notify=archiveStatusSummaryChanged)
    def archiveRetentionGapNote(self) -> str:
        return self._archive_retention_gap_note

    # Toast properties
    @Property(str, notify=toastChanged)
    def toastMessage(self) -> str:
        return self._toast_message

    @Property(str, notify=toastChanged)
    def toastTone(self) -> str:
        return self._toast_tone

    @Property(bool, notify=toastChanged)
    def toastVisible(self) -> bool:
        return bool(self._toast_message)

    # ---- Navigation & UI control slots ----

    @Slot(str)
    def navigate(self, target: str) -> None:
        if target not in ("overview", "groups", "logs", "history"):
            return
        changed = self._route != target
        self._route = target
        if changed:
            self.routeChanged.emit()
        self._sync_poll_timers(immediate=True)
        if target == "history":
            self.loadArchiveGroups()

    @Slot(str)
    def openGroupDetail(self, group_id: str) -> None:
        if not group_id:
            return
        if self._active_group_id != group_id:
            self._active_group_id = group_id
            self._detail_seq += 1
            self._detail_etag = ""
            self._detail_raw = {}
            self._detail_router_logs.reset_for_new_query()
            self._detail_mavproxy_logs.reset_for_new_query()
        self._route = "detail"
        self.routeChanged.emit()
        self._sync_poll_timers(immediate=True)

    @Slot(str, str)
    def openHistoryGroup(self, group_id: str, highlight_slice_id: str = "") -> None:
        if not group_id:
            return
        self._history_group_id = group_id
        self._highlight_slice_id = highlight_slice_id
        self._route = "historyDetail"
        self.routeChanged.emit()
        self._sync_poll_timers(immediate=False)
        self.loadArchiveGroupDetail(group_id, highlight_slice_id)

    @Slot()
    def toggleLiveUpdates(self) -> None:
        self._live_updates_enabled = not self._live_updates_enabled
        self.liveUpdatesChanged.emit()
        self._sync_poll_timers(immediate=self._live_updates_enabled)

    @Slot(str)
    def setDetailLogTab(self, source: str) -> None:
        if source in ("router", "mavproxy") and source != self._detail_log_tab:
            self._detail_log_tab = source
            self.detailChanged.emit()

    @Slot(str, str)
    def setGroupsFilter(self, query: str, filter_mode: str) -> None:
        clean_filter = filter_mode if filter_mode in ("all", "online", "idle", "attention") else "all"
        if query == self._group_query and clean_filter == self._group_filter:
            return
        self._group_query = query
        self._group_filter = clean_filter
        self.groupsFilterChanged.emit()
        self.pollGroups()

    @Slot(str, str, str, str)
    def setLiveLogsFilter(self, group_id: str, source: str, level: str, query: str) -> None:
        clean_src = source if source in ("all", "router", "mavproxy") else "all"
        clean_lvl = level if level in ("all", "DEBUG", "INFO", "WARN", "ERROR") else "all"
        if (
            group_id == self._logs_group_filter
            and clean_src == self._logs_source_filter
            and clean_lvl == self._logs_level_filter
            and query == self._logs_query_filter
        ):
            return
        self._logs_group_filter = group_id
        self._logs_source_filter = clean_src
        self._logs_level_filter = clean_lvl
        self._logs_query_filter = query
        self._logs_seq += 1
        self._live_logs_model.reset_for_new_query()
        self.logsFilterChanged.emit()
        self.pollLiveLogs()

    @Slot(str)
    def setGlobalSearchQuery(self, query: str) -> None:
        self._global_search_query = query
        needle = query.strip().lower()
        if not needle:
            self._global_search_results = []
        else:
            results: list[dict[str, Any]] = []
            for raw in self._overview_groups_model.raw_items() or self._group_list_model.raw_items():
                name = str(raw.get("name", ""))
                dtu = str(raw.get("dtu_port", ""))
                gcs = str(raw.get("gcs_port", ""))
                gid = str(raw.get("group_id", ""))
                if needle in name.lower() or needle in dtu or needle in gcs or needle in gid.lower():
                    results.append(
                        {
                            "kind": "group",
                            "groupId": gid,
                            "title": name,
                            "subtitle": f"UDP {dtu} / {str(raw.get('gcs_protocol', 'tcp')).upper()} {gcs}",
                        }
                    )
            results.append({"kind": "logs", "query": query.strip(), "title": f"在实时日志中搜索 “{query.strip()}”", "subtitle": "跳转日志页"})
            self._global_search_results = results[:8]
        self.searchChanged.emit()

    @Slot()
    def clearGlobalSearch(self) -> None:
        if self._global_search_query or self._global_search_results:
            self._global_search_query = ""
            self._global_search_results = []
            self.searchChanged.emit()

    @Slot(str, str)
    def showToast(self, message: str, tone: str = "info") -> None:
        self._toast_message = message
        self._toast_tone = tone
        self.toastChanged.emit()
        self._toast_timer.start(4000)

    @Slot()
    def dismissToast(self) -> None:
        if self._toast_message:
            self._toast_message = ""
            self.toastChanged.emit()

    @Slot(str)
    def toggleHistorySlice(self, session_id: str) -> None:
        currently = self._archive_sessions_model.is_expanded(session_id)
        next_state = not currently
        self._archive_sessions_model.set_expanded(session_id, next_state)
        if next_state:
            src = self._archive_sessions_model.get_active_source(session_id)
            if not self._archive_sessions_model.has_entries_loaded(session_id, src):
                self.loadSliceEntries(session_id, src, reset=False)

    @Slot(str, str)
    def selectHistorySliceSource(self, session_id: str, source: str) -> None:
        if source not in ("router", "mavproxy"):
            return
        self._archive_sessions_model.set_active_source(session_id, source)
        if not self._archive_sessions_model.has_entries_loaded(session_id, source):
            self.loadSliceEntries(session_id, source, reset=False)

    @Slot(str)
    def loadMoreSliceEntries(self, session_id: str) -> None:
        src = self._archive_sessions_model.get_active_source(session_id)
        self.loadSliceEntries(session_id, src, reset=False)

    @Slot(str)
    def requestManualArchiveRetry(self, session_id: str) -> None:
        if session_id:
            self.manualArchiveRetryRequested.emit(session_id)

    # ---- Archive auto-save status integration (fed by P4 engine) ----

    def update_archive_summary(
        self,
        *,
        local_root: str,
        failed_count: int,
        failed_group_id: str,
        failed_session_id: str,
        failed_message: str,
        status_text: str,
        retention_gap_note: str,
        session_states: dict[str, dict[str, Any]],
    ) -> None:
        self._archive_local_root = local_root
        self._archive_failed_count = failed_count
        self._archive_failed_group_id = failed_group_id
        self._archive_failed_session_id = failed_session_id
        self._archive_failed_message = failed_message
        self._archive_status_text = status_text
        self._archive_retention_gap_note = retention_gap_note
        self._archive_sessions_model.update_local_states(session_states)
        self.archiveStatusSummaryChanged.emit()

    # ---- Page-scoped polling scheduler ----

    def _stop_all_timers(self) -> None:
        self._overview_timer.stop()
        self._groups_timer.stop()
        self._detail_timer.stop()
        self._logs_timer.stop()

    def _sync_poll_timers(self, *, immediate: bool) -> None:
        self._stop_all_timers()
        if not self._authenticated:
            return
        if not self._live_updates_enabled:
            return

        if self._route == "overview":
            self._overview_timer.start()
            if immediate:
                self.pollOverview()
        elif self._route == "groups":
            self._groups_timer.start()
            if immediate:
                self.pollGroups()
        elif self._route == "detail" and self._active_group_id:
            self._detail_timer.start()
            if immediate:
                self._poll_detail_tick()
        elif self._route == "logs":
            self._logs_timer.start()
            if immediate:
                self.pollLiveLogs()

    def _mark_synced(self) -> None:
        self._last_sync_text = datetime.now().strftime("%H:%M:%S")
        self.liveUpdatesChanged.emit()

    # ---- Polling implementations (strictly non-overlapping & epoch-checked) ----

    @Slot()
    def pollOverview(self) -> None:
        if not self._authenticated or self._in_flight["overview"]:
            return
        epoch = self._active_epoch
        self._in_flight["overview"] = True

        def _work() -> dict[str, Any]:
            return self._api.get_overview(expected_epoch=epoch)

        def _done(data: dict[str, Any] | None, err: Exception | None) -> None:
            self._in_flight["overview"] = False
            if epoch != self._active_epoch or err is not None or not isinstance(data, dict):
                return
            self._apply_overview(data)
            self._mark_synced()

        self._runner.submit(_work, _done)

    def _apply_overview(self, data: dict[str, Any]) -> None:
        self._overview_stale = bool(data.get("stale", False))
        self._overview_observed_at = format_local_time(data.get("observed_at"))
        comps: list[dict[str, Any]] = []
        ok_count = 0
        for c in data.get("components") or []:
            st = str(c.get("status", "unknown"))
            lbl, tone = component_status_meta(st)
            if st == "ok" and not c.get("stale"):
                ok_count += 1
            comps.append(
                {
                    "name": str(c.get("name", "")),
                    "status": st,
                    "statusLabel": lbl,
                    "tone": tone,
                    "observedAt": format_local_time(c.get("observed_at")),
                    "stale": bool(c.get("stale", False)),
                    "detail": str(c.get("detail") or ""),
                }
            )
        self._components = comps
        self._components_ok_count = ok_count
        self._components_total_count = len(comps) if comps else 3

        disk = data.get("disk") or {}
        self._disk_status = str(disk.get("status", "ok"))
        used = format_bytes(disk.get("archive_used_bytes"))
        free = format_bytes(disk.get("free_bytes"))
        total = format_bytes(disk.get("total_bytes"))
        self._disk_summary = f"归档已用 {used} · 剩余 {free} / 共 {total}"

        metrics = data.get("metrics") or {}
        self._metrics = {
            "group_count": int(metrics.get("group_count", 0)),
            "max_groups": int(metrics.get("max_groups", 5)),
            "running_router_count": int(metrics.get("running_router_count", 0)),
            "online_fc_count": int(metrics.get("online_fc_count", 0)),
            "needs_verification_count": int(metrics.get("needs_verification_count", 0)),
        }
        groups = list(data.get("groups") or [])
        self._overview_groups_model.sync_groups(groups)
        self._groups_total = int(self._metrics["group_count"])
        self._max_groups = int(self._metrics["max_groups"])
        for g in groups:
            if g.get("group_id"):
                self._group_name_map[str(g["group_id"])] = str(g.get("name", g["group_id"]))
        self.overviewChanged.emit()
        self.groupsFilterChanged.emit()

    @Slot()
    def pollGroups(self) -> None:
        if not self._authenticated or self._in_flight["groups"]:
            return
        epoch = self._active_epoch
        q = self._group_query
        flt = self._group_filter
        self._in_flight["groups"] = True

        def _work() -> dict[str, Any]:
            return self._api.list_groups(q=q, filter_mode=flt, expected_epoch=epoch)

        def _done(data: dict[str, Any] | None, err: Exception | None) -> None:
            self._in_flight["groups"] = False
            if epoch != self._active_epoch or err is not None or not isinstance(data, dict):
                return
            if q != self._group_query or flt != self._group_filter:
                return
            items = list(data.get("items") or [])
            self._group_list_model.sync_groups(items)
            self._groups_total = int(data.get("total", len(items)))
            self._max_groups = int(data.get("max_groups", 5))
            for g in items:
                if g.get("group_id"):
                    self._group_name_map[str(g["group_id"])] = str(g.get("name", g["group_id"]))
            self.groupsFilterChanged.emit()
            self._mark_synced()

        self._runner.submit(_work, _done)

    def _poll_detail_tick(self) -> None:
        self.pollGroupDetail()
        self._poll_detail_log("router")
        self._poll_detail_log("mavproxy")

    @Slot()
    def pollGroupDetail(self) -> None:
        gid = self._active_group_id
        if not self._authenticated or not gid or self._in_flight["detail"]:
            return
        epoch = self._active_epoch
        seq = self._detail_seq
        self._in_flight["detail"] = True

        def _work() -> tuple[str, Any, str | None]:
            try:
                res = self._api.get_group(gid, expected_epoch=epoch)
                return ("ok", res.data, res.etag)
            except ApiError as exc:
                if exc.status_code == 404 and exc.code == "GROUP_NOT_FOUND":
                    # Contract: check GET /archive/groups/{id}; redirect ONLY if 200
                    try:
                        arch = self._api.get_archive_group(gid, expected_epoch=epoch)
                        return ("deleted_archived", arch, None)
                    except (ApiError, NetworkError):
                        return ("not_found", exc, None)
                raise

        def _done(result: tuple[str, Any, str | None] | None, err: Exception | None) -> None:
            self._in_flight["detail"] = False
            if epoch != self._active_epoch or seq != self._detail_seq or gid != self._active_group_id:
                return
            if err is not None or result is None:
                return
            status, payload, etag = result
            if status == "deleted_archived":
                self.showToast("端口组已删除，历史归档仍可查看", "info")
                self.openHistoryGroup(gid)
                return
            if status == "not_found":
                self.showToast("未找到该端口组及其归档记录", "warn")
                self.navigate("groups")
                return
            if isinstance(payload, dict):
                self._apply_group_detail(payload, etag)
                self._mark_synced()

        self._runner.submit(_work, _done)

    def _apply_group_detail(self, data: dict[str, Any], etag: str | None) -> None:
        self._detail_raw = data
        self._detail_etag = etag or f'"v{data.get("config_version", 1)}"'
        self._detail_name = str(data.get("name", ""))
        lc_state = str(data.get("lifecycle_state", "configured_stopped"))
        lc_label, lc_tone = lifecycle_status_meta(lc_state)
        self._detail_lifecycle_state = lc_state
        self._detail_lifecycle_label = lc_label
        self._detail_lifecycle_tone = lc_tone
        self._detail_config_version = int(data.get("config_version", 1))
        self._detail_dtu_port = int(data.get("dtu_port", 0))
        self._detail_gcs_protocol = str(data.get("gcs_protocol", "tcp"))
        self._detail_gcs_port = int(data.get("gcs_port", 0))
        self._detail_dtu_peer = str(data["dtu_peer"]) if data.get("dtu_peer") else DASH
        self._detail_gcs_peer = str(data["gcs_peer"]) if data.get("gcs_peer") else DASH
        self._detail_fc_state = str(data.get("fc_state", "offline"))
        self._detail_gcs_state = str(data.get("gcs_state", "disconnected"))
        self._detail_stale = bool(data.get("stale", False))
        self._detail_observed_at = format_local_time(data.get("observed_at"))
        self._detail_services = format_service_cards(data)

        telemetry = data.get("telemetry") if isinstance(data.get("telemetry"), dict) else None
        self._detail_telemetry = build_telemetry_cards(telemetry, data.get("sysid"))
        if telemetry and telemetry.get("observed_at"):
            stale_suffix = "（观测已过期）" if telemetry.get("stale") else ""
            self._detail_telemetry_note = f"观测于 {format_local_time(telemetry.get('observed_at'))}{stale_suffix}"
        else:
            self._detail_telemetry_note = "暂无遥测"

        cmds: list[dict[str, Any]] = []
        for c in data.get("recent_gcs_commands") or []:
            st = str(c.get("status", "UNKNOWN"))
            tone = "ok" if st == "ACCEPTED" else ("bad" if st in ("DENIED", "FAILED") else "warn")
            cmds.append(
                {
                    "id": str(c.get("id", "")),
                    "command": str(c.get("command", "")),
                    "detail": str(c.get("detail") or ""),
                    "status": st,
                    "tone": tone,
                    "sourceLabel": str(c.get("source_label") or ""),
                    "observedAt": format_local_time(c.get("observed_at")),
                }
            )
        self._detail_commands = cmds
        self.detailChanged.emit()

    def _poll_detail_log(self, source: str) -> None:
        gid = self._active_group_id
        flight_key = f"detail_{source}_logs"
        if not self._authenticated or not gid or self._in_flight[flight_key]:
            return
        model = self._detail_router_logs if source == "router" else self._detail_mavproxy_logs
        epoch = self._active_epoch
        seq = self._detail_seq
        cursor = model.cursor
        self._in_flight[flight_key] = True

        def _work() -> dict[str, Any]:
            return self._api.query_live_logs(
                group_id=gid,
                source=source,
                cursor=cursor,
                limit=100,
                expected_epoch=epoch,
            )

        def _done(data: dict[str, Any] | None, err: Exception | None) -> None:
            self._in_flight[flight_key] = False
            if epoch != self._active_epoch or seq != self._detail_seq or gid != self._active_group_id:
                return
            if isinstance(err, ApiError) and err.status_code == 410 and err.code == "CURSOR_EXPIRED":
                model.cursor = ""
                return
            if err is not None or not isinstance(data, dict):
                return
            if data.get("next_cursor") is not None:
                model.cursor = str(data["next_cursor"])
            model.append_entries(list(data.get("items") or []), self._group_name_map)

        self._runner.submit(_work, _done)

    @Slot()
    def pollLiveLogs(self) -> None:
        if not self._authenticated or self._in_flight["live_logs"]:
            return
        epoch = self._active_epoch
        seq = self._logs_seq
        gid = self._logs_group_filter
        src = self._logs_source_filter
        lvl = self._logs_level_filter
        q = self._logs_query_filter
        cursor = self._live_logs_model.cursor
        self._in_flight["live_logs"] = True

        def _work() -> dict[str, Any]:
            return self._api.query_live_logs(
                group_id=gid,
                source=src,
                level=lvl,
                q=q,
                cursor=cursor,
                limit=100,
                expected_epoch=epoch,
            )

        def _done(data: dict[str, Any] | None, err: Exception | None) -> None:
            self._in_flight["live_logs"] = False
            if epoch != self._active_epoch or seq != self._logs_seq:
                return
            if isinstance(err, ApiError) and err.status_code == 410 and err.code == "CURSOR_EXPIRED":
                self._live_logs_model.cursor = ""
                self.showToast("实时日志游标已过期，已重置为最新窗口", "warn")
                return
            if err is not None or not isinstance(data, dict):
                return
            if data.get("next_cursor") is not None:
                self._live_logs_model.cursor = str(data["next_cursor"])
            self._live_logs_model.append_entries(list(data.get("items") or []), self._group_name_map)
            self._mark_synced()

        self._runner.submit(_work, _done)

    # ---- History metadata + lazy /entries pagination ----

    @Slot()
    def loadArchiveGroups(self) -> None:
        if not self._authenticated:
            return
        epoch = self._active_epoch

        def _work() -> dict[str, Any]:
            return self._api.list_archive_groups(include_deleted=True, expected_epoch=epoch)

        def _done(data: dict[str, Any] | None, err: Exception | None) -> None:
            if epoch != self._active_epoch or err is not None or not isinstance(data, dict):
                return
            self._archive_groups_model.set_items(list(data.get("items") or []))
            self.historyChanged.emit()

        self._runner.submit(_work, _done)

    def loadArchiveGroupDetail(self, group_id: str, highlight_slice_id: str = "") -> None:
        if not self._authenticated or not group_id:
            return
        epoch = self._active_epoch
        self._history_seq += 1
        seq = self._history_seq

        def _work() -> tuple[dict[str, Any], dict[str, Any]]:
            meta = self._api.get_archive_group(group_id, expected_epoch=epoch)
            sessions = self._api.list_archive_group_sessions(group_id, limit=30, expected_epoch=epoch)
            return meta, sessions

        def _done(res: tuple[dict[str, Any], dict[str, Any]] | None, err: Exception | None) -> None:
            if epoch != self._active_epoch or seq != self._history_seq:
                return
            if err is not None or res is None:
                return
            meta, sessions = res
            self._history_group_meta = {
                "groupId": str(meta.get("group_id", group_id)),
                "nameSnapshot": str(meta.get("name_snapshot", group_id)),
                "dtuPort": int(meta.get("dtu_port_snapshot", 0)),
                "gcsProtocol": str(meta.get("gcs_protocol_snapshot", "tcp")).upper(),
                "gcsPort": int(meta.get("gcs_port_snapshot", 0)),
                "deleted": bool(meta.get("deleted", False)),
                "deletedAt": format_local_time(meta.get("deleted_at"), with_date=True) if meta.get("deleted_at") else "",
                "sealedCount": int(meta.get("sealed_session_count", 0)),
                "activeCount": int(meta.get("active_session_count", 0)),
            }
            self._archive_sessions_model.set_sessions(list(sessions.get("items") or []), preserve_expanded=True)
            if highlight_slice_id:
                self._archive_sessions_model.set_expanded(highlight_slice_id, True)
                src = self._archive_sessions_model.get_active_source(highlight_slice_id)
                if not self._archive_sessions_model.has_entries_loaded(highlight_slice_id, src):
                    self.loadSliceEntries(highlight_slice_id, src, reset=False)
            self.historyChanged.emit()

        self._runner.submit(_work, _done)

    def loadSliceEntries(self, session_id: str, source: str, *, reset: bool = False) -> None:
        if not self._authenticated or not session_id:
            return
        epoch = self._active_epoch
        cursor = "" if reset else self._archive_sessions_model.get_entries_cursor(session_id, source)
        self._archive_sessions_model.set_entries_loading(session_id, source, True)

        def _work() -> dict[str, Any]:
            return self._api.get_archive_session_entries(
                session_id,
                source=source,
                cursor=cursor,
                limit=200,
                expected_epoch=epoch,
            )

        def _done(data: dict[str, Any] | None, err: Exception | None) -> None:
            if epoch != self._active_epoch:
                return
            if err is not None or not isinstance(data, dict):
                self._archive_sessions_model.set_entries_loading(session_id, source, False)
                if isinstance(err, ApiError) and err.status_code == 410:
                    self.showToast("该云端归档切片已超过 7 天保留期", "warn")
                return
            self._archive_sessions_model.append_entries_page(
                session_id,
                source,
                list(data.get("items") or []),
                next_cursor=data.get("next_cursor"),
                has_more=bool(data.get("has_more", False)),
                source_availability=str(data.get("source_availability", "available")),
                missing_reason=data.get("missing_reason"),
            )

        self._runner.submit(_work, _done)
