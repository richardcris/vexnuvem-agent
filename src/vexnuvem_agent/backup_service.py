from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import threading
import zipfile

from .api_client import MonitoringApiClient
from .config import ConfigManager, normalize_filters
from .ftp_service import FTPFailoverUploader
from .models import AppConfig, BackupSource
from .paths import ARCHIVE_DIR
from .storage import BackupHistoryStore
from .system_info import collect_system_snapshot


COMPRESSED_EXTENSIONS = {
    ".7z",
    ".avi",
    ".gz",
    ".jpg",
    ".jpeg",
    ".mp3",
    ".mp4",
    ".pdf",
    ".png",
    ".rar",
    ".zip",
}


def format_bytes(size_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size_bytes)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{size_bytes} B"


class BackupEngine:
    def __init__(
        self,
        config_manager: ConfigManager,
        history_store: BackupHistoryStore,
        ftp_uploader: FTPFailoverUploader,
        api_client: MonitoringApiClient,
        logger,
    ) -> None:
        self.config_manager = config_manager
        self.history_store = history_store
        self.ftp_uploader = ftp_uploader
        self.api_client = api_client
        self.logger = logger
        self._lock = threading.Lock()

    def run_backup(self, trigger: str = "manual", progress_callback=None) -> dict[str, str | int]:
        if not self._lock.acquire(blocking=False):
            raise RuntimeError("Ja existe um backup em andamento.")

        started_at = datetime.now()
        config: AppConfig | None = None
        archive_path: Path | None = None
        archive_size = 0

        try:
            config = self.config_manager.load()
            self._emit_progress(progress_callback, 4, "Lendo configuracoes")

            if not config.sources:
                raise RuntimeError("Nenhuma pasta ou arquivo foi configurado para backup.")

            files = self._collect_files(config.sources, config.filters)
            if not files:
                filters_text = ", ".join(config.filters) if config.filters else "todos os arquivos"
                raise RuntimeError(
                    "Nenhum arquivo compativel foi encontrado nas fontes configuradas. "
                    f"Filtros atuais: {filters_text}. "
                    "Limpe os filtros para incluir todo o conteudo da pasta ou adicione as extensoes desejadas."
                )

            total_input_bytes = sum(item[0].stat().st_size for item in files)
            archive_path = ARCHIVE_DIR / self._build_archive_name(config, started_at)

            self._emit_progress(progress_callback, 10, "Compactando arquivos")
            self._create_archive(
                files=files,
                archive_path=archive_path,
                compression_level=config.compression_level,
                total_input_bytes=total_input_bytes,
                progress_callback=progress_callback,
            )
            archive_size = archive_path.stat().st_size

            self._emit_progress(progress_callback, 58, f"Arquivo gerado: {archive_path.name}")
            upload_result = self.ftp_uploader.upload_file(
                archive_path=archive_path,
                servers=config.ftp_servers,
                max_retries=max(config.max_retries, 1),
                progress_callback=lambda sent, total, message: self._emit_upload_progress(
                    progress_callback,
                    sent,
                    total,
                    message,
                ),
            )

            finished_at = datetime.now()
            config.last_backup_at = finished_at.isoformat(timespec="seconds")
            config.last_backup_status = "Sucesso"
            self.config_manager.save(config)

            record = {
                "started_at": started_at.isoformat(timespec="seconds"),
                "finished_at": finished_at.isoformat(timespec="seconds"),
                "status": "success",
                "trigger_type": trigger,
                "archive_path": str(archive_path),
                "size_bytes": archive_size,
                "ftp_server": upload_result.server_name,
                "remote_path": upload_result.remote_path,
                "error_message": "",
            }
            self.history_store.add_record(record)
            self._notify_api(
                config=config,
                status="success",
                trigger=trigger,
                started_at=started_at,
                finished_at=finished_at,
                size_bytes=archive_size,
                archive_path=archive_path,
                ftp_server=upload_result.server_name,
                remote_path=upload_result.remote_path,
                error_message="",
            )
            self.logger.info("Backup concluido com sucesso em %s", upload_result.server_name)
            self._emit_progress(progress_callback, 100, "Backup concluido")
            return {
                "status": "success",
                "archive_path": str(archive_path),
                "size_bytes": archive_size,
                "ftp_server": upload_result.server_name,
                "remote_path": upload_result.remote_path,
                "finished_at": finished_at.isoformat(timespec="seconds"),
            }
        except Exception as exc:
            finished_at = datetime.now()
            error_message = str(exc)
            self.logger.error("Falha no backup: %s", error_message)
            if config is None:
                config = self.config_manager.load()
            config.last_backup_at = finished_at.isoformat(timespec="seconds")
            config.last_backup_status = f"Erro: {error_message}"
            self.config_manager.save(config)
            self.history_store.add_record(
                {
                    "started_at": started_at.isoformat(timespec="seconds"),
                    "finished_at": finished_at.isoformat(timespec="seconds"),
                    "status": "error",
                    "trigger_type": trigger,
                    "archive_path": str(archive_path) if archive_path else "",
                    "size_bytes": archive_size,
                    "ftp_server": "",
                    "remote_path": "",
                    "error_message": error_message,
                }
            )
            self._notify_api(
                config=config,
                status="error",
                trigger=trigger,
                started_at=started_at,
                finished_at=finished_at,
                size_bytes=archive_size,
                archive_path=archive_path,
                ftp_server="",
                remote_path="",
                error_message=error_message,
            )
            raise
        finally:
            self._lock.release()

    def _collect_files(
        self,
        sources: list[BackupSource],
        filters: list[str],
    ) -> list[tuple[Path, str]]:
        allowed_filters = set(normalize_filters(filters))
        collected: list[tuple[Path, str]] = []
        seen: set[str] = set()

        for source in sources:
            source_path = Path(source.path).expanduser()
            if not source_path.exists():
                self.logger.warning("Fonte ignorada porque nao existe: %s", source.path)
                continue

            if source_path.is_file():
                if self._matches_filters(source_path, allowed_filters):
                    resolved = str(source_path.resolve())
                    if resolved not in seen:
                        collected.append((source_path, source_path.name))
                        seen.add(resolved)
                continue

            for file_path in source_path.rglob("*"):
                if not file_path.is_file() or not self._matches_filters(file_path, allowed_filters):
                    continue
                resolved = str(file_path.resolve())
                if resolved in seen:
                    continue
                arcname = str(Path(source_path.name) / file_path.relative_to(source_path))
                collected.append((file_path, arcname))
                seen.add(resolved)

        return collected

    def _create_archive(
        self,
        files: list[tuple[Path, str]],
        archive_path: Path,
        compression_level: int,
        total_input_bytes: int,
        progress_callback=None,
    ) -> None:
        processed = 0
        with zipfile.ZipFile(
            archive_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=max(1, min(compression_level, 9)),
        ) as zip_handle:
            for file_path, arcname in files:
                compression = self._smart_compression_type(file_path)
                zip_handle.write(file_path, arcname=arcname, compress_type=compression)
                processed += file_path.stat().st_size
                progress = 10 + int((processed / max(total_input_bytes, 1)) * 45)
                self._emit_progress(progress_callback, progress, f"Compactando {file_path.name}")

    def _notify_api(
        self,
        config: AppConfig,
        status: str,
        trigger: str,
        started_at: datetime,
        finished_at: datetime,
        size_bytes: int,
        archive_path: Path | None,
        ftp_server: str,
        remote_path: str,
        error_message: str,
    ) -> None:
        system_snapshot = collect_system_snapshot()
        payload = {
            "client_id": config.client_id,
            "status": status,
            "file_size": size_bytes,
            "date": self._to_api_datetime(finished_at),
            "ip": system_snapshot.get("ip_address", "127.0.0.1"),
        }
        if error_message:
            payload["error_message"] = error_message
        self.api_client.send_backup_status(config.api, payload)

    @staticmethod
    def _matches_filters(file_path: Path, filters: set[str]) -> bool:
        if not filters:
            return True
        return file_path.suffix.lower() in filters

    @staticmethod
    def _smart_compression_type(file_path: Path) -> int:
        return zipfile.ZIP_STORED if file_path.suffix.lower() in COMPRESSED_EXTENSIONS else zipfile.ZIP_DEFLATED

    @staticmethod
    def _build_archive_name(config: AppConfig, started_at: datetime) -> str:
        safe_name = "".join(char if char.isalnum() else "_" for char in config.client_name).strip("_")
        safe_name = safe_name or config.client_id
        return f"{safe_name}_{started_at:%Y%m%d_%H%M%S}.zip"

    @staticmethod
    def _emit_progress(progress_callback, percent: int, message: str) -> None:
        if progress_callback:
            progress_callback(max(0, min(percent, 100)), message)

    def _emit_upload_progress(self, progress_callback, sent_bytes: int, total_bytes: int, message: str) -> None:
        percent = 60 + int((sent_bytes / max(total_bytes, 1)) * 35)
        self._emit_progress(progress_callback, percent, message)

    @staticmethod
    def _to_api_datetime(value: datetime) -> str:
        return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
