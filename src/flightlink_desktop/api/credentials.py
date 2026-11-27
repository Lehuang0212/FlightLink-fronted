"""Recent server config and Windows Credential Manager refresh-token storage."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol

import keyring
from keyring.errors import KeyringError

KEYRING_SERVICE = "FlightLinkDesktop1.0"


class SecretBackend(Protocol):
    def get_password(self, service: str, username: str) -> str | None: ...
    def set_password(self, service: str, username: str, password: str) -> None: ...
    def delete_password(self, service: str, username: str) -> None: ...


class KeyringSecretBackend:
    """Uses Windows Credential Manager via keyring (no plaintext password storage)."""

    def get_password(self, service: str, username: str) -> str | None:
        try:
            return keyring.get_password(service, username)
        except KeyringError:
            return None

    def set_password(self, service: str, username: str, password: str) -> None:
        try:
            keyring.set_password(service, username, password)
        except KeyringError:
            pass

    def delete_password(self, service: str, username: str) -> None:
        try:
            keyring.delete_password(service, username)
        except KeyringError:
            pass


def default_app_data_dir() -> Path:
    override = os.environ.get("FLIGHTLINK_DATA_DIR")
    if override:
        return Path(override)
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "FlightLink"
    return Path.home() / ".flightlink"


class CredentialStore:
    """Stores recent server address in JSON and refresh tokens in OS credential vault.

    Never stores plaintext passwords or access tokens on disk.
    """

    def __init__(
        self,
        *,
        config_path: Path | None = None,
        secret_backend: SecretBackend | None = None,
    ) -> None:
        self.config_path = config_path or (default_app_data_dir() / "client_config.json")
        self._secrets: SecretBackend = secret_backend or KeyringSecretBackend()

    @staticmethod
    def _token_account_key(server_url: str, username: str) -> str:
        return f"refresh|{server_url.rstrip('/')}|{username.strip()}"

    def _load_config(self) -> dict[str, object]:
        try:
            if self.config_path.exists():
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
        except (OSError, json.JSONDecodeError):
            pass
        return {}

    def _save_config(self, data: dict[str, object]) -> None:
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.config_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, self.config_path)
        except OSError:
            pass

    def get_recent_server(self) -> str:
        cfg = self._load_config()
        val = cfg.get("recent_server_url")
        return str(val) if isinstance(val, str) and val.strip() else ""

    def get_recent_username(self) -> str:
        cfg = self._load_config()
        val = cfg.get("recent_username")
        return str(val) if isinstance(val, str) and val.strip() else ""

    def save_recent_server(self, server_url: str, username: str | None = None) -> None:
        cfg = self._load_config()
        cfg["recent_server_url"] = server_url.rstrip("/")
        if username is not None:
            cfg["recent_username"] = username.strip()
        # Explicitly ensure no plaintext credentials ever enter config JSON
        cfg.pop("password", None)
        cfg.pop("access_token", None)
        cfg.pop("refresh_token", None)
        self._save_config(cfg)

    def save_refresh_token(self, server_url: str, username: str, refresh_token: str) -> None:
        if not server_url or not username or not refresh_token:
            return
        key = self._token_account_key(server_url, username)
        self._secrets.set_password(KEYRING_SERVICE, key, refresh_token)

    def load_refresh_token(self, server_url: str, username: str) -> str | None:
        if not server_url or not username:
            return None
        key = self._token_account_key(server_url, username)
        return self._secrets.get_password(KEYRING_SERVICE, key)

    def clear_refresh_token(self, server_url: str, username: str) -> None:
        if not server_url or not username:
            return
        key = self._token_account_key(server_url, username)
        self._secrets.delete_password(KEYRING_SERVICE, key)
