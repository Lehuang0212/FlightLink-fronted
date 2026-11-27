"""P1 contract & concurrency tests: URL normalization, credentials, single-flight refresh, server isolation, viewer role."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

import httpx
import pytest

from flightlink_desktop.api.auth import AuthCoordinator
from flightlink_desktop.api.client import FlightLinkApiClient
from flightlink_desktop.api.credentials import CredentialStore
from flightlink_desktop.api.errors import ApiError, SessionInvalidatedError, UrlValidationError
from flightlink_desktop.api.url_utils import normalize_server_url


class MemorySecretBackend:
    def __init__(self) -> None:
        self.data: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.data.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.data[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        self.data.pop((service, username), None)


def _token_payload(access: str, refresh: str, username: str = "ops_admin", role: str = "admin") -> dict[str, Any]:
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_at": "2026-11-28T00:00:00Z",
        "refresh_expires_at": "2026-12-05T00:00:00Z",
        "user": {
            "user_id": f"usr_{username}",
            "username": username,
            "display_name": "管理员" if role == "admin" else "观测员",
            "role": role,
            "created_at": "2026-11-01T00:00:00Z",
            "last_login_at": "2026-11-27T00:00:00Z",
        },
    }


def _health_payload(ecs_id: str = "ecs-a") -> dict[str, Any]:
    return {
        "status": "ok",
        "version": "1.0.0",
        "ecs_instance_id": ecs_id,
        "observed_at": "2026-11-27T08:00:00Z",
        "db_ok": True,
    }


def test_normalize_server_url_preserves_explicit_ports_and_defaults() -> None:
    assert normalize_server_url("127.0.0.1") == "http://127.0.0.1:8000"
    assert normalize_server_url("http://127.0.0.1") == "http://127.0.0.1:8000"
    assert normalize_server_url("http://127.0.0.1:18080") == "http://127.0.0.1:18080"
    assert normalize_server_url("http://127.0.0.1:18080/api/v1/") == "http://127.0.0.1:18080"
    assert normalize_server_url("https://ecs.example.com") == "https://ecs.example.com"
    assert normalize_server_url("https://ecs.example.com:8443/api/v1") == "https://ecs.example.com:8443"
    assert normalize_server_url("ecs.example.com") == "https://ecs.example.com:8000"

    with pytest.raises(UrlValidationError):
        normalize_server_url("")
    with pytest.raises(UrlValidationError):
        normalize_server_url("ftp://127.0.0.1:8000")
    with pytest.raises(UrlValidationError):
        normalize_server_url("http://127.0.0.1:70000")


def test_credential_store_never_persists_plaintext_password_and_scopes_refresh_token(tmp_path: Path) -> None:
    secrets = MemorySecretBackend()
    cfg_path = tmp_path / "client_config.json"
    store = CredentialStore(config_path=cfg_path, secret_backend=secrets)

    store.save_recent_server("https://ecs-a.example.com:8443", "ops_admin")
    store.save_refresh_token("https://ecs-a.example.com:8443", "ops_admin", "rt_server_a_1234567890")
    store.save_refresh_token("https://ecs-b.example.com:8443", "ops_admin", "rt_server_b_1234567890")

    raw_json = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert raw_json["recent_server_url"] == "https://ecs-a.example.com:8443"
    assert "password" not in raw_json
    assert "access_token" not in raw_json
    assert "refresh_token" not in raw_json
    assert store.load_refresh_token("https://ecs-a.example.com:8443", "ops_admin") == "rt_server_a_1234567890"
    assert store.load_refresh_token("https://ecs-b.example.com:8443", "ops_admin") == "rt_server_b_1234567890"
    assert store.load_refresh_token("https://ecs-a.example.com:8443", "other_user") is None


def test_wrong_password_does_not_trigger_refresh(tmp_path: Path) -> None:
    refresh_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal refresh_calls
        if request.url.path == "/api/v1/health":
            return httpx.Response(200, json=_health_payload("ecs-a"))
        if request.url.path == "/api/v1/auth/login":
            return httpx.Response(
                401,
                json={
                    "error": {
                        "code": "INVALID_CREDENTIALS",
                        "message": "Invalid username or password.",
                        "retryable": False,
                        "details": [],
                        "request_id": "req_bad_pwd",
                    }
                },
            )
        if request.url.path == "/api/v1/auth/refresh":
            refresh_calls += 1
            return httpx.Response(200, json=_token_payload("new", "new_r"))
        return httpx.Response(404)

    store = CredentialStore(config_path=tmp_path / "cfg.json", secret_backend=MemorySecretBackend())
    auth = AuthCoordinator(credential_store=store)
    client = FlightLinkApiClient(auth, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(ApiError) as exc_info:
            client.login("http://127.0.0.1:8000", "ops_admin", "wrong_pass")
        assert exc_info.value.status_code == 401
        assert exc_info.value.code == "INVALID_CREDENTIALS"
        assert refresh_calls == 0
        assert not auth.snapshot().is_authenticated
    finally:
        client.close()


def test_concurrent_detail_and_archive_token_expired_triggers_single_refresh(tmp_path: Path) -> None:
    lock = threading.Lock()
    refresh_calls = 0
    detail_attempts = 0
    archive_attempts = 0
    both_expired_barrier = threading.Barrier(2)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal refresh_calls, detail_attempts, archive_attempts
        path = request.url.path
        auth_header = request.headers.get("Authorization", "")

        if path == "/api/v1/health":
            return httpx.Response(200, json=_health_payload("ecs-a"))
        if path == "/api/v1/auth/login":
            return httpx.Response(200, json=_token_payload("tok_expired_1", "ref_1_long_token_1234"))
        if path == "/api/v1/auth/refresh":
            time.sleep(0.05)  # Give concurrent waiter time to block on single-flight lock
            with lock:
                refresh_calls += 1
            return httpx.Response(200, json=_token_payload("tok_fresh_2", "ref_2_long_token_5678"))
        if path == "/api/v1/groups/grp_1":
            with lock:
                detail_attempts += 1
            if auth_header == "Bearer tok_expired_1":
                both_expired_barrier.wait(timeout=3.0)
                return httpx.Response(
                    401,
                    json={
                        "error": {
                            "code": "TOKEN_EXPIRED",
                            "message": "Access token expired",
                            "retryable": False,
                            "request_id": "req_exp_detail",
                        }
                    },
                )
            assert auth_header == "Bearer tok_fresh_2"
            return httpx.Response(200, json={"group_id": "grp_1", "name": "一号机"}, headers={"ETag": '"v1"'})
        if path == "/api/v1/archive/changes":
            with lock:
                archive_attempts += 1
            if auth_header == "Bearer tok_expired_1":
                both_expired_barrier.wait(timeout=3.0)
                return httpx.Response(
                    401,
                    json={
                        "error": {
                            "code": "TOKEN_EXPIRED",
                            "message": "Access token expired",
                            "retryable": False,
                            "request_id": "req_exp_arch",
                        }
                    },
                )
            assert auth_header == "Bearer tok_fresh_2"
            return httpx.Response(
                200,
                json={
                    "ecs_instance_id": "ecs-a",
                    "retention_seconds": 604800,
                    "items": [],
                    "next_cursor": "cur_1",
                    "has_more": False,
                    "observed_at": "2026-11-27T08:00:00Z",
                },
            )
        return httpx.Response(404)

    store = CredentialStore(config_path=tmp_path / "cfg.json", secret_backend=MemorySecretBackend())
    auth = AuthCoordinator(credential_store=store)
    client = FlightLinkApiClient(auth, transport=httpx.MockTransport(handler))
    try:
        client.login("http://127.0.0.1:8000", "ops_admin", "StrongPass!2026")
        results: dict[str, Any] = {}
        errors: list[Exception] = []

        def run_detail() -> None:
            try:
                results["detail"] = client.get_group("grp_1").data
            except Exception as exc:
                errors.append(exc)

        def run_archive() -> None:
            try:
                results["archive"] = client.list_archive_changes()
            except Exception as exc:
                errors.append(exc)

        t1 = threading.Thread(target=run_detail)
        t2 = threading.Thread(target=run_archive)
        t1.start()
        t2.start()
        t1.join(timeout=5.0)
        t2.join(timeout=5.0)

        assert not errors, f"Unexpected errors: {errors}"
        assert refresh_calls == 1, f"Expected single-flight refresh (1), got {refresh_calls}"
        assert detail_attempts == 2
        assert archive_attempts == 2
        assert results["detail"]["group_id"] == "grp_1"
        assert results["archive"]["next_cursor"] == "cur_1"
    finally:
        client.close()


def test_refresh_failure_clears_session_and_notifies_expiry(tmp_path: Path) -> None:
    expired_events: list[tuple[int, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/health":
            return httpx.Response(200, json=_health_payload("ecs-a"))
        if request.url.path == "/api/v1/auth/login":
            return httpx.Response(200, json=_token_payload("tok_old", "ref_revoked_12345678"))
        if request.url.path == "/api/v1/overview":
            return httpx.Response(
                401,
                json={"error": {"code": "TOKEN_EXPIRED", "message": "expired", "retryable": False, "request_id": "r1"}},
            )
        if request.url.path == "/api/v1/auth/refresh":
            return httpx.Response(
                401,
                json={"error": {"code": "TOKEN_EXPIRED", "message": "refresh expired", "retryable": False, "request_id": "r2"}},
            )
        return httpx.Response(404)

    secrets = MemorySecretBackend()
    store = CredentialStore(config_path=tmp_path / "cfg.json", secret_backend=secrets)
    auth = AuthCoordinator(
        credential_store=store,
        on_session_expired=lambda ep, reason: expired_events.append((ep, reason)),
    )
    client = FlightLinkApiClient(auth, transport=httpx.MockTransport(handler))
    try:
        client.login("http://127.0.0.1:8000", "ops_admin", "StrongPass!2026", remember_refresh=True)
        assert store.load_refresh_token("http://127.0.0.1:8000", "ops_admin") == "ref_revoked_12345678"

        with pytest.raises(ApiError) as exc_info:
            client.get_overview()
        assert exc_info.value.status_code == 401
        assert not auth.snapshot().is_authenticated
        assert store.load_refresh_token("http://127.0.0.1:8000", "ops_admin") is None
        assert len(expired_events) == 1
    finally:
        client.close()


def test_switching_server_a_to_b_discards_late_response_and_isolates_tokens(tmp_path: Path) -> None:
    server_a_started = threading.Event()
    release_server_a = threading.Event()
    seen_server_b_tokens: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        path = request.url.path
        if host == "ecs-a.example.com":
            if path == "/api/v1/health":
                return httpx.Response(200, json=_health_payload("ecs-A"))
            if path == "/api/v1/auth/login":
                return httpx.Response(200, json=_token_payload("tok_server_A", "ref_A_123456789012"))
            if path == "/api/v1/overview":
                server_a_started.set()
                release_server_a.wait(timeout=5.0)
                return httpx.Response(200, json={"ecs_instance_id": "ecs-A", "groups": [{"name": "A号机"}]})
        elif host == "ecs-b.example.com":
            if path == "/api/v1/health":
                return httpx.Response(200, json=_health_payload("ecs-B"))
            if path == "/api/v1/auth/login":
                return httpx.Response(200, json=_token_payload("tok_server_B", "ref_B_123456789012"))
            if path == "/api/v1/overview":
                seen_server_b_tokens.append(request.headers.get("Authorization", ""))
                return httpx.Response(200, json={"ecs_instance_id": "ecs-B", "groups": [{"name": "B号机"}]})
        return httpx.Response(404)

    store = CredentialStore(config_path=tmp_path / "cfg.json", secret_backend=MemorySecretBackend())
    auth = AuthCoordinator(credential_store=store)
    client = FlightLinkApiClient(auth, transport=httpx.MockTransport(handler))
    try:
        client.login("https://ecs-a.example.com", "ops_admin", "PassA")
        epoch_a = auth.current_epoch()
        late_outcome: list[Any] = []

        def slow_a_poll() -> None:
            try:
                data = client.get_overview(expected_epoch=epoch_a)
                late_outcome.append(("ok", data))
            except SessionInvalidatedError as exc:
                late_outcome.append(("discarded", str(exc)))

        worker_a = threading.Thread(target=slow_a_poll)
        worker_a.start()
        assert server_a_started.wait(timeout=3.0)

        # Switch to Server B and login while Server A request is still in-flight
        auth.switch_server("https://ecs-b.example.com")
        client.login("https://ecs-b.example.com", "ops_admin", "PassB")
        overview_b = client.get_overview()
        assert overview_b["ecs_instance_id"] == "ecs-B"
        assert seen_server_b_tokens == ["Bearer tok_server_B"]

        # Now release Server A's late response
        release_server_a.set()
        worker_a.join(timeout=3.0)
        assert len(late_outcome) == 1
        assert late_outcome[0][0] == "discarded"
    finally:
        client.close()


def test_viewer_blocked_from_server_writes_but_allowed_archive_reads(tmp_path: Path) -> None:
    write_called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal write_called
        if request.url.path == "/api/v1/health":
            return httpx.Response(200, json=_health_payload("ecs-v"))
        if request.url.path == "/api/v1/auth/login":
            return httpx.Response(200, json=_token_payload("tok_viewer", "ref_viewer_1234567", username="obs1", role="viewer"))
        if request.url.path == "/api/v1/groups" and request.method == "POST":
            write_called = True
            return httpx.Response(403, json={"error": {"code": "INSUFFICIENT_ROLE", "message": "forbidden", "retryable": False, "request_id": "r3"}})
        if request.url.path == "/api/v1/archive/changes":
            return httpx.Response(
                200,
                json={"ecs_instance_id": "ecs-v", "retention_seconds": 604800, "items": [], "next_cursor": None, "has_more": False, "observed_at": "2026-11-27T08:00:00Z"},
            )
        if request.url.path == "/api/v1/archive/sessions/sess_1/files/file_1":
            return httpx.Response(200, content=b"router log bytes", headers={"X-Content-SHA256": "abc"})
        return httpx.Response(404)

    store = CredentialStore(config_path=tmp_path / "cfg.json", secret_backend=MemorySecretBackend())
    auth = AuthCoordinator(credential_store=store)
    client = FlightLinkApiClient(auth, transport=httpx.MockTransport(handler))
    try:
        client.login("http://127.0.0.1:8000", "obs1", "ViewerPass!1")
        snap = auth.snapshot()
        assert not snap.is_admin
        assert snap.can_archive_sync

        with pytest.raises(ApiError) as exc_info:
            client.create_group(
                {"name": "一号机", "dtu_port": 5760, "gcs_protocol": "tcp", "gcs_port": 14552},
                idempotency_key="11111111-1111-4111-8111-111111111111",
            )
        assert exc_info.value.status_code == 403
        assert exc_info.value.code == "INSUFFICIENT_ROLE"
        assert not write_called

        changes = client.list_archive_changes()
        assert changes["ecs_instance_id"] == "ecs-v"
        with client.stream_authenticated("GET", "/api/v1/archive/sessions/sess_1/files/file_1") as resp:
            assert resp.status_code == 200
            assert resp.read() == b"router log bytes"
    finally:
        client.close()
