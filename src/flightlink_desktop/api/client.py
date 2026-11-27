"""Background HTTP client adhering strictly to docs/api/openapi.yaml."""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

import httpx

from flightlink_desktop.api.auth import AuthCoordinator, TokenBundle, UserProfile
from flightlink_desktop.api.errors import ApiError, NetworkError, SessionInvalidatedError
from flightlink_desktop.api.url_utils import normalize_server_url


@dataclass(frozen=True)
class HealthResult:
    server_url: str
    status: str
    version: str
    ecs_instance_id: str
    observed_at: str
    db_ok: bool
    rtt_ms: int


@dataclass(frozen=True)
class ApiResponse:
    status_code: int
    data: Any
    headers: dict[str, str]
    etag: str | None = None


class FlightLinkApiClient:
    """Thread-safe httpx client for FlightLink ECS /api/v1.

    - Never disables TLS verification (verify=True always).
    - Shares AuthCoordinator across UI and archive workers for single-flight 401 TOKEN_EXPIRED refresh.
    - Checks session epoch before and after every authenticated request so late responses
      after logout or server switch are never delivered or persisted.
    - Accepts an optional httpx.BaseTransport for deterministic tests (never a production mock mode).
    """

    def __init__(
        self,
        auth: AuthCoordinator,
        *,
        timeout: float = 15.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.auth = auth
        self._timeout = timeout
        self._transport = transport
        self._client_lock = threading.Lock()
        self._clients: dict[str, httpx.Client] = {}

    def _get_client(self, server_url: str) -> httpx.Client:
        key = server_url.rstrip("/")
        with self._client_lock:
            client = self._clients.get(key)
            if client is None or client.is_closed:
                kwargs: dict[str, Any] = {
                    "base_url": key,
                    "timeout": self._timeout,
                    "verify": True,  # Hard rule: never disable TLS verification
                    "follow_redirects": False,
                }
                if self._transport is not None:
                    kwargs["transport"] = self._transport
                client = httpx.Client(**kwargs)
                self._clients[key] = client
            return client

    def close(self) -> None:
        with self._client_lock:
            clients = list(self._clients.values())
            self._clients.clear()
        for client in clients:
            try:
                client.close()
            except Exception:
                pass

    @staticmethod
    def _parse_json_safe(resp: httpx.Response) -> Any:
        if not resp.content:
            return None
        try:
            return resp.json()
        except ValueError:
            return None

    @staticmethod
    def _parse_token_bundle(payload: dict[str, Any]) -> TokenBundle:
        user_raw = payload.get("user")
        if not isinstance(user_raw, dict):
            raise ApiError(500, "INVALID_RESPONSE", "Missing user object in token response")
        return TokenBundle(
            access_token=str(payload["access_token"]),
            refresh_token=str(payload["refresh_token"]),
            expires_at=str(payload["expires_at"]),
            refresh_expires_at=str(payload["refresh_expires_at"]),
            user=UserProfile.from_dict(user_raw),
        )

    @staticmethod
    def _format_http_error(prefix: str, exc: httpx.HTTPError) -> str:
        if isinstance(exc, httpx.RemoteProtocolError):
            return f"{prefix}（远端断开连接，请检查端口与 HTTP/HTTPS 协议是否匹配）：{exc}"
        if isinstance(exc, httpx.ConnectTimeout):
            return f"{prefix}（连接超时，请检查地址、端口或防火墙）：{exc}"
        if isinstance(exc, httpx.ConnectError):
            return f"{prefix}（无法建立连接，请检查服务器是否启动及端口）：{exc}"
        return f"{prefix}：{exc}"

    def probe_health(self, raw_server_url: str) -> HealthResult:
        """GET /api/v1/health — strictly read-only connectivity & RTT check."""
        server_url = normalize_server_url(raw_server_url)
        client = self._get_client(server_url)
        t0 = time.perf_counter()
        try:
            resp = client.get("/api/v1/health")
        except httpx.HTTPError as exc:
            raise NetworkError(self._format_http_error("无法连接服务器", exc)) from exc
        rtt_ms = max(1, int(round((time.perf_counter() - t0) * 1000)))
        payload = self._parse_json_safe(resp)
        if resp.status_code != 200 or not isinstance(payload, dict):
            raise ApiError.from_response(resp.status_code, payload)
        return HealthResult(
            server_url=server_url,
            status=str(payload.get("status", "unknown")),
            version=str(payload.get("version", "")),
            ecs_instance_id=str(payload.get("ecs_instance_id", "")),
            observed_at=str(payload.get("observed_at", "")),
            db_ok=bool(payload.get("db_ok", False)),
            rtt_ms=rtt_ms,
        )

    def _raw_refresh(self, server_url: str, refresh_token: str) -> TokenBundle:
        client = self._get_client(server_url)
        try:
            resp = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": refresh_token},
            )
        except httpx.HTTPError as exc:
            raise NetworkError(f"刷新令牌失败：{exc}") from exc
        payload = self._parse_json_safe(resp)
        if resp.status_code != 200 or not isinstance(payload, dict):
            raise ApiError.from_response(resp.status_code, payload)
        return self._parse_token_bundle(payload)

    def login(
        self,
        raw_server_url: str,
        username: str,
        password: str,
        *,
        remember_refresh: bool = True,
    ) -> tuple[HealthResult, TokenBundle]:
        """Probe /api/v1/health first, then POST /api/v1/auth/login.

        Wrong credentials return 401 INVALID_CREDENTIALS and NEVER trigger refresh.
        """
        health = self.probe_health(raw_server_url)
        client = self._get_client(health.server_url)
        try:
            resp = client.post(
                "/api/v1/auth/login",
                json={"username": username.strip(), "password": password},
            )
        except httpx.HTTPError as exc:
            raise NetworkError(f"登录请求失败：{exc}") from exc

        payload = self._parse_json_safe(resp)
        if resp.status_code != 200 or not isinstance(payload, dict):
            raise ApiError.from_response(resp.status_code, payload)

        bundle = self._parse_token_bundle(payload)
        self.auth.set_session(
            server_url=health.server_url,
            ecs_instance_id=health.ecs_instance_id,
            bundle=bundle,
            remember_refresh=remember_refresh,
        )
        return health, bundle

    def restore_session(self, raw_server_url: str, username: str, refresh_token: str) -> tuple[HealthResult, TokenBundle]:
        """Restore session on startup using a refresh token from Windows Credential Manager."""
        health = self.probe_health(raw_server_url)
        bundle = self._raw_refresh(health.server_url, refresh_token)
        self.auth.set_session(
            server_url=health.server_url,
            ecs_instance_id=health.ecs_instance_id,
            bundle=bundle,
            remember_refresh=True,
        )
        return health, bundle

    def logout(self) -> None:
        """POST /api/v1/auth/logout and immediately invalidate local session epoch."""
        snap = self.auth.snapshot()
        # Invalidate local epoch first so no late poll/archive response can slip in
        self.auth.clear_session(clear_persisted_refresh=True)
        if not snap.server_url or not snap.access_token:
            return
        client = self._get_client(snap.server_url)
        headers = {"Authorization": f"Bearer {snap.access_token}"}
        body: dict[str, Any] = {}
        if snap.refresh_token:
            body["refresh_token"] = snap.refresh_token
        try:
            client.post("/api/v1/auth/logout", json=body, headers=headers)
        except httpx.HTTPError:
            # Best-effort server revoke; local session is already cleared
            pass

    def request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
        extra_headers: dict[str, str] | None = None,
        expected_epoch: int | None = None,
        require_admin: bool = False,
    ) -> ApiResponse:
        """Perform an authenticated JSON request with single-flight 401 TOKEN_EXPIRED retry (max 1 replay)."""
        snap = self.auth.snapshot()
        epoch = expected_epoch if expected_epoch is not None else snap.epoch
        if not snap.is_authenticated or snap.epoch != epoch:
            raise SessionInvalidatedError("Session is not active or epoch mismatch")
        if require_admin and not snap.is_admin:
            raise ApiError(
                status_code=403,
                code="INSUFFICIENT_ROLE",
                message="当前账号仅具备只读权限，无法执行服务端写操作。",
                retryable=False,
            )

        server_url = snap.server_url
        token = snap.access_token
        assert token is not None

        for attempt in range(2):
            if not self.auth.is_epoch_current(epoch):
                raise SessionInvalidatedError("Session invalidated before request")

            headers = {"Authorization": f"Bearer {token}"}
            if extra_headers:
                headers.update(extra_headers)

            client = self._get_client(server_url)
            try:
                resp = client.request(method, path, params=params, json=json_body, headers=headers)
            except httpx.HTTPError as exc:
                if not self.auth.is_epoch_current(epoch):
                    raise SessionInvalidatedError("Session invalidated during network error") from exc
                raise NetworkError(f"网络请求失败：{exc}") from exc

            # Reject late responses from an old session/server
            if not self.auth.is_epoch_current(epoch):
                raise SessionInvalidatedError("Discarding late response from previous session")

            payload = self._parse_json_safe(resp)
            if resp.status_code == 401 and attempt == 0:
                err = ApiError.from_response(resp.status_code, payload)
                if err.code == "TOKEN_EXPIRED":
                    token = self.auth.refresh_single_flight(
                        expected_epoch=epoch,
                        failed_access_token=token,
                        do_refresh=self._raw_refresh,
                    )
                    continue
                raise err

            if resp.status_code >= 400:
                raise ApiError.from_response(resp.status_code, payload)

            resp_headers = {k.lower(): v for k, v in resp.headers.items()}
            return ApiResponse(
                status_code=resp.status_code,
                data=payload,
                headers=resp_headers,
                etag=resp.headers.get("ETag"),
            )

        raise ApiError(401, "TOKEN_EXPIRED", "Token remained expired after single replay")

    @contextmanager
    def stream_authenticated(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        expected_epoch: int | None = None,
    ) -> Iterator[httpx.Response]:
        """Authenticated streaming request (used by archive file download) sharing single-flight refresh."""
        snap = self.auth.snapshot()
        epoch = expected_epoch if expected_epoch is not None else snap.epoch
        if not snap.is_authenticated or snap.epoch != epoch:
            raise SessionInvalidatedError("Session is not active or epoch mismatch")

        server_url = snap.server_url
        token = snap.access_token
        assert token is not None
        client = self._get_client(server_url)

        for attempt in range(2):
            if not self.auth.is_epoch_current(epoch):
                raise SessionInvalidatedError("Session invalidated before stream")

            headers = {"Authorization": f"Bearer {token}"}
            try:
                cm = client.stream(method, path, params=params, headers=headers)
                resp = cm.__enter__()
            except httpx.HTTPError as exc:
                if not self.auth.is_epoch_current(epoch):
                    raise SessionInvalidatedError("Session invalidated during stream open") from exc
                raise NetworkError(f"文件流请求失败：{exc}") from exc

            try:
                if not self.auth.is_epoch_current(epoch):
                    cm.__exit__(None, None, None)
                    raise SessionInvalidatedError("Discarding late stream response from previous session")

                if resp.status_code == 401 and attempt == 0:
                    resp.read()
                    payload = self._parse_json_safe(resp)
                    cm.__exit__(None, None, None)
                    err = ApiError.from_response(401, payload)
                    if err.code == "TOKEN_EXPIRED":
                        token = self.auth.refresh_single_flight(
                            expected_epoch=epoch,
                            failed_access_token=token,
                            do_refresh=self._raw_refresh,
                        )
                        continue
                    raise err

                yield resp
                cm.__exit__(None, None, None)
                return
            except BaseException as exc:
                cm.__exit__(type(exc), exc, exc.__traceback__)
                raise

        raise ApiError(401, "TOKEN_EXPIRED", "Stream remained unauthorized after single replay")

    # ---- Typed endpoint helpers aligned 1:1 with docs/api/openapi.yaml ----

    def get_me(self, *, expected_epoch: int | None = None) -> UserProfile:
        res = self.request_json("GET", "/api/v1/auth/me", expected_epoch=expected_epoch)
        return UserProfile.from_dict(res.data)

    def get_overview(self, *, expected_epoch: int | None = None) -> dict[str, Any]:
        return self.request_json("GET", "/api/v1/overview", expected_epoch=expected_epoch).data

    def list_groups(
        self,
        *,
        q: str = "",
        filter_mode: str = "all",
        expected_epoch: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"filter": filter_mode}
        if q:
            params["q"] = q
        return self.request_json("GET", "/api/v1/groups", params=params, expected_epoch=expected_epoch).data

    def get_group(self, group_id: str, *, expected_epoch: int | None = None) -> ApiResponse:
        return self.request_json("GET", f"/api/v1/groups/{group_id}", expected_epoch=expected_epoch)

    def create_group(
        self,
        payload: dict[str, Any],
        *,
        idempotency_key: str,
        expected_epoch: int | None = None,
    ) -> ApiResponse:
        return self.request_json(
            "POST",
            "/api/v1/groups",
            json_body=payload,
            extra_headers={"Idempotency-Key": idempotency_key},
            expected_epoch=expected_epoch,
            require_admin=True,
        )

    def update_group(
        self,
        group_id: str,
        payload: dict[str, Any],
        *,
        dry_run: bool = False,
        if_match: str | None = None,
        idempotency_key: str | None = None,
        expected_epoch: int | None = None,
    ) -> ApiResponse:
        headers: dict[str, str] = {}
        if if_match:
            headers["If-Match"] = if_match
        if idempotency_key and not dry_run:
            headers["Idempotency-Key"] = idempotency_key
        params = {"dry_run": "true"} if dry_run else None
        return self.request_json(
            "PATCH",
            f"/api/v1/groups/{group_id}",
            params=params,
            json_body=payload,
            extra_headers=headers or None,
            expected_epoch=expected_epoch,
            require_admin=True,
        )

    def delete_group(
        self,
        group_id: str,
        *,
        if_match: str | None = None,
        idempotency_key: str,
        expected_epoch: int | None = None,
    ) -> ApiResponse:
        headers: dict[str, str] = {"Idempotency-Key": idempotency_key}
        if if_match:
            headers["If-Match"] = if_match
        return self.request_json(
            "DELETE",
            f"/api/v1/groups/{group_id}",
            extra_headers=headers,
            expected_epoch=expected_epoch,
            require_admin=True,
        )

    def trigger_group_action(
        self,
        group_id: str,
        action: str,
        *,
        idempotency_key: str,
        if_match: str | None = None,
        expected_config_version: int | None = None,
        expected_epoch: int | None = None,
    ) -> ApiResponse:
        headers: dict[str, str] = {"Idempotency-Key": idempotency_key}
        if if_match:
            headers["If-Match"] = if_match
        body = {"expected_config_version": expected_config_version} if expected_config_version is not None else None
        return self.request_json(
            "POST",
            f"/api/v1/groups/{group_id}/actions/{action}",
            json_body=body,
            extra_headers=headers,
            expected_epoch=expected_epoch,
            require_admin=True,
        )

    def list_operations(
        self,
        *,
        group_id: str | None = None,
        status: str | None = None,
        limit: int = 20,
        expected_epoch: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if group_id:
            params["group_id"] = group_id
        if status:
            params["status"] = status
        return self.request_json("GET", "/api/v1/operations", params=params, expected_epoch=expected_epoch).data

    def get_operation(self, operation_id: str, *, expected_epoch: int | None = None) -> dict[str, Any]:
        return self.request_json("GET", f"/api/v1/operations/{operation_id}", expected_epoch=expected_epoch).data

    def retry_operation(
        self,
        operation_id: str,
        *,
        idempotency_key: str,
        expected_epoch: int | None = None,
    ) -> ApiResponse:
        return self.request_json(
            "POST",
            f"/api/v1/operations/{operation_id}/retry",
            extra_headers={"Idempotency-Key": idempotency_key},
            expected_epoch=expected_epoch,
            require_admin=True,
        )

    def query_live_logs(
        self,
        *,
        group_id: str = "",
        source: str = "all",
        level: str = "all",
        q: str = "",
        cursor: str = "",
        limit: int = 100,
        expected_epoch: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"source": source, "level": level, "limit": limit}
        if group_id:
            params["group_id"] = group_id
        if q:
            params["q"] = q
        if cursor:
            params["cursor"] = cursor
        return self.request_json("GET", "/api/v1/logs", params=params, expected_epoch=expected_epoch).data

    def list_archive_groups(
        self,
        *,
        include_deleted: bool = True,
        expected_epoch: int | None = None,
    ) -> dict[str, Any]:
        return self.request_json(
            "GET",
            "/api/v1/archive/groups",
            params={"include_deleted": "true" if include_deleted else "false"},
            expected_epoch=expected_epoch,
        ).data

    def get_archive_group(self, group_id: str, *, expected_epoch: int | None = None) -> dict[str, Any]:
        return self.request_json("GET", f"/api/v1/archive/groups/{group_id}", expected_epoch=expected_epoch).data

    def list_archive_group_sessions(
        self,
        group_id: str,
        *,
        status: str = "all",
        cursor: str = "",
        limit: int = 30,
        expected_epoch: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"status": status, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        return self.request_json(
            "GET",
            f"/api/v1/archive/groups/{group_id}/sessions",
            params=params,
            expected_epoch=expected_epoch,
        ).data

    def get_archive_session(self, session_id: str, *, expected_epoch: int | None = None) -> dict[str, Any]:
        return self.request_json("GET", f"/api/v1/archive/sessions/{session_id}", expected_epoch=expected_epoch).data

    def get_archive_session_entries(
        self,
        session_id: str,
        *,
        source: str,
        level: str = "all",
        q: str = "",
        cursor: str = "",
        limit: int = 200,
        expected_epoch: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"source": source, "level": level, "limit": limit}
        if q:
            params["q"] = q
        if cursor:
            params["cursor"] = cursor
        return self.request_json(
            "GET",
            f"/api/v1/archive/sessions/{session_id}/entries",
            params=params,
            expected_epoch=expected_epoch,
        ).data

    def list_archive_changes(
        self,
        *,
        cursor: str = "",
        limit: int = 50,
        expected_epoch: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        return self.request_json(
            "GET",
            "/api/v1/archive/changes",
            params=params,
            expected_epoch=expected_epoch,
        ).data
