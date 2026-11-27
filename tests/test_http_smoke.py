"""P0 HTTP smoke test using httpx.MockTransport against /api/v1/health."""

from __future__ import annotations

import httpx


def test_health_endpoint_contract_with_mock_transport() -> None:
    observed_requests: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed_requests.append((request.method, str(request.url)))
        if request.url.path == "/api/v1/health":
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "version": "1.0.0",
                    "ecs_instance_id": "ecs-test-01",
                    "observed_at": "2026-11-27T08:00:00Z",
                    "db_ok": True,
                },
            )
        return httpx.Response(404, json={"error": {"code": "NOT_FOUND", "message": "not found", "retryable": False, "request_id": "req_1"}})

    transport = httpx.MockTransport(handler)
    with httpx.Client(base_url="http://127.0.0.1:8000", transport=transport) as client:
        resp = client.get("/api/v1/health")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ok"
    assert payload["ecs_instance_id"] == "ecs-test-01"
    assert payload["db_ok"] is True
    assert observed_requests == [("GET", "http://127.0.0.1:8000/api/v1/health")]
