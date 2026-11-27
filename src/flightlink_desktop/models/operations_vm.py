"""GUI-thread OperationsViewModel handling Create/Edit/Delete/Actions, dry-run, 202 tracking, 409/412/422, and retry."""

from __future__ import annotations

import time
from typing import Any, Callable

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from flightlink_desktop.api.auth import AuthCoordinator
from flightlink_desktop.api.client import ApiResponse, FlightLinkApiClient
from flightlink_desktop.api.errors import ApiError, NetworkError, SessionInvalidatedError
from flightlink_desktop.models.workspace_vm import WorkspaceViewModel
from flightlink_desktop.workers.operation_tracker import IntentKeyManager, TrackedOperation
from flightlink_desktop.workers.task_runner import BackgroundTaskRunner

ACTION_LABELS = {
    "create": "新建端口组",
    "update": "更新端口组配置",
    "delete": "删除端口组",
    "start": "启动 Router",
    "stop": "停止 Router",
    "restart": "重启 Router",
    "sync_security_group": "同步安全组",
    "sync-security-group": "同步安全组",
    "verify": "核验通道状态",
}

STATUS_LABELS = {
    "pending": "已受理，排队中（尚未生效）",
    "running": "执行中（尚未完成）",
    "succeeded": "操作已完成",
    "failed": "操作失败",
    "needs_verification": "待人工核实（已停止自动轮询）",
    "cancelled": "已取消",
}


class OperationsViewModel(QObject):
    """Manages async write operations & dialogs independently of UI live-update pause switch."""

    dialogChanged = Signal()
    deleteDialogChanged = Signal()
    operationChanged = Signal()
    operationCompleted = Signal(str, str, str)  # operation_id, action, status

    def __init__(
        self,
        api_client: FlightLinkApiClient,
        auth: AuthCoordinator,
        task_runner: BackgroundTaskRunner,
        workspace_vm: WorkspaceViewModel,
        parent: QObject | None = None,
        *,
        clock: Callable[[], float] | None = None,
        key_manager: IntentKeyManager | None = None,
    ) -> None:
        super().__init__(parent)
        self._api = api_client
        self._auth = auth
        self._runner = task_runner
        self._workspace = workspace_vm
        self._clock = clock or time.monotonic
        self._keys = key_manager or IntentKeyManager()

        self._active_epoch: int = 0

        # Create / Edit dialog state
        self._dialog_open: bool = False
        self._dialog_mode: str = "create"  # create | edit
        self._dialog_group_id: str = ""
        self._dialog_etag: str = ""
        self._dialog_config_version: int = 1
        self._initial_draft: dict[str, Any] = {"name": "", "dtu_port": "", "gcs_protocol": "tcp", "gcs_port": ""}
        self._draft_name: str = ""
        self._draft_dtu_port: str = ""
        self._draft_gcs_protocol: str = "tcp"
        self._draft_gcs_port: str = ""
        self._submitting: bool = False
        self._dry_running: bool = False
        self._form_error: str = ""
        self._field_errors: dict[str, str] = {}
        self._dry_run_summary: str = ""
        self._version_reloaded_notice: str = ""
        self._confirm_discard_open: bool = False

        # Delete confirmation dialog state
        self._delete_dialog_open: bool = False
        self._delete_group_id: str = ""
        self._delete_group_name: str = ""
        self._delete_etag: str = ""
        self._delete_submitting: bool = False
        self._delete_error: str = ""

        # Active tracked 202 operation (survives page navigation and live-update pause!)
        self._active_op: TrackedOperation | None = None
        self._op_poll_in_flight: bool = False
        self._action_submitting: bool = False
        self._op_timer = QTimer(self)
        self._op_timer.setSingleShot(True)
        self._op_timer.timeout.connect(self._poll_active_operation)

    @Slot(int, str, str)
    def onSessionStarted(self, epoch: int, ecs_instance_id: str, server_url: str) -> None:
        self._active_epoch = epoch
        self._keys.clear_all()

    @Slot(int, str)
    def onSessionEnded(self, new_epoch: int, reason: str) -> None:
        self._active_epoch = new_epoch
        self._op_timer.stop()
        self._op_poll_in_flight = False
        self._active_op = None
        self._dialog_open = False
        self._delete_dialog_open = False
        self._submitting = False
        self._delete_submitting = False
        self._action_submitting = False
        self._keys.clear_all()
        self.dialogChanged.emit()
        self.deleteDialogChanged.emit()
        self.operationChanged.emit()

    def stop_tracking(self) -> None:
        self._op_timer.stop()

    # ---- Create / Edit Dialog Properties ----

    @Property(bool, notify=dialogChanged)
    def dialogOpen(self) -> bool:
        return self._dialog_open

    @Property(str, notify=dialogChanged)
    def dialogMode(self) -> str:
        return self._dialog_mode

    @Property(str, notify=dialogChanged)
    def draftName(self) -> str:
        return self._draft_name

    @Property(str, notify=dialogChanged)
    def draftDtuPort(self) -> str:
        return self._draft_dtu_port

    @Property(str, notify=dialogChanged)
    def draftGcsProtocol(self) -> str:
        return self._draft_gcs_protocol

    @Property(str, notify=dialogChanged)
    def draftGcsPort(self) -> str:
        return self._draft_gcs_port

    @Property(int, notify=dialogChanged)
    def dialogConfigVersion(self) -> int:
        return self._dialog_config_version

    @Property(bool, notify=dialogChanged)
    def isDraftDirty(self) -> bool:
        return (
            self._draft_name != self._initial_draft["name"]
            or self._draft_dtu_port != self._initial_draft["dtu_port"]
            or self._draft_gcs_protocol != self._initial_draft["gcs_protocol"]
            or self._draft_gcs_port != self._initial_draft["gcs_port"]
        )

    @Property(bool, notify=dialogChanged)
    def submitting(self) -> bool:
        return self._submitting

    @Property(bool, notify=dialogChanged)
    def dryRunning(self) -> bool:
        return self._dry_running

    @Property(str, notify=dialogChanged)
    def formError(self) -> str:
        return self._form_error

    @Property("QVariantMap", notify=dialogChanged)
    def fieldErrors(self) -> dict[str, str]:
        return self._field_errors

    @Property(str, notify=dialogChanged)
    def dryRunSummary(self) -> str:
        return self._dry_run_summary

    @Property(str, notify=dialogChanged)
    def versionReloadedNotice(self) -> str:
        return self._version_reloaded_notice

    @Property(bool, notify=dialogChanged)
    def confirmDiscardOpen(self) -> bool:
        return self._confirm_discard_open

    # ---- Delete Dialog Properties ----

    @Property(bool, notify=deleteDialogChanged)
    def deleteDialogOpen(self) -> bool:
        return self._delete_dialog_open

    @Property(str, notify=deleteDialogChanged)
    def deleteGroupName(self) -> str:
        return self._delete_group_name

    @Property(bool, notify=deleteDialogChanged)
    def deleteSubmitting(self) -> bool:
        return self._delete_submitting

    @Property(str, notify=deleteDialogChanged)
    def deleteError(self) -> str:
        return self._delete_error

    # ---- Active Operation Tracker Properties ----

    @Property(bool, notify=operationChanged)
    def hasActiveOperation(self) -> bool:
        return self._active_op is not None

    @Property(str, notify=operationChanged)
    def activeOperationId(self) -> str:
        return self._active_op.operation_id if self._active_op else ""

    @Property(str, notify=operationChanged)
    def activeStatus(self) -> str:
        return self._active_op.status if self._active_op else ""

    @Property(bool, notify=operationChanged)
    def activeIsTerminal(self) -> bool:
        return bool(self._active_op and self._active_op.is_terminal)

    @Property(bool, notify=operationChanged)
    def canRetryActive(self) -> bool:
        return bool(
            self._active_op
            and self._active_op.status in ("failed", "needs_verification")
            and self._active_op.retryable
            and self._auth.snapshot().is_admin
        )

    @Property(str, notify=operationChanged)
    def activeSummaryText(self) -> str:
        if not self._active_op:
            return ""
        op = self._active_op
        act_lbl = ACTION_LABELS.get(op.action, op.action)
        st_lbl = STATUS_LABELS.get(op.status, op.status)
        base = f"{act_lbl}（{op.operation_id}）：{st_lbl}"
        if op.network_interrupted:
            base += " · 网络暂时中断，正在恢复查询原操作（不会重复创建）"
        elif op.error_message:
            base += f" · {op.error_message}"
        return base

    @Property(str, notify=operationChanged)
    def activeStepsText(self) -> str:
        if not self._active_op:
            return ""
        op = self._active_op
        parts: list[str] = []
        for s in op.steps:
            name = str(s.get("step_name", ""))
            st = str(s.get("status", ""))
            det = str(s.get("error_message") or s.get("detail") or "")
            parts.append(f"[{st}] {name}" + (f" ({det})" if det else ""))
        text = " → ".join(parts)
        if op.retry_hint:
            text = (text + "\n" if text else "") + f"核验建议：{op.retry_hint}"
        return text

    # ---- Dialog Slots ----

    @Slot()
    def openCreateDialog(self) -> None:
        if not self._auth.snapshot().is_admin:
            self._workspace.showToast("当前账号仅只读权限，无法新建端口组", "warn")
            return
        self._dialog_mode = "create"
        self._dialog_group_id = ""
        self._dialog_etag = ""
        self._dialog_config_version = 1
        self._initial_draft = {"name": "", "dtu_port": "", "gcs_protocol": "tcp", "gcs_port": ""}
        self._draft_name = ""
        self._draft_dtu_port = ""
        self._draft_gcs_protocol = "tcp"
        self._draft_gcs_port = ""
        self._form_error = ""
        self._field_errors = {}
        self._dry_run_summary = ""
        self._version_reloaded_notice = ""
        self._confirm_discard_open = False
        self._submitting = False
        self._dry_running = False
        self._dialog_open = True
        self._keys.clear("create_group")
        self.dialogChanged.emit()

    @Slot(str)
    def openEditDialog(self, group_id: str) -> None:
        if not self._auth.snapshot().is_admin:
            self._workspace.showToast("当前账号仅只读权限，无法编辑端口组", "warn")
            return
        if not group_id:
            return
        epoch = self._active_epoch
        self._dialog_mode = "edit"
        self._dialog_group_id = group_id
        self._form_error = ""
        self._field_errors = {}
        self._dry_run_summary = ""
        self._version_reloaded_notice = ""
        self._confirm_discard_open = False
        self._submitting = False
        self._dry_running = False
        self._keys.clear(f"update_group:{group_id}")

        # Seed from detail if matching, then fetch authoritative ETag + latest config_version
        if group_id == self._workspace.activeGroupId and self._workspace.detailName:
            self._apply_edit_source(
                name=self._workspace.detailName,
                dtu_port=self._workspace.detailDtuPort,
                gcs_protocol=self._workspace.detailGcsProtocol,
                gcs_port=self._workspace.detailGcsPort,
                config_version=self._workspace.detailConfigVersion,
                etag=self._workspace.detailEtag,
            )
            self._dialog_open = True
            self.dialogChanged.emit()
        else:
            self._dialog_open = True
            self.dialogChanged.emit()

        def _work() -> ApiResponse:
            return self._api.get_group(group_id, expected_epoch=epoch)

        def _done(res: ApiResponse | None, err: Exception | None) -> None:
            if epoch != self._active_epoch or not self._dialog_open or self._dialog_group_id != group_id:
                return
            if err is not None or res is None or not isinstance(res.data, dict):
                self._form_error = self._format_error(err)
                self.dialogChanged.emit()
                return
            d = res.data
            # Only overwrite draft if user hasn't started editing yet
            if not self.isDraftDirty:
                self._apply_edit_source(
                    name=str(d.get("name", "")),
                    dtu_port=int(d.get("dtu_port", 0)),
                    gcs_protocol=str(d.get("gcs_protocol", "tcp")),
                    gcs_port=int(d.get("gcs_port", 0)),
                    config_version=int(d.get("config_version", 1)),
                    etag=res.etag or f'"v{d.get("config_version", 1)}"',
                )
            else:
                self._dialog_config_version = int(d.get("config_version", self._dialog_config_version))
                self._dialog_etag = res.etag or f'"v{self._dialog_config_version}"'
            self.dialogChanged.emit()

        self._runner.submit(_work, _done)

    def _apply_edit_source(
        self,
        *,
        name: str,
        dtu_port: int,
        gcs_protocol: str,
        gcs_port: int,
        config_version: int,
        etag: str,
    ) -> None:
        self._dialog_config_version = config_version
        self._dialog_etag = etag or f'"v{config_version}"'
        self._initial_draft = {
            "name": name,
            "dtu_port": str(dtu_port),
            "gcs_protocol": gcs_protocol.lower(),
            "gcs_port": str(gcs_port),
        }
        self._draft_name = self._initial_draft["name"]
        self._draft_dtu_port = self._initial_draft["dtu_port"]
        self._draft_gcs_protocol = self._initial_draft["gcs_protocol"]
        self._draft_gcs_port = self._initial_draft["gcs_port"]

    @Slot(str, str, str, str)
    def updateDraft(self, name: str, dtu_port: str, gcs_protocol: str, gcs_port: str) -> None:
        self._draft_name = name
        self._draft_dtu_port = dtu_port
        self._draft_gcs_protocol = gcs_protocol.lower() if gcs_protocol.lower() in ("tcp", "udp") else "tcp"
        self._draft_gcs_port = gcs_port
        self._dry_run_summary = ""
        self.dialogChanged.emit()

    @Slot()
    def requestCloseDialog(self) -> None:
        if self._submitting:
            return
        if self.isDraftDirty and not self._confirm_discard_open:
            self._confirm_discard_open = True
            self.dialogChanged.emit()
            return
        self.forceCloseDialog()

    @Slot()
    def cancelDiscardConfirmation(self) -> None:
        self._confirm_discard_open = False
        self.dialogChanged.emit()

    @Slot()
    def forceCloseDialog(self) -> None:
        self._dialog_open = False
        self._confirm_discard_open = False
        self._form_error = ""
        self._field_errors = {}
        self._dry_run_summary = ""
        self._version_reloaded_notice = ""
        self.dialogChanged.emit()

    def _validate_draft(self) -> tuple[dict[str, Any] | None, dict[str, str]]:
        errors: dict[str, str] = {}
        clean_name = self._draft_name.strip()
        if not clean_name:
            errors["name"] = "请输入端口组名称。"
        elif len(clean_name) > 24:
            errors["name"] = "名称不能超过 24 个字符。"

        dtu_val: int | None = None
        try:
            dtu_val = int(self._draft_dtu_port.strip())
            if not (1 <= dtu_val <= 65535):
                errors["dtu_port"] = "DTU 端口必须在 1–65535 之间。"
        except ValueError:
            errors["dtu_port"] = "请输入有效的整数端口号。"

        gcs_val: int | None = None
        try:
            gcs_val = int(self._draft_gcs_port.strip())
            if not (1 <= gcs_val <= 65535):
                errors["gcs_port"] = "GCS 端口必须在 1–65535 之间。"
        except ValueError:
            errors["gcs_port"] = "请输入有效的整数端口号。"

        if dtu_val is not None and gcs_val is not None and dtu_val == gcs_val:
            errors["gcs_port"] = "GCS 端口不能与 DTU 端口相同。"

        if self._draft_gcs_protocol not in ("tcp", "udp"):
            errors["gcs_protocol"] = "GCS 协议仅支持 TCP 或 UDP。"

        if errors:
            return None, errors

        payload: dict[str, Any] = {
            "name": clean_name,
            "dtu_port": dtu_val,
            "gcs_protocol": self._draft_gcs_protocol,
            "gcs_port": gcs_val,
        }
        return payload, {}

    @Slot()
    def runEditDryRun(self) -> None:
        """PATCH /api/v1/groups/{id}?dry_run=true -> 200 preview ONLY (never marks applied)."""
        if self._dialog_mode != "edit" or self._dry_running or self._submitting:
            return
        payload, field_errs = self._validate_draft()
        if payload is None:
            self._field_errors = field_errs
            self._form_error = "请先修正表单中的校验错误。"
            self.dialogChanged.emit()
            return

        payload["expected_config_version"] = self._dialog_config_version
        gid = self._dialog_group_id
        etag = self._dialog_etag
        epoch = self._active_epoch

        self._dry_running = True
        self._form_error = ""
        self._field_errors = {}
        self._dry_run_summary = ""
        self.dialogChanged.emit()

        def _work() -> ApiResponse:
            return self._api.update_group(
                gid,
                payload,
                dry_run=True,
                if_match=etag,
                expected_epoch=epoch,
            )

        def _done(res: ApiResponse | None, err: Exception | None) -> None:
            if epoch != self._active_epoch:
                return
            self._dry_running = False
            if err is not None or res is None:
                self._handle_write_error(err, group_id_for_412=gid)
                self.dialogChanged.emit()
                return
            data = res.data if isinstance(res.data, dict) else {}
            restart = "需要短暂重启本组 Router" if data.get("requires_restart") else "无需重启 Router"
            sg = "需要同步云安全组" if data.get("requires_sg_sync") else "无需改动安全组"
            steps = ", ".join(str(s) for s in (data.get("planned_steps") or []))
            self._dry_run_summary = f"预演结果（未执行，HTTP 200）：{restart}；{sg}" + (f"；计划步骤：{steps}" if steps else "")
            self.dialogChanged.emit()

        self._runner.submit(_work, _done)

    @Slot()
    def submitDialog(self) -> None:
        """Formal POST /groups or PATCH /groups/{id} returning 202 Accepted (never marks applied)."""
        if self._submitting:
            return
        payload, field_errs = self._validate_draft()
        if payload is None:
            self._field_errors = field_errs
            self._form_error = "请先修正表单中的校验错误。"
            self.dialogChanged.emit()
            return

        epoch = self._active_epoch
        mode = self._dialog_mode
        gid = self._dialog_group_id
        etag = self._dialog_etag

        if mode == "create":
            scope = "create_group"
            idem_key = self._keys.key_for(scope, payload)
        else:
            payload["expected_config_version"] = self._dialog_config_version
            scope = f"update_group:{gid}"
            idem_key = self._keys.key_for(scope, payload)

        self._submitting = True
        self._form_error = ""
        self._field_errors = {}
        self.dialogChanged.emit()

        def _work() -> ApiResponse:
            if mode == "create":
                return self._api.create_group(payload, idempotency_key=idem_key, expected_epoch=epoch)
            return self._api.update_group(
                gid,
                payload,
                dry_run=False,
                if_match=etag,
                idempotency_key=idem_key,
                expected_epoch=epoch,
            )

        def _done(res: ApiResponse | None, err: Exception | None) -> None:
            if epoch != self._active_epoch:
                return
            self._submitting = False
            if err is not None or res is None:
                # On NetworkError (timeout / lost response), KEEP idem_key so user retry reuses exact same key!
                if not isinstance(err, NetworkError):
                    self._keys.clear(scope)
                self._handle_write_error(err, group_id_for_412=gid if mode == "edit" else "")
                self.dialogChanged.emit()
                return

            self._keys.clear(scope)
            self._dialog_open = False
            self._confirm_discard_open = False
            self._version_reloaded_notice = ""
            self.dialogChanged.emit()
            self._accept_202_response(res, epoch=epoch)

        self._runner.submit(_work, _done)

    # ---- Delete Dialog Slots ----

    @Slot(str, str)
    def openDeleteDialog(self, group_id: str, group_name: str) -> None:
        if not self._auth.snapshot().is_admin:
            self._workspace.showToast("当前账号仅只读权限，无法删除端口组", "warn")
            return
        self._delete_group_id = group_id
        self._delete_group_name = group_name
        self._delete_etag = self._workspace.detailEtag if group_id == self._workspace.activeGroupId else ""
        self._delete_error = ""
        self._delete_submitting = False
        self._delete_dialog_open = True
        self._keys.clear(f"delete_group:{group_id}")
        self.deleteDialogChanged.emit()

        # Fetch fresh ETag if not already on detail page
        if not self._delete_etag:
            epoch = self._active_epoch

            def _work() -> ApiResponse:
                return self._api.get_group(group_id, expected_epoch=epoch)

            def _done(res: ApiResponse | None, err: Exception | None) -> None:
                if epoch == self._active_epoch and self._delete_dialog_open and self._delete_group_id == group_id and res is not None:
                    self._delete_etag = res.etag or f'"v{res.data.get("config_version", 1)}"'

            self._runner.submit(_work, _done)

    @Slot()
    def closeDeleteDialog(self) -> None:
        if self._delete_submitting:
            return
        self._delete_dialog_open = False
        self._delete_error = ""
        self.deleteDialogChanged.emit()

    @Slot()
    def confirmDeleteGroup(self) -> None:
        if self._delete_submitting or not self._delete_group_id:
            return
        gid = self._delete_group_id
        etag = self._delete_etag or None
        epoch = self._active_epoch
        scope = f"delete_group:{gid}"
        idem_key = self._keys.key_for(scope, {"group_id": gid, "if_match": etag})

        self._delete_submitting = True
        self._delete_error = ""
        self.deleteDialogChanged.emit()

        def _work() -> ApiResponse:
            return self._api.delete_group(gid, if_match=etag, idempotency_key=idem_key, expected_epoch=epoch)

        def _done(res: ApiResponse | None, err: Exception | None) -> None:
            if epoch != self._active_epoch:
                return
            self._delete_submitting = False
            if err is not None or res is None:
                if not isinstance(err, NetworkError):
                    self._keys.clear(scope)
                if isinstance(err, ApiError) and err.status_code == 412:
                    self._reload_delete_etag(gid, epoch)
                    self._delete_error = "配置版本已变化（412），已刷新最新版本，请再次确认删除。"
                else:
                    self._delete_error = self._format_error(err)
                self.deleteDialogChanged.emit()
                return

            self._keys.clear(scope)
            self._delete_dialog_open = False
            self.deleteDialogChanged.emit()
            self._accept_202_response(res, epoch=epoch)

        self._runner.submit(_work, _done)

    def _reload_delete_etag(self, group_id: str, epoch: int) -> None:
        def _work() -> ApiResponse:
            return self._api.get_group(group_id, expected_epoch=epoch)

        def _done(res: ApiResponse | None, err: Exception | None) -> None:
            if epoch == self._active_epoch and self._delete_dialog_open and res is not None:
                self._delete_etag = res.etag or f'"v{res.data.get("config_version", 1)}"'

        self._runner.submit(_work, _done)

    # ---- Lifecycle Action & Operation Retry Slots ----

    @Slot(str, str)
    def triggerGroupAction(self, group_id: str, action: str) -> None:
        if self._action_submitting or not group_id:
            return
        if not self._auth.snapshot().is_admin:
            self._workspace.showToast("当前账号仅只读权限，无法执行通道操作", "warn")
            return
        epoch = self._active_epoch
        scope = f"action:{group_id}:{action}"
        idem_key = self._keys.key_for(scope, {"group_id": group_id, "action": action})
        self._action_submitting = True

        def _work() -> ApiResponse:
            return self._api.trigger_group_action(group_id, action, idempotency_key=idem_key, expected_epoch=epoch)

        def _done(res: ApiResponse | None, err: Exception | None) -> None:
            if epoch != self._active_epoch:
                return
            self._action_submitting = False
            if err is not None or res is None:
                if not isinstance(err, NetworkError):
                    self._keys.clear(scope)
                self._workspace.showToast(self._format_error(err), "bad")
                return
            self._keys.clear(scope)
            self._accept_202_response(res, epoch=epoch)

        self._runner.submit(_work, _done)

    @Slot()
    def retryActiveOperation(self) -> None:
        if not self._active_op or not self.canRetryActive or self._action_submitting:
            return
        op_id = self._active_op.operation_id
        epoch = self._active_epoch
        scope = f"retry_op:{op_id}"
        idem_key = self._keys.key_for(scope, {"operation_id": op_id})
        self._action_submitting = True

        def _work() -> ApiResponse:
            return self._api.retry_operation(op_id, idempotency_key=idem_key, expected_epoch=epoch)

        def _done(res: ApiResponse | None, err: Exception | None) -> None:
            if epoch != self._active_epoch:
                return
            self._action_submitting = False
            if err is not None or res is None:
                if not isinstance(err, NetworkError):
                    self._keys.clear(scope)
                self._workspace.showToast(self._format_error(err), "bad")
                return
            self._keys.clear(scope)
            self._accept_202_response(res, epoch=epoch)

        self._runner.submit(_work, _done)

    @Slot()
    def dismissActiveOperation(self) -> None:
        if self._active_op and self._active_op.is_terminal:
            self._op_timer.stop()
            self._active_op = None
            self.operationChanged.emit()

    # ---- 202 Acceptance & Polling State Machine ----

    def _accept_202_response(self, res: ApiResponse, *, epoch: int) -> None:
        op_data = res.data.get("operation") if isinstance(res.data, dict) else None
        if not isinstance(op_data, dict):
            return
        self._active_op = TrackedOperation.from_api(op_data, epoch=epoch, now_monotonic=self._clock())
        self.operationChanged.emit()
        act_lbl = ACTION_LABELS.get(self._active_op.action, self._active_op.action)
        self._workspace.showToast(f"{act_lbl}已受理（{self._active_op.operation_id}），正在追踪执行步骤…", "info")
        if self._active_op.is_terminal:
            self._on_operation_terminal(self._active_op)
        else:
            self._schedule_next_operation_poll()

    def _schedule_next_operation_poll(self) -> None:
        if not self._active_op or self._active_op.is_terminal:
            return
        delay_ms = self._active_op.next_poll_interval_ms(self._clock())
        self._op_timer.start(delay_ms)

    def _poll_active_operation(self) -> None:
        op = self._active_op
        if op is None or op.is_terminal or self._op_poll_in_flight:
            return
        epoch = op.epoch
        if epoch != self._active_epoch:
            return
        op_id = op.operation_id
        self._op_poll_in_flight = True

        def _work() -> dict[str, Any]:
            return self._api.get_operation(op_id, expected_epoch=epoch)

        def _done(data: dict[str, Any] | None, err: Exception | None) -> None:
            self._op_poll_in_flight = False
            if self._active_op is None or self._active_op.operation_id != op_id or epoch != self._active_epoch:
                return
            if isinstance(err, SessionInvalidatedError):
                return
            if isinstance(err, NetworkError):
                # Network outage: keep polling original operation_id, NEVER re-create write!
                self._active_op.network_interrupted = True
                self.operationChanged.emit()
                self._schedule_next_operation_poll()
                return
            if err is not None or not isinstance(data, dict):
                self._schedule_next_operation_poll()
                return

            self._active_op.update_from_api(data)
            self.operationChanged.emit()
            if self._active_op.is_terminal:
                self._on_operation_terminal(self._active_op)
            else:
                self._schedule_next_operation_poll()

        self._runner.submit(_work, _done)

    def _on_operation_terminal(self, op: TrackedOperation) -> None:
        self._op_timer.stop()
        act_lbl = ACTION_LABELS.get(op.action, op.action)
        if op.status == "succeeded":
            self._workspace.showToast(f"{act_lbl}已完成", "info")
        elif op.status == "needs_verification":
            self._workspace.showToast(f"{act_lbl}需要人工核实，已停止自动轮询", "warn")
        elif op.status == "failed":
            self._workspace.showToast(f"{act_lbl}失败：{op.error_message or op.error_code}", "bad")

        self.operationCompleted.emit(op.operation_id, op.action, op.status)
        # Refresh current page state cleanly after terminal operation
        if self._workspace.route == "overview":
            self._workspace.pollOverview()
        elif self._workspace.route == "groups":
            self._workspace.pollGroups()
        elif self._workspace.route == "detail":
            self._workspace.pollGroupDetail()

    # ---- Error handling (409, 412, 422) ----

    def _handle_write_error(self, err: Exception | None, *, group_id_for_412: str) -> None:
        if isinstance(err, ApiError):
            if err.status_code == 412 and err.code == "CONFIG_VERSION_MISMATCH" and group_id_for_412:
                # Preserve user's draft and reload authoritative ETag/config_version!
                self._form_error = "配置版本已发生变更（412），已保留您的草稿并重新加载最新版本，请核对后再次提交。"
                self._reload_edit_version_preserving_draft(group_id_for_412)
                return
            if err.status_code == 422:
                fmap: dict[str, str] = {}
                for det in err.details:
                    if det.field:
                        fmap[det.field] = det.message
                self._field_errors = fmap
                self._form_error = err.message or "表单参数校验失败（422）。"
                return
            if err.status_code == 409:
                fmap = {det.field: det.message for det in err.details if det.field}
                self._field_errors = fmap
                self._form_error = f"冲突（{err.code}）：{err.message}"
                return
        self._form_error = self._format_error(err)

    def _reload_edit_version_preserving_draft(self, group_id: str) -> None:
        epoch = self._active_epoch

        def _work() -> ApiResponse:
            return self._api.get_group(group_id, expected_epoch=epoch)

        def _done(res: ApiResponse | None, err: Exception | None) -> None:
            if epoch != self._active_epoch or not self._dialog_open or self._dialog_group_id != group_id:
                return
            if err is not None or res is None or not isinstance(res.data, dict):
                return
            new_ver = int(res.data.get("config_version", self._dialog_config_version))
            self._dialog_config_version = new_ver
            self._dialog_etag = res.etag or f'"v{new_ver}"'
            self._version_reloaded_notice = (
                f"已自动获取最新配置版本 v{new_ver}（当前远端：{res.data.get('name')}，"
                f"UDP {res.data.get('dtu_port')} / {str(res.data.get('gcs_protocol', 'tcp')).upper()} {res.data.get('gcs_port')}），"
                "您的草稿已完整保留。"
            )
            self.dialogChanged.emit()

        self._runner.submit(_work, _done)

    @staticmethod
    def _format_error(err: Exception | None) -> str:
        if err is None:
            return "未知错误。"
        if isinstance(err, ApiError):
            req = f"（{err.request_id}）" if err.request_id else ""
            return f"{err.message}{req}"
        return str(err)
