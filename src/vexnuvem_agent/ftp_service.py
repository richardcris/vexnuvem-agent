from __future__ import annotations

from dataclasses import dataclass
from ftplib import FTP, all_errors, error_perm
from pathlib import Path, PurePosixPath
import posixpath
import time

from .models import FtpServerConfig


@dataclass
class UploadResult:
    server_name: str
    remote_path: str


class FTPFailoverUploader:
    def __init__(self, logger) -> None:
        self.logger = logger

    def upload_file(
        self,
        archive_path: Path,
        servers: list[FtpServerConfig],
        max_retries: int,
        progress_callback=None,
    ) -> UploadResult:
        candidates = [server for server in servers if server.enabled and server.host]
        if not candidates:
            raise RuntimeError("Nenhum servidor FTP habilitado foi configurado.")

        last_error: Exception | None = None
        total_bytes = archive_path.stat().st_size

        for server in candidates:
            for attempt in range(1, max_retries + 1):
                try:
                    self.logger.info(
                        "Iniciando upload para %s (%s), tentativa %s/%s",
                        server.name,
                        server.host,
                        attempt,
                        max_retries,
                    )
                    with FTP() as ftp:
                        ftp.connect(server.host, server.port, timeout=30)
                        ftp.login(server.username, server.password)
                        ftp.set_pasv(server.passive_mode)
                        self._ensure_remote_directory(ftp, server.remote_dir)

                        sent_bytes = 0

                        def on_chunk(chunk: bytes) -> None:
                            nonlocal sent_bytes
                            sent_bytes += len(chunk)
                            if progress_callback:
                                progress_callback(sent_bytes, total_bytes, f"Enviando para {server.name}")

                        with archive_path.open("rb") as handle:
                            ftp.storbinary(
                                f"STOR {archive_path.name}",
                                handle,
                                blocksize=64 * 1024,
                                callback=on_chunk,
                            )

                    remote_path = posixpath.join(server.remote_dir.rstrip("/"), archive_path.name)
                    if not remote_path.startswith("/"):
                        remote_path = f"/{remote_path}"
                    self.logger.info("Upload concluido em %s", server.name)
                    return UploadResult(server_name=server.name, remote_path=remote_path)
                except all_errors as exc:
                    last_error = exc
                    self.logger.warning(
                        "Falha no upload para %s na tentativa %s/%s: %s",
                        server.name,
                        attempt,
                        max_retries,
                        exc,
                    )
                    time.sleep(2)

        raise RuntimeError(f"Todos os servidores FTP falharam. Ultimo erro: {last_error}")

    def _ensure_remote_directory(self, ftp: FTP, remote_dir: str) -> None:
        clean_path = remote_dir.strip() or "/"
        if clean_path == "/":
            ftp.cwd("/")
            return

        ftp.cwd("/")
        for part in PurePosixPath(clean_path).parts:
            if part in ("/", ""):
                continue
            try:
                ftp.cwd(part)
            except error_perm:
                ftp.mkd(part)
                ftp.cwd(part)
