"""Server URL normalization preserving explicit ports and enforcing valid schemes."""

from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit, urlunsplit

from flightlink_desktop.api.errors import UrlValidationError

DEFAULT_PORT = 8000
DEFAULT_SERVER_URL = "http://127.0.0.1:8000"


def is_loopback_host(host: str) -> bool:
    lowered = host.strip().lower().strip("[]")
    if lowered in ("localhost", "127.0.0.1", "::1"):
        return True
    try:
        return ipaddress.ip_address(lowered).is_loopback
    except ValueError:
        return False


def normalize_server_url(raw: str) -> str:
    """Normalize user-entered server URL.

    Rules:
    - Preserves any explicitly entered port (e.g. :18080, :8443).
    - Defaults to port 8000 when no port is given on HTTP or scheme-less input.
    - Keeps standard implicit port 443 when user enters https://host without port.
    - Strips trailing slash and optional trailing /api/v1 suffix so callers always
      append /api/v1 cleanly.
    - Supports remote HTTPS and loopback HTTP tunnels.
    """
    text = (raw or "").strip()
    if not text:
        raise UrlValidationError("请输入服务器地址。")

    had_scheme = "://" in text
    if not had_scheme:
        # Inspect host portion before any slash to decide default scheme
        host_port = text.split("/", 1)[0]
        host_only = host_port.rsplit(":", 1)[0] if ":" in host_port and not host_port.startswith("[") else host_port
        scheme = "http" if is_loopback_host(host_only) else "https"
        text = f"{scheme}://{text}"

    try:
        parts = urlsplit(text)
    except ValueError as exc:
        raise UrlValidationError(f"服务器地址格式无效：{exc}") from exc

    scheme = parts.scheme.lower()
    if scheme not in ("http", "https"):
        raise UrlValidationError("仅支持 http:// 或 https:// 服务器地址。")

    if not parts.hostname:
        raise UrlValidationError("服务器地址缺少主机名。")

    try:
        port = parts.port
    except ValueError as exc:
        raise UrlValidationError("端口号必须在 1 到 65535 之间。") from exc

    if port is not None and not (1 <= port <= 65535):
        raise UrlValidationError("端口号必须在 1 到 65535 之间。")

    host_str = parts.hostname
    if ":" in host_str and not host_str.startswith("["):
        host_str = f"[{host_str}]"

    if port is not None:
        netloc = f"{host_str}:{port}"
    elif scheme == "http" or not had_scheme:
        netloc = f"{host_str}:{DEFAULT_PORT}"
    else:
        # Explicit https://host without port preserves standard HTTPS (443)
        netloc = host_str

    path = parts.path.rstrip("/")
    if path.endswith("/api/v1"):
        path = path[: -len("/api/v1")]
    elif path == "/api":
        path = ""

    return urlunsplit((scheme, netloc, path, "", ""))
