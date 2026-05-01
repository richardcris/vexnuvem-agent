from __future__ import annotations

import json
from pathlib import Path

from .models import AppConfig
from .paths import CONFIG_FILE
from .security import decrypt_text, encrypt_text


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
