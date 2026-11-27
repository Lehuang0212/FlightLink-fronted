"""Idempotency-Key manager and 202 async operation polling state machine."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable

TERMINAL_OPERATION_STATUSES = frozenset({"succeeded", "failed", "needs_verification", "cancelled"})


class IntentKeyManager:
    """Generates one UUIDv4 Idempotency-Key per distinct user intent + payload.

    - Retrying the same payload (e.g., after timeout/lost response) reuses the exact same key.
    - Changing any field in the payload immediately rotates to a fresh UUIDv4 key.
    """

    def __init__(self, key_factory: Callable[[], str] | None = None) -> None:
        self._key_factory = key_factory or (lambda: str(uuid.uuid4()))
        self._keys: dict[str, tuple[str, str]] = {}  # scope -> (payload_fingerprint, key)

    @staticmethod
    def _fingerprint(payload: Any) -> str:
        return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))

    def key_for(self, scope: str, payload: Any) -> str:
        fp = self._fingerprint(payload)
        existing = self._keys.get(scope)
        if existing is not None and existing[0] == fp:
            return existing[1]
        new_key = self._key_factory()
        self._keys[scope] = (fp, new_key)
        return new_key

    def clear(self, scope: str) -> None:
        self._keys.pop(scope, None)

    def clear_all(self) -> None:
        self._keys.clear()


@dataclass
class TrackedOperation:
    operation_id: str
    group_id: str
    action: str
    status: str
    retryable: bool
    retry_hint: str
    error_code: str
    error_message: str
    steps: list[dict[str, Any]]
    started_monotonic: float
    epoch: int
    network_interrupted: bool = False

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_OPERATION_STATUSES

    def next_poll_interval_ms(self, now_monotonic: float) -> int:
        """Contract cadence: 500ms during first 5s, then 1500ms (1-2s) until terminal."""
        elapsed = max(0.0, now_monotonic - self.started_monotonic)
        return 500 if elapsed < 5.0 else 1500

    @classmethod
    def from_api(cls, op_data: dict[str, Any], *, epoch: int, now_monotonic: float | None = None) -> "TrackedOperation":
        now = now_monotonic if now_monotonic is not None else time.monotonic()
        return cls(
            operation_id=str(op_data.get("operation_id", "")),
            group_id=str(op_data.get("group_id", "")),
            action=str(op_data.get("action", "")),
            status=str(op_data.get("status", "pending")),
            retryable=bool(op_data.get("retryable", False)),
            retry_hint=str(op_data.get("retry_hint") or ""),
            error_code=str(op_data.get("error_code") or ""),
            error_message=str(op_data.get("error_message") or ""),
            steps=list(op_data.get("steps") or []),
            started_monotonic=now,
            epoch=epoch,
            network_interrupted=False,
        )

    def update_from_api(self, op_data: dict[str, Any]) -> None:
        self.status = str(op_data.get("status", self.status))
        self.retryable = bool(op_data.get("retryable", False))
        self.retry_hint = str(op_data.get("retry_hint") or "")
        self.error_code = str(op_data.get("error_code") or "")
        self.error_message = str(op_data.get("error_message") or "")
        self.steps = list(op_data.get("steps") or [])
        self.network_interrupted = False
