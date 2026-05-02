from __future__ import annotations

from typing import Any
from urllib.parse import quote

import requests

from .models import ApiConfig


class MonitoringApiClient:
    def __init__(self, logger) -> None:
        self.logger = logger

    def send_backup_status(self, config: ApiConfig, payload: dict[str, Any]) -> tuple[bool, str]:
        if not config.enabled or not config.endpoint:
            return False, "monitoring_disabled"

        headers = self._build_headers(config, config.endpoint)
        candidate_requests = self._build_backup_requests(config.endpoint, payload)

        errors: list[str] = []
        for request_data in candidate_requests:
            try:
                response = requests.post(
                    request_data["url"],
                    json=request_data["json"],
                    headers=headers,
                    timeout=15,
                )
                response.raise_for_status()
                data = self._decode_json(response)
                message = str(data.get("message") or response.text[:200] or "ok")
                return True, message
            except requests.RequestException as exc:
                errors.append(str(exc))
                self.logger.warning("Falha ao enviar evento para API em %s: %s", request_data["url"], exc)
        return False, errors[0] if errors else "Falha desconhecida ao enviar evento para API"

    def fetch_client_status(self, config: ApiConfig, client_id: str) -> tuple[bool, dict[str, Any] | str]:
        if not config.enabled or not config.endpoint:
            return False, "monitoring_disabled"

        headers = self._build_headers(config, config.endpoint)
        candidate_requests = self._build_status_requests(config.endpoint, client_id)

        errors: list[str] = []
        for request_data in candidate_requests:
            try:
                method = request_data.get("method", "GET")
                if method == "POST":
                    response = requests.post(
                        request_data["url"],
                        json=request_data.get("json"),
                        headers=headers,
                        timeout=15,
                    )
                else:
                    response = requests.get(
                        request_data["url"],
                        params=request_data.get("params"),
                        headers=headers,
                        timeout=15,
                    )
                response.raise_for_status()
                return True, self._decode_json(response)
            except requests.RequestException as exc:
                errors.append(str(exc))
                self.logger.warning("Falha ao consultar status da API em %s: %s", request_data["url"], exc)
        return False, errors[0] if errors else "Falha desconhecida ao consultar status da API"

    @staticmethod
    def _build_headers(config: ApiConfig, endpoint: str) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if config.token:
            headers["Authorization"] = f"Bearer {config.token}"
        return headers

    @staticmethod
    def _build_url(endpoint: str, resource_path: str) -> str:
        base = endpoint.strip().rstrip("/")
        if base.endswith("/backup"):
            base = base[: -len("/backup")]
        elif "/status/" in base:
            base = base.split("/status/", 1)[0]
        return f"{base}{resource_path}"

    @classmethod
    def _build_backup_requests(cls, endpoint: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        base = endpoint.strip().rstrip("/")
        if cls._is_base44_functions_endpoint(base):
            return [
                {"url": f"{base}/receiveBackup", "json": payload},
                {"url": f"{base}/backup", "json": payload},
            ]
        return [{"url": cls._build_url(base, "/backup"), "json": payload}]

    @classmethod
    def _build_status_requests(cls, endpoint: str, client_id: str) -> list[dict[str, Any]]:
        base = endpoint.strip().rstrip("/")
        encoded_client_id = quote(client_id, safe="")
        if cls._is_base44_functions_endpoint(base):
            return [
                {"method": "POST", "url": f"{base}/clientStatus", "json": {"agent_id": client_id}},
                {"method": "POST", "url": f"{base}/clientStatus", "json": {"client_id": client_id}},
                {"url": f"{base}/clientStatus/{encoded_client_id}"},
                {"url": f"{base}/status/{encoded_client_id}"},
            ]
        return [{"url": cls._build_url(base, f"/status/{encoded_client_id}")}]

    @staticmethod
    def _is_base44_functions_endpoint(endpoint: str) -> bool:
        return endpoint.endswith("/functions") or "/functions/" in endpoint

    @staticmethod
    def _decode_json(response: requests.Response) -> dict[str, Any]:
        try:
            data = response.json()
            if isinstance(data, dict):
                return data
        except ValueError:
            pass
        return {"raw": response.text[:200]}
