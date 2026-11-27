"""Contract error types matching docs/api/openapi.yaml ErrorEnvelope."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FieldErrorDetail:
    field: str
    message: str


@dataclass
class ApiError(Exception):
    """Structured HTTP error returned by FlightLink ECS /api/v1."""

    status_code: int
    code: str
    message: str
    retryable: bool = False
    details: list[FieldErrorDetail] = field(default_factory=list)
    request_id: str = ""

    def __str__(self) -> str:
        req = f" [request_id={self.request_id}]" if self.request_id else ""
        return f"HTTP {self.status_code} {self.code}: {self.message}{req}"

    @classmethod
    def from_response(cls, status_code: int, payload: Any) -> "ApiError":
        if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
            err = payload["error"]
            raw_details = err.get("details") or []
            details = [
                FieldErrorDetail(
                    field=str(item.get("field", "")),
                    message=str(item.get("message", "")),
                )
                for item in raw_details
                if isinstance(item, dict)
            ]
            return cls(
                status_code=status_code,
                code=str(err.get("code") or f"HTTP_{status_code}"),
                message=str(err.get("message") or f"Request failed with HTTP {status_code}"),
                retryable=bool(err.get("retryable", False)),
                details=details,
                request_id=str(err.get("request_id") or ""),
            )
        return cls(
            status_code=status_code,
            code=f"HTTP_{status_code}",
            message=f"Unexpected HTTP {status_code} response",
            retryable=status_code >= 500,
        )


class NetworkError(Exception):
    """Transport-level network or TLS failure."""


class UrlValidationError(ValueError):
    """Invalid server address supplied by the user."""


class SessionInvalidatedError(Exception):
    """Raised when an in-flight response belongs to a stale session epoch."""
