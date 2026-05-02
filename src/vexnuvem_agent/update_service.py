from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import subprocess
import re
import uuid

import requests

from . import __github_repository__
from .models import UpdateConfig


class UpdateCheckError(RuntimeError):
    pass


class UpdateInstallError(RuntimeError):
    pass


@dataclass
class UpdateInfo:
    current_version: str
    latest_version: str
    repository: str
    release_url: str
    asset_name: str = ""
    asset_url: str = ""
    asset_api_url: str = ""
    published_at: str = ""
    notes: str = ""
    auth_token: str = ""


@dataclass
class UpdateCheckResult:
    status: str
    message: str
    info: UpdateInfo | None = None


class GitHubUpdateService:
    API_TEMPLATE = "https://api.github.com/repos/{repository}/releases?per_page=10"

    def __init__(self, logger, timeout: float = 10.0) -> None:
        self.logger = logger
        self.timeout = timeout

    def check_for_updates(self, current_version: str, config: UpdateConfig) -> UpdateCheckResult:
        if not config.enabled:
            return UpdateCheckResult(status="disabled", message="Atualizacoes automaticas desativadas.")

        repository = self._normalize_repository(config.repository or __github_repository__)
        auth_token = (config.token or "").strip()
        if not repository:
            return UpdateCheckResult(
                status="unconfigured",
                message="Configure o repositorio GitHub do instalador para ativar as atualizacoes automaticas.",
            )

        payload = self._fetch_latest_release(repository, auth_token)
        latest_version = self._extract_version(payload.get("tag_name", ""))
        if not latest_version:
            latest_version = self._extract_version(payload.get("name", ""))
        if not latest_version:
            raise UpdateCheckError("A release mais recente nao possui uma versao valida no GitHub.")

        if self._compare_versions(latest_version, current_version) <= 0:
            return UpdateCheckResult(
                status="up_to_date",
                message=f"Voce ja esta na versao mais recente ({current_version}).",
            )

        asset_name, asset_url, asset_api_url = self._pick_release_asset(payload)
        info = UpdateInfo(
            current_version=current_version,
            latest_version=latest_version,
            repository=repository,
            release_url=payload.get("html_url", ""),
            asset_name=asset_name,
            asset_url=asset_url,
            asset_api_url=asset_api_url,
            published_at=payload.get("published_at", ""),
            notes=(payload.get("body") or "").strip(),
            auth_token=auth_token,
        )
        return UpdateCheckResult(
            status="update_available",
            message=f"Nova versao disponivel: {latest_version}",
            info=info,
        )

    def download_installer(
        self,
        info: UpdateInfo,
        destination_dir: Path,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> Path:
        auth_token = (info.auth_token or "").strip()
        asset_url = (info.asset_url or "").strip()
        asset_api_url = (info.asset_api_url or "").strip()
        use_api_download = bool(auth_token and asset_api_url)
        download_url = asset_api_url if use_api_download else asset_url
        asset_name = self._safe_asset_name(info)
        if not download_url:
            raise UpdateInstallError("A release nao possui um instalador para download automatico.")

        destination_dir.mkdir(parents=True, exist_ok=True)
        target_path = destination_dir / asset_name
        temp_path = target_path.with_suffix(target_path.suffix + ".download")
        headers = self._build_headers(
            auth_token,
            accept="application/octet-stream" if use_api_download else "application/vnd.github+json",
        )

        try:
            with requests.get(download_url, headers=headers, stream=True, timeout=60.0) as response:
                response.raise_for_status()
                total_bytes = int(response.headers.get("Content-Length", 0) or 0)
                received_bytes = 0
                if progress_callback:
                    progress_callback(received_bytes, total_bytes)
                with temp_path.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 256):
                        if chunk:
                            handle.write(chunk)
                            received_bytes += len(chunk)
                            if progress_callback:
                                progress_callback(received_bytes, total_bytes)
        except requests.RequestException as exc:
            self.logger.warning("Falha ao baixar instalador da release %s: %s", info.latest_version, exc)
            raise UpdateInstallError("Nao foi possivel baixar o instalador da nova versao.") from exc
        except OSError as exc:
            raise UpdateInstallError("Nao foi possivel gravar o instalador baixado no disco.") from exc

        temp_path.replace(target_path)
        if progress_callback:
            final_size = target_path.stat().st_size if target_path.exists() else 0
            progress_callback(final_size, final_size)
        return target_path

    def create_windows_upgrade_launcher(
        self,
        installer_path: Path,
        launcher_dir: Path,
        current_pid: int,
        restart_executable: str = "",
    ) -> Path:
        launcher_dir.mkdir(parents=True, exist_ok=True)
        launcher_path = launcher_dir / f"apply_update_{uuid.uuid4().hex}.cmd"
        log_path = launcher_dir / f"installer_{uuid.uuid4().hex}.log"
        restart_target = self._normalize_restart_executable(restart_executable)

        script = self._build_upgrade_script(
            installer_path=installer_path,
            current_pid=current_pid,
            log_path=log_path,
            restart_executable=restart_target,
        )
        launcher_path.write_text(script, encoding="utf-8")
        return launcher_path

    def launch_upgrade_launcher(self, launcher_path: Path) -> None:
        creation_flags = 0
        creation_flags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
        creation_flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        creation_flags |= getattr(subprocess, "DETACHED_PROCESS", 0)

        try:
            subprocess.Popen(
                ["cmd.exe", "/c", str(launcher_path)],
                creationflags=creation_flags,
                close_fds=True,
            )
        except OSError as exc:
            raise UpdateInstallError("Nao foi possivel iniciar o instalador da nova versao.") from exc

    def launch_installer(self, installer_path: Path) -> None:
        try:
            subprocess.Popen(
                [str(installer_path)],
                close_fds=True,
            )
        except OSError as exc:
            raise UpdateInstallError("Nao foi possivel abrir o instalador da nova versao.") from exc

    def _fetch_latest_release(self, repository: str, auth_token: str = "") -> dict:
        url = self.API_TEMPLATE.format(repository=repository)
        headers = self._build_headers(auth_token)
        try:
            response = requests.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            self.logger.warning("Falha ao consultar release mais recente em %s: %s", repository, exc)
            if status_code == 404 and not auth_token:
                raise UpdateCheckError(
                    f"Nao foi possivel consultar a release mais recente em {repository}. "
                    "Se o repositorio for privado, informe um token do GitHub com permissao Contents: Read."
                ) from exc
            if status_code in {401, 403}:
                raise UpdateCheckError(
                    "O GitHub recusou o acesso a release. Verifique se o token informado ainda e valido e tem permissao Contents: Read."
                ) from exc
            if status_code == 404:
                raise UpdateCheckError(
                    f"Nao foi possivel localizar a release mais recente em {repository}. "
                    "Verifique o nome do repositorio, o token configurado e se ja existe uma release publicada."
                ) from exc
        except requests.RequestException as exc:
            self.logger.warning("Falha ao consultar release mais recente em %s: %s", repository, exc)
            raise UpdateCheckError(f"Nao foi possivel consultar a release mais recente em {repository}.") from exc

        payload = response.json()
        if not isinstance(payload, list):
            raise UpdateCheckError("Resposta invalida do GitHub ao consultar releases.")

        for release in payload:
            if not isinstance(release, dict):
                continue
            if release.get("draft") or release.get("prerelease"):
                continue
            return release

        raise UpdateCheckError(
            f"Nao foi possivel localizar uma release publicada em {repository}. "
            "Verifique se ja existe uma release publicada no GitHub."
        )

    @staticmethod
    def _normalize_repository(raw_value: str) -> str:
        clean = (raw_value or "").strip()
        if not clean:
            return ""
        clean = clean.removeprefix("https://github.com/").removeprefix("http://github.com/")
        clean = clean.strip("/")
        parts = [part for part in clean.split("/") if part]
        if len(parts) < 2:
            return ""
        return f"{parts[0]}/{parts[1].removesuffix('.git')}"

    @staticmethod
    def _extract_version(raw_value: str) -> str:
        match = re.search(r"(\d+(?:\.\d+)+)", raw_value or "")
        return match.group(1) if match else ""

    @staticmethod
    def _pick_release_asset(payload: dict) -> tuple[str, str, str]:
        assets = payload.get("assets", []) if isinstance(payload, dict) else []
        if not isinstance(assets, list):
            return "", "", ""

        preferred = None
        fallback = None
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            name = str(asset.get("name", ""))
            browser_url = str(asset.get("browser_download_url", ""))
            api_url = str(asset.get("url", ""))
            if not name or (not browser_url and not api_url):
                continue
            lower_name = name.lower()
            if lower_name.endswith(".exe"):
                candidate = (name, browser_url, api_url)
                fallback = candidate
                if "setup" in lower_name or "installer" in lower_name:
                    preferred = candidate
                    break
        if preferred:
            return preferred
        if fallback:
            return fallback
        return "", "", ""

    @staticmethod
    def _build_headers(auth_token: str = "", accept: str = "application/vnd.github+json") -> dict[str, str]:
        headers = {
            "Accept": accept,
            "User-Agent": "VexNuvem-Agent-Updater",
        }
        token = (auth_token or "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    @staticmethod
    def _safe_asset_name(info: UpdateInfo) -> str:
        base_name = (info.asset_name or f"VexNuvem-Agent-Setup-{info.latest_version}.exe").strip()
        clean = re.sub(r"[^A-Za-z0-9._-]+", "-", base_name)
        return clean or f"VexNuvem-Agent-Setup-{info.latest_version}.exe"

    @staticmethod
    def _normalize_restart_executable(raw_value: str) -> str:
        candidate = (raw_value or "").strip()
        if not candidate:
            return ""
        path = Path(candidate)
        if path.suffix.lower() != ".exe":
            return ""
        return str(path)

    @staticmethod
    def _build_upgrade_script(
        installer_path: Path,
        current_pid: int,
        log_path: Path,
        restart_executable: str,
    ) -> str:
        installer = str(installer_path)
        log_file = str(log_path)
        restart = restart_executable.replace('"', '""')
        return (
            "@echo off\r\n"
            "setlocal\r\n"
            f"set \"TARGET_PID={current_pid}\"\r\n"
            f"set \"INSTALLER={installer}\"\r\n"
            f"set \"INSTALL_LOG={log_file}\"\r\n"
            f"set \"RESTART_EXE={restart}\"\r\n"
            "\r\n"
            ":wait_for_app\r\n"
            "tasklist /FI \"PID eq %TARGET_PID%\" | findstr /R /C:\" %TARGET_PID% \" >nul\r\n"
            "if not errorlevel 1 (\r\n"
            "  timeout /t 1 /nobreak >nul\r\n"
            "  goto wait_for_app\r\n"
            ")\r\n"
            "\r\n"
            "if not exist \"%INSTALLER%\" goto cleanup\r\n"
            "\"%INSTALLER%\" /SP- /SILENT /SUPPRESSMSGBOXES /NORESTART /CURRENTUSER /CLOSEAPPLICATIONS /FORCECLOSEAPPLICATIONS /NORESTARTAPPLICATIONS /LOG=\"%INSTALL_LOG%\"\r\n"
            "set \"INSTALL_EXIT=%ERRORLEVEL%\"\r\n"
            "if \"%INSTALL_EXIT%\"==\"0\" goto restart_app\r\n"
            "if \"%INSTALL_EXIT%\"==\"3010\" goto restart_app\r\n"
            "goto cleanup\r\n"
            "\r\n"
            ":restart_app\r\n"
            "if \"%RESTART_EXE%\" NEQ \"\" if exist \"%RESTART_EXE%\" start \"\" \"%RESTART_EXE%\"\r\n"
            "\r\n"
            ":cleanup\r\n"
            "if exist \"%INSTALLER%\" del /f /q \"%INSTALLER%\" >nul 2>nul\r\n"
            "del /f /q \"%~f0\" >nul 2>nul\r\n"
            "exit /b 0\r\n"
        )

    @classmethod
    def _compare_versions(cls, left: str, right: str) -> int:
        left_parts = cls._version_tuple(left)
        right_parts = cls._version_tuple(right)
        length = max(len(left_parts), len(right_parts))
        left_padded = left_parts + (0,) * (length - len(left_parts))
        right_padded = right_parts + (0,) * (length - len(right_parts))
        if left_padded == right_padded:
            return 0
        return 1 if left_padded > right_padded else -1

    @classmethod
    def _version_tuple(cls, raw_value: str) -> tuple[int, ...]:
        version = cls._extract_version(raw_value)
        if not version:
            raise UpdateCheckError(f"Versao invalida: {raw_value!r}")
        return tuple(int(part) for part in version.split("."))