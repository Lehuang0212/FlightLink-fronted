"""Shared authentication coordinator with single-flight token refresh and epoch isolation."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable

from flightlink_desktop.api.credentials import CredentialStore
from flightlink_desktop.api.errors import ApiError, NetworkError, SessionInvalidatedError


@dataclass(frozen=True)
class UserProfile:
    user_id: str
    username: str
    display_name: str
    role: str  # "admin" | "viewer"
    created_at: str = ""
    last_login_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "UserProfile":
        return cls(
            user_id=str(data.get("user_id", "")),
            username=str(data.get("username", "")),
            display_name=str(data.get("display_name") or data.get("username") or ""),
            role=str(data.get("role", "viewer")),
            created_at=str(data.get("created_at", "")),
            last_login_at=str(data["last_login_at"]) if data.get("last_login_at") is not None else None,
        )


@dataclass(frozen=True)
class TokenBundle:
    access_token: str
    refresh_token: str
    expires_at: str
    refresh_expires_at: str
    user: UserProfile


@dataclass(frozen=True)
class AuthSnapshot:
    epoch: int
    server_url: str
    ecs_instance_id: str
    access_token: str | None
    refresh_token: str | None
    user: UserProfile | None

    @property
    def is_authenticated(self) -> bool:
        return bool(self.access_token and self.user and self.server_url)

    @property
    def is_admin(self) -> bool:
        return self.user is not None and self.user.role == "admin"

    @property
    def can_archive_sync(self) -> bool:
        # Both admin and viewer can run local archive auto-save/retry via authenticated read endpoints
        return self.is_authenticated


class AuthCoordinator:
    """Thread-safe session state + single-flight 401 TOKEN_EXPIRED refresh coordinator.

    Shared by all UI pollers, write workers, and the background archive sync worker.
    - Access token lives strictly in memory.
    - Refresh token is optionally persisted in OS Credential Manager bound to (server_url, username).
    - Epoch monotonically increments on every login, logout, server switch, or refresh failure,
      guaranteeing late responses from a previous host/session are always rejected.
    """

    def __init__(
        self,
        *,
        credential_store: CredentialStore | None = None,
        on_session_expired: Callable[[int, str], None] | None = None,
    ) -> None:
        self._lock = threading.Lock()
        self._refresh_cond = threading.Condition(self._lock)
        self._refresh_in_flight = False
        self._refresh_error: Exception | None = None

        self._epoch = 0
        self._server_url = ""
        self._ecs_instance_id = ""
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._user: UserProfile | None = None
        self._remember_refresh = False

        self._store = credential_store or CredentialStore()
        self._on_session_expired = on_session_expired

    def snapshot(self) -> AuthSnapshot:
        with self._lock:
            return AuthSnapshot(
                epoch=self._epoch,
                server_url=self._server_url,
                ecs_instance_id=self._ecs_instance_id,
                access_token=self._access_token,
                refresh_token=self._refresh_token,
                user=self._user,
            )

    def current_epoch(self) -> int:
        with self._lock:
            return self._epoch

    def is_epoch_current(self, epoch: int) -> bool:
        with self._lock:
            return epoch == self._epoch

    def set_session(
        self,
        *,
        server_url: str,
        ecs_instance_id: str,
        bundle: TokenBundle,
        remember_refresh: bool = True,
    ) -> AuthSnapshot:
        normalized = server_url.rstrip("/")
        with self._lock:
            self._epoch += 1
            self._server_url = normalized
            self._ecs_instance_id = ecs_instance_id
            self._access_token = bundle.access_token
            self._refresh_token = bundle.refresh_token
            self._user = bundle.user
            self._remember_refresh = remember_refresh
            snap = AuthSnapshot(
                epoch=self._epoch,
                server_url=self._server_url,
                ecs_instance_id=self._ecs_instance_id,
                access_token=self._access_token,
                refresh_token=self._refresh_token,
                user=self._user,
            )
            self._refresh_cond.notify_all()

        self._store.save_recent_server(normalized, bundle.user.username)
        if remember_refresh:
            self._store.save_refresh_token(normalized, bundle.user.username, bundle.refresh_token)
        else:
            self._store.clear_refresh_token(normalized, bundle.user.username)
        return snap

    def clear_session(self, *, clear_persisted_refresh: bool = True) -> int:
        with self._lock:
            old_server = self._server_url
            old_user = self._user.username if self._user else ""
            self._epoch += 1
            self._access_token = None
            self._refresh_token = None
            self._user = None
            self._ecs_instance_id = ""
            self._remember_refresh = False
            new_epoch = self._epoch
            self._refresh_cond.notify_all()

        if clear_persisted_refresh and old_server and old_user:
            self._store.clear_refresh_token(old_server, old_user)
        return new_epoch

    def switch_server(self, new_server_url: str) -> int:
        """Invalidate any active session and switch target host cleanly."""
        with self._lock:
            self._epoch += 1
            self._server_url = new_server_url.rstrip("/")
            self._ecs_instance_id = ""
            self._access_token = None
            self._refresh_token = None
            self._user = None
            self._remember_refresh = False
            new_epoch = self._epoch
            self._refresh_cond.notify_all()
        if new_server_url.strip():
            self._store.save_recent_server(new_server_url.rstrip("/"))
        return new_epoch

    def refresh_single_flight(
        self,
        *,
        expected_epoch: int,
        failed_access_token: str | None,
        do_refresh: Callable[[str, str], TokenBundle],
    ) -> str:
        """Execute single-flight token refresh for 401 TOKEN_EXPIRED.

        - Concurrent callers sharing the same (epoch, failed_access_token) wait on the
          single in-flight refresh request and receive the rotated access token.
        - If epoch changed (logout or server switch), raises SessionInvalidatedError.
        - If refresh fails, clears session state and fires on_session_expired callback.
        """
        with self._refresh_cond:
            if expected_epoch != self._epoch:
                raise SessionInvalidatedError("Session changed before refresh")

            # Another thread already rotated the token for this epoch
            if self._access_token and self._access_token != failed_access_token:
                return self._access_token

            if self._refresh_in_flight:
                while self._refresh_in_flight:
                    self._refresh_cond.wait()
                if expected_epoch != self._epoch:
                    raise SessionInvalidatedError("Session changed while waiting for refresh")
                if self._refresh_error is not None:
                    raise self._refresh_error
                if self._access_token:
                    return self._access_token
                raise SessionInvalidatedError("No access token after refresh")

            refresh_token = self._refresh_token
            server_url = self._server_url
            remember = self._remember_refresh
            if not refresh_token or not server_url:
                raise SessionInvalidatedError("No refresh token available")

            self._refresh_in_flight = True
            self._refresh_error = None

        # Perform network refresh outside lock so UI/other operations don't deadlock
        bundle: TokenBundle | None = None
        err: Exception | None = None
        try:
            bundle = do_refresh(server_url, refresh_token)
        except Exception as exc:
            err = exc

        notify_expired = False
        expired_reason = ""
        old_server = ""
        old_user = ""
        with self._refresh_cond:
            self._refresh_in_flight = False
            if expected_epoch != self._epoch:
                # Session was logged out or switched during refresh — discard late refresh result!
                self._refresh_error = SessionInvalidatedError("Session invalidated during refresh")
                self._refresh_cond.notify_all()
                raise self._refresh_error

            if err is not None or bundle is None:
                old_server = self._server_url
                old_user = self._user.username if self._user else ""
                self._epoch += 1
                self._access_token = None
                self._refresh_token = None
                self._user = None
                self._remember_refresh = False
                self._refresh_error = err or ApiError(401, "REFRESH_FAILED", "Token refresh failed")
                notify_expired = True
                expired_reason = str(self._refresh_error)
                expired_epoch = self._epoch
                self._refresh_cond.notify_all()
            else:
                self._access_token = bundle.access_token
                self._refresh_token = bundle.refresh_token
                self._user = bundle.user
                self._refresh_error = None
                new_token = bundle.access_token
                self._refresh_cond.notify_all()

        if notify_expired:
            if old_server and old_user:
                self._store.clear_refresh_token(old_server, old_user)
            if self._on_session_expired is not None:
                self._on_session_expired(expired_epoch, expired_reason)
            if isinstance(err, (ApiError, NetworkError, SessionInvalidatedError)):
                raise err
            raise ApiError(401, "REFRESH_FAILED", expired_reason)

        if remember and bundle is not None:
            self._store.save_refresh_token(server_url, bundle.user.username, bundle.refresh_token)
        return new_token
