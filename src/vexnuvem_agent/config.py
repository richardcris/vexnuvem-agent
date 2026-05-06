from __future__ import annotations

import json
from pathlib import Path

from .models import AppConfig, ApiConfig, FtpServerConfig
from .paths import CONFIG_FILE
from .security import decrypt_text, encrypt_text

# ---------------------------------------------------------------------------
# Padroes de fabrica — aplicados apenas na primeira execucao (sem config.json)
# ---------------------------------------------------------------------------
_DEFAULT_API_ENDPOINT = "https://vex-cloud-pulse.base44.app/functions"

_DEFAULT_FTP_HOSTS = [
    "ftp58.nitroflare.com",
    "ftp59.nitroflare.com",
    "ftp60.nitroflare.com",
    "ftp61.nitroflare.com",
    "ftp62.nitroflare.com",
    "ftp63.nitroflare.com",
    "ftp64.nitroflare.com",
    "ftp65.nitroflare.com",
    "ftp66.nitroflare.com",
    "ftp67.nitroflare.com",
    "ftp68.nitroflare.com",
    "ftp69.nitroflare.com",
    "ftp72.nitroflare.com",
    "ftp73.nitroflare.com",
    "ftp76.nitroflare.com",
    "ftp77.nitroflare.com",
    "ftp78.nitroflare.com",
    "ftp79.nitroflare.com",
]


def _apply_factory_defaults(config: AppConfig) -> None:
    """Preenche servidores FTP e endpoint de API quando ainda nao configurados."""
    if not config.ftp_servers:
        config.ftp_servers = [
            FtpServerConfig(
                name=host.split(".")[0].upper(),
                host=host,
                port=21,
                username="",
                password="",
                remote_dir="/",
                passive_mode=True,
                enabled=True,
            )
            for host in _DEFAULT_FTP_HOSTS
        ]
    if not config.api.endpoint:
        config.api.endpoint = _DEFAULT_API_ENDPOINT


def normalize_filters(filters: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_filter in filters:
        clean = raw_filter.strip().lower().replace(" ", "")
        if not clean:
            continue
        if clean.startswith("*."):
            clean = clean[1:]
        elif clean.startswith("*"):
            clean = clean[1:]
        elif not clean.startswith("."):
            clean = f".{clean.lstrip('.') }"
        if clean not in seen:
            normalized.append(clean)
            seen.add(clean)
    return normalized


def filters_to_text(filters: list[str]) -> str:
    return ", ".join(normalize_filters(filters))


def text_to_filters(text: str) -> list[str]:
    return normalize_filters(text.split(","))


class ConfigManager:
    def __init__(self, config_path: Path = CONFIG_FILE) -> None:
        self.config_path = config_path

    def load(self) -> AppConfig:
        if not self.config_path.exists():
            config = AppConfig()
            _apply_factory_defaults(config)
            self.save(config)
            return config

        payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        config = AppConfig.from_dict(payload)
        config.filters = normalize_filters(config.filters)
        for server in config.ftp_servers:
            server.password = decrypt_text(server.password)
        config.api.token = decrypt_text(config.api.token)
        config.update.token = decrypt_text(config.update.token)
        config.auth.password = decrypt_text(config.auth.password)
        return config

    def save(self, config: AppConfig) -> None:
        config.filters = normalize_filters(config.filters)
        payload = config.to_dict()
        for server in payload["ftp_servers"]:
            server["password"] = encrypt_text(server.get("password", ""))
        payload["api"]["token"] = encrypt_text(payload["api"].get("token", ""))
        payload["update"]["token"] = encrypt_text(payload["update"].get("token", ""))
        payload["auth"]["password"] = encrypt_text(payload["auth"].get("password", ""))
        self.config_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
