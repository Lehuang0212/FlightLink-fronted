"""GUI-thread SessionViewModel managing health probe, real login, role state, and epoch isolation."""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Qt, Signal, Slot
from PySide6.QtGui import QGuiApplication

from flightlink_desktop.api.auth import AuthCoordinator, AuthSnapshot
from flightlink_desktop.api.client import FlightLinkApiClient, HealthResult
from flightlink_desktop.api.credentials import CredentialStore
from flightlink_desktop.api.errors import ApiError, NetworkError, SessionInvalidatedError, UrlValidationError
from flightlink_desktop.api.url_utils import DEFAULT_SERVER_URL, normalize_server_url
from flightlink_desktop.workers.task_runner import BackgroundTaskRunner


class SessionViewModel(QObject):
    """QObject ViewModel owned strictly by the Qt GUI thread."""

    serverUrlChanged = Signal()
    healthChanged = Signal()
    loginStateChanged = Signal()
    sessionChanged = Signal()
    sessionStarted = Signal(int, str, str)  # epoch, ecs_instance_id, server_url
    sessionEnded = Signal(int, str)  # new_epoch, reason
    _internalSessionExpired = Signal(int, str)

    def __init__(
        self,
        api_client: FlightLinkApiClient,
        auth: AuthCoordinator,
        credential_store: CredentialStore,
        task_runner: BackgroundTaskRunner,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._api = api_client
        self._auth = auth
        self._store = credential_store
        self._runner = task_runner

        recent = self._store.get_recent_server()
        self._server_url: str = recent or DEFAULT_SERVER_URL
        self._health_status: str = "idle"  # idle | checking | ok | error
        self._health_message: str = ""
        self._health_rtt_ms: int = 0
        self._ecs_instance_id: str = ""
        self._server_version: str = ""
        self._probe_seq: int = 0

        self._logging_in: bool = False
        self._login_error: str = ""
        self._login_seq: int = 0
        self._authenticated: bool = False
        self._current_username: str = ""
        self._current_display_name: str = ""
        self._current_role: str = ""
        self._current_epoch: int = self._auth.current_epoch()

        self._internalSessionExpired.connect(
            self._handle_session_expired_on_gui,
            Qt.ConnectionType.QueuedConnection,
        )

    def notify_expired_from_worker(self, expired_epoch: int, reason: str) -> None:
        """Thread-safe bridge called by AuthCoordinator when refresh fails."""
        self._internalSessionExpired.emit(expired_epoch, reason)

    @Slot(int, str)
    def _handle_session_expired_on_gui(self, expired_epoch: int, reason: str) -> None:
        if expired_epoch < self._current_epoch:
            return
        self._current_epoch = expired_epoch
        was_authed = self._authenticated
        self._authenticated = False
        self._current_username = ""
        self._current_display_name = ""
        self._current_role = ""
        self._logging_in = False
        self._login_error = "登录状态已过期，请重新登录。"
        self.loginStateChanged.emit()
        self.sessionChanged.emit()
        if was_authed:
            self.sessionEnded.emit(expired_epoch, reason or "TOKEN_EXPIRED")

    # ---- Properties ----

    @Property(str, notify=serverUrlChanged)
    def serverUrl(self) -> str:
        return self._server_url

    @Property(str, notify=healthChanged)
    def healthStatus(self) -> str:
        return self._health_status

    @Property(str, notify=healthChanged)
    def healthMessage(self) -> str:
        return self._health_message

    @Property(int, notify=healthChanged)
    def healthRttMs(self) -> int:
        return self._health_rtt_ms

    @Property(str, notify=healthChanged)
    def ecsInstanceId(self) -> str:
        return self._ecs_instance_id

    @Property(bool, notify=loginStateChanged)
    def loggingIn(self) -> bool:
        return self._logging_in

    @Property(str, notify=loginStateChanged)
    def loginError(self) -> str:
        return self._login_error

    @Property(bool, notify=sessionChanged)
    def authenticated(self) -> bool:
        return self._authenticated

    @Property(str, notify=sessionChanged)
    def currentUsername(self) -> str:
        return self._current_username

    @Property(str, notify=sessionChanged)
    def currentDisplayName(self) -> str:
        return self._current_display_name

    @Property(str, notify=sessionChanged)
    def currentRole(self) -> str:
        return self._current_role

    @Property(str, notify=sessionChanged)
    def currentRoleLabel(self) -> str:
        if self._current_role == "admin":
            return "系统管理员"
        if self._current_role == "viewer":
            return "只读观测员"
        return ""

    @Property(bool, notify=sessionChanged)
    def isAdmin(self) -> bool:
        return self._authenticated and self._current_role == "admin"

    @Property(bool, notify=sessionChanged)
    def canArchiveSync(self) -> bool:
        # Both admin and viewer can run local archive auto-save and manual retry
        return self._authenticated

    @Property(int, notify=sessionChanged)
    def sessionEpoch(self) -> int:
        return self._current_epoch

    # ---- Slots ----

    @Slot()
    def clearLoginError(self) -> None:
        if self._login_error:
            self._login_error = ""
            self.loginStateChanged.emit()

    @Slot(str)
    def copyToClipboard(self, text: str) -> None:
        if not text:
            return
        cb = QGuiApplication.clipboard()
        if cb is not None:
            cb.setText(text)

    @Slot(str)
    def setServerUrl(self, value: str) -> None:
        if value != self._server_url:
            self._server_url = value
            self.serverUrlChanged.emit()

    @Slot(str)
    def probeHealth(self, raw_url: str) -> None:
        try:
            normalized = normalize_server_url(raw_url)
        except UrlValidationError as exc:
            self._health_status = "error"
            self._health_message = str(exc)
            self._health_rtt_ms = 0
            self.healthChanged.emit()
            return

        if normalized != self._server_url:
            self._server_url = normalized
            self.serverUrlChanged.emit()
        self._store.save_recent_server(normalized)

        self._probe_seq += 1
        seq = self._probe_seq
        self._health_status = "checking"
        self._health_message = "正在检测服务器连通性…"
        self.healthChanged.emit()

        def _work() -> HealthResult:
            return self._api.probe_health(normalized)

        def _done(result: HealthResult | None, err: Exception | None) -> None:
            if seq != self._probe_seq:
                return
            if err is not None or result is None:
                self._health_status = "error"
                self._health_rtt_ms = 0
                self._health_message = self._format_error(err)
            else:
                self._health_status = "ok" if result.status == "ok" and result.db_ok else "error"
                self._health_rtt_ms = result.rtt_ms
                self._ecs_instance_id = result.ecs_instance_id
                self._server_version = result.version
                inst = f" · {result.ecs_instance_id}" if result.ecs_instance_id else ""
                if self._health_status == "ok":
                    self._health_message = f"ECS 已连接{inst} · {result.rtt_ms} ms"
                else:
                    self._health_message = f"ECS 状态降级（{result.status}）{inst} · {result.rtt_ms} ms"
            self.healthChanged.emit()

        self._runner.submit(_work, _done)

    @Slot(str, str, str, bool)
    def login(self, raw_url: str, username: str, password: str, remember_session: bool) -> None:
        if self._logging_in:
            return

        try:
            normalized = normalize_server_url(raw_url)
        except UrlValidationError as exc:
            self._login_error = str(exc)
            self.loginStateChanged.emit()
            return

        clean_user = (username or "").strip()
        if not clean_user:
            self._login_error = "请输入账号。"
            self.loginStateChanged.emit()
            return
        if not password:
            self._login_error = "请输入密码。"
            self.loginStateChanged.emit()
            return

        if normalized != self._server_url:
            self._server_url = normalized
            self.serverUrlChanged.emit()

        self._logging_in = True
        self._login_error = ""
        self._login_seq += 1
        seq = self._login_seq
        self._health_status = "checking"
        self._health_message = "正在检测连通性并登录…"
        self.loginStateChanged.emit()
        self.healthChanged.emit()

        def _work() -> tuple[HealthResult, AuthSnapshot]:
            health, _ = self._api.login(
                normalized,
                clean_user,
                password,
                remember_refresh=remember_session,
            )
            return health, self._auth.snapshot()

        def _done(result: tuple[HealthResult, AuthSnapshot] | None, err: Exception | None) -> None:
            if seq != self._login_seq:
                return
            self._logging_in = False
            if err is not None or result is None:
                self._login_error = self._format_error(err)
                if isinstance(err, NetworkError):
                    self._health_status = "error"
                    self._health_message = self._login_error
                    self.healthChanged.emit()
                self.loginStateChanged.emit()
                return

            health, snap = result
            if not self._auth.is_epoch_current(snap.epoch) or not snap.is_authenticated or snap.user is None:
                self.loginStateChanged.emit()
                return

            self._apply_authenticated_snapshot(health, snap)

        self._runner.submit(_work, _done)

    @Slot()
    def tryRestoreSession(self) -> None:
        """Attempt cross-restart session recovery using Windows Credential Manager refresh token."""
        if self._authenticated or self._logging_in:
            return
        recent_server = self._store.get_recent_server()
        recent_user = self._store.get_recent_username()
        if not recent_server or not recent_user:
            return
        refresh_token = self._store.load_refresh_token(recent_server, recent_user)
        if not refresh_token:
            return

        self._logging_in = True
        self._login_seq += 1
        seq = self._login_seq
        self.loginStateChanged.emit()

        def _work() -> tuple[HealthResult, AuthSnapshot]:
            health, _ = self._api.restore_session(recent_server, recent_user, refresh_token)
            return health, self._auth.snapshot()

        def _done(result: tuple[HealthResult, AuthSnapshot] | None, err: Exception | None) -> None:
            if seq != self._login_seq:
                return
            self._logging_in = False
            if err is not None or result is None:
                if isinstance(err, ApiError) and err.status_code == 401:
                    self._store.clear_refresh_token(recent_server, recent_user)
                self.loginStateChanged.emit()
                return
            health, snap = result
            if self._auth.is_epoch_current(snap.epoch) and snap.is_authenticated and snap.user is not None:
                self._apply_authenticated_snapshot(health, snap)
            else:
                self.loginStateChanged.emit()

        self._runner.submit(_work, _done)

    @Slot()
    def logout(self) -> None:
        self._login_seq += 1
        self._probe_seq += 1
        was_authed = self._authenticated
        new_epoch = self._auth.current_epoch() + 1

        # Clear GUI state immediately; api.logout() clears AuthCoordinator epoch synchronously first
        self._authenticated = False
        self._logging_in = False
        self._current_username = ""
        self._current_display_name = ""
        self._current_role = ""
        self._login_error = ""

        # Perform server-side revoke in background while invalidating local epoch immediately
        snap_before = self._auth.snapshot()
        actual_epoch = self._auth.clear_session(clear_persisted_refresh=True)
        self._current_epoch = actual_epoch
        self.loginStateChanged.emit()
        self.sessionChanged.emit()
        if was_authed:
            self.sessionEnded.emit(actual_epoch, "USER_LOGOUT")

        if snap_before.server_url and snap_before.access_token:
            def _revoke() -> None:
                client = self._api._get_client(snap_before.server_url)
                headers = {"Authorization": f"Bearer {snap_before.access_token}"}
                body = {"refresh_token": snap_before.refresh_token} if snap_before.refresh_token else {}
                try:
                    client.post("/api/v1/auth/logout", json=body, headers=headers)
                except Exception:
                    pass

            self._runner.submit(_revoke, lambda _r, _e: None)

    @Slot(str)
    def switchServer(self, raw_url: str) -> None:
        try:
            normalized = normalize_server_url(raw_url)
        except UrlValidationError as exc:
            self._login_error = str(exc)
            self.loginStateChanged.emit()
            return

        self._login_seq += 1
        self._probe_seq += 1
        was_authed = self._authenticated
        new_epoch = self._auth.switch_server(normalized)
        self._current_epoch = new_epoch
        self._server_url = normalized
        self._ecs_instance_id = ""
        self._health_status = "idle"
        self._health_message = ""
        self._health_rtt_ms = 0
        self._authenticated = False
        self._logging_in = False
        self._current_username = ""
        self._current_display_name = ""
        self._current_role = ""
        self._login_error = ""
        self.serverUrlChanged.emit()
        self.healthChanged.emit()
        self.loginStateChanged.emit()
        self.sessionChanged.emit()
        if was_authed:
            self.sessionEnded.emit(new_epoch, "SERVER_SWITCHED")

    def _apply_authenticated_snapshot(self, health: HealthResult, snap: AuthSnapshot) -> None:
        assert snap.user is not None
        self._current_epoch = snap.epoch
        self._server_url = snap.server_url
        self._ecs_instance_id = health.ecs_instance_id
        self._server_version = health.version
        self._health_status = "ok" if health.status == "ok" and health.db_ok else "error"
        self._health_rtt_ms = health.rtt_ms
        inst = f" · {health.ecs_instance_id}" if health.ecs_instance_id else ""
        self._health_message = f"ECS 已连接{inst} · {health.rtt_ms} ms"
        self._authenticated = True
        self._current_username = snap.user.username
        self._current_display_name = snap.user.display_name
        self._current_role = snap.user.role
        self._login_error = ""
        self.serverUrlChanged.emit()
        self.healthChanged.emit()
        self.loginStateChanged.emit()
        self.sessionChanged.emit()
        self.sessionStarted.emit(snap.epoch, health.ecs_instance_id, snap.server_url)

    @staticmethod
    def _format_error(err: Exception | None) -> str:
        if err is None:
            return "未知错误。"
        if isinstance(err, SessionInvalidatedError):
            return "会话已切换。"
        if isinstance(err, ApiError):
            if err.code == "INVALID_CREDENTIALS":
                return "账号或密码错误。"
            if err.code == "INSUFFICIENT_ROLE":
                return "当前账号仅只读权限，无法执行该操作。"
            req = f"（{err.request_id}）" if err.request_id else ""
            return f"{err.message}{req}"
        return str(err)
