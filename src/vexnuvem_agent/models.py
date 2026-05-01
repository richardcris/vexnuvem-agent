from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
import uuid


def _normalize_text_patterns(values: list[str], *, dot_prefix: bool = False) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        clean = str(raw_value or "").strip().lower()
        if not clean:
            continue
        if dot_prefix and not clean.startswith("."):
            clean = f".{clean.lstrip('.')}"
        if clean not in seen:
            normalized.append(clean)
            seen.add(clean)
    return normalized


@dataclass
class BackupSource:
    path: str
    source_type: str = "folder"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BackupSource":
        return cls(
            path=data.get("path", ""),
            source_type=data.get("source_type", "folder"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FtpServerConfig:
    name: str = "Servidor FTP"
    host: str = ""
    port: int = 21
    username: str = ""
    password: str = ""
    remote_dir: str = "/"
    passive_mode: bool = True
    enabled: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FtpServerConfig":
        return cls(
            name=data.get("name", "Servidor FTP"),
            host=data.get("host", ""),
            port=int(data.get("port", 21) or 21),
            username=data.get("username", ""),
            password=data.get("password", ""),
            remote_dir=data.get("remote_dir", "/"),
            passive_mode=bool(data.get("passive_mode", True)),
            enabled=bool(data.get("enabled", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScheduleConfig:
    enabled: bool = False
    mode: str = "daily"
    time_of_day: str = "22:00"
    interval_hours: int = 6
    weekdays: list[str] = field(default_factory=lambda: ["mon", "tue", "wed", "thu", "fri"])

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScheduleConfig":
        return cls(
            enabled=bool(data.get("enabled", False)),
            mode=data.get("mode", "daily"),
            time_of_day=data.get("time_of_day", "22:00"),
            interval_hours=int(data.get("interval_hours", 6) or 6),
            weekdays=list(data.get("weekdays", ["mon", "tue", "wed", "thu", "fri"])),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ApiConfig:
    enabled: bool = False
    endpoint: str = ""
    token: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ApiConfig":
        return cls(
            enabled=bool(data.get("enabled", False)),
            endpoint=data.get("endpoint", ""),
            token=data.get("token", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class UpdateConfig:
    enabled: bool = True
    repository: str = ""
    token: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UpdateConfig":
        return cls(
            enabled=bool(data.get("enabled", True)),
            repository=data.get("repository", ""),
            token=data.get("token", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AuthConfig:
    username: str = "admin"
    password: str = "admin"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuthConfig":
        return cls(
            username=data.get("username", "admin") or "admin",
            password=data.get("password", "admin") or "admin",
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProtectionConfig:
    enabled: bool = True
    auto_defender_scan: bool = True
    suspicious_event_threshold: int = 6
    suspicious_extensions: list[str] = field(
        default_factory=lambda: [
            ".akira",
            ".blackcat",
            ".cerber",
            ".clop",
            ".conti",
            ".crypt",
            ".crypted",
            ".cryx",
            ".enc",
            ".encrypted",
            ".lockbit",
            ".locked",
            ".ryk",
            ".ryuk",
            ".zepto",
        ]
    )
    ransom_note_names: list[str] = field(
        default_factory=lambda: [
            "decrypt_instructions.txt",
            "help_decrypt.txt",
            "how_to_restore_files.txt",
            "readme.txt",
            "recover-files.txt",
            "restore-your-files.txt",
        ]
    )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProtectionConfig":
        return cls(
            enabled=bool(data.get("enabled", True)),
            auto_defender_scan=bool(data.get("auto_defender_scan", True)),
            suspicious_event_threshold=max(2, int(data.get("suspicious_event_threshold", 6) or 6)),
            suspicious_extensions=_normalize_text_patterns(
                list(data.get("suspicious_extensions", cls().suspicious_extensions)),
                dot_prefix=True,
            ),
            ransom_note_names=_normalize_text_patterns(
                list(data.get("ransom_note_names", cls().ransom_note_names)),
                dot_prefix=False,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["suspicious_extensions"] = _normalize_text_patterns(self.suspicious_extensions, dot_prefix=True)
        payload["ransom_note_names"] = _normalize_text_patterns(self.ransom_note_names, dot_prefix=False)
        payload["suspicious_event_threshold"] = max(2, int(self.suspicious_event_threshold or 6))
        return payload


@dataclass
class AppConfig:
    client_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12].upper())
    client_name: str = "Novo Cliente"
    sources: list[BackupSource] = field(default_factory=list)
    filters: list[str] = field(default_factory=lambda: [".fdb", ".sql", ".zip"])
    ftp_servers: list[FtpServerConfig] = field(default_factory=list)
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)
    api: ApiConfig = field(default_factory=ApiConfig)
    update: UpdateConfig = field(default_factory=UpdateConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)
    protection: ProtectionConfig = field(default_factory=ProtectionConfig)
    max_retries: int = 3
    compression_level: int = 6
    run_in_background: bool = True
    start_with_windows: bool = False
    last_backup_at: str = ""
    last_backup_status: str = "Nunca executado"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        return cls(
            client_id=data.get("client_id") or uuid.uuid4().hex[:12].upper(),
            client_name=data.get("client_name", "Novo Cliente"),
            sources=[BackupSource.from_dict(item) for item in data.get("sources", [])],
            filters=list(data.get("filters", [".fdb", ".sql", ".zip"])),
            ftp_servers=[FtpServerConfig.from_dict(item) for item in data.get("ftp_servers", [])],
            schedule=ScheduleConfig.from_dict(data.get("schedule", {})),
            api=ApiConfig.from_dict(data.get("api", {})),
            update=UpdateConfig.from_dict(data.get("update", {})),
            auth=AuthConfig.from_dict(data.get("auth", {})),
            protection=ProtectionConfig.from_dict(data.get("protection", {})),
            max_retries=int(data.get("max_retries", 3) or 3),
            compression_level=int(data.get("compression_level", 6) or 6),
            run_in_background=bool(data.get("run_in_background", True)),
            start_with_windows=bool(data.get("start_with_windows", False)),
            last_backup_at=data.get("last_backup_at", ""),
            last_backup_status=data.get("last_backup_status", "Nunca executado"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "client_id": self.client_id,
            "client_name": self.client_name,
            "sources": [item.to_dict() for item in self.sources],
            "filters": list(self.filters),
            "ftp_servers": [item.to_dict() for item in self.ftp_servers],
            "schedule": self.schedule.to_dict(),
            "api": self.api.to_dict(),
            "update": self.update.to_dict(),
            "auth": self.auth.to_dict(),
            "protection": self.protection.to_dict(),
            "max_retries": self.max_retries,
            "compression_level": self.compression_level,
            "run_in_background": self.run_in_background,
            "start_with_windows": self.start_with_windows,
            "last_backup_at": self.last_backup_at,
            "last_backup_status": self.last_backup_status,
        }
