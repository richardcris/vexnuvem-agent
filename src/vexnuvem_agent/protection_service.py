from __future__ import annotations

from collections import deque
from pathlib import Path
import os
import subprocess
import threading
import time

from PySide6.QtCore import QObject, Signal
from watchdog.events import FileSystemEvent, FileSystemEventHandler, FileSystemMovedEvent
from watchdog.observers import Observer

from .models import AppConfig, ProtectionConfig


RANSOM_NOTE_EXTENSIONS = {".hta", ".html", ".md", ".txt", ".url"}
RANSOM_NOTE_KEYWORDS = ("decrypt", "help", "ransom", "recover", "restore")
SUSPICIOUS_EVENT_WINDOW_SECONDS = 20.0
ALERT_COOLDOWN_SECONDS = 120.0
DEFENDER_SCAN_COOLDOWN_SECONDS = 300.0


class _ProtectionEventHandler(FileSystemEventHandler):
    def __init__(self, service: "RansomwareProtectionService") -> None:
        super().__init__()
        self.service = service

    def on_created(self, event: FileSystemEvent) -> None:
        self._forward(event, "created")

    def on_modified(self, event: FileSystemEvent) -> None:
        self._forward(event, "modified")

    def on_moved(self, event: FileSystemMovedEvent) -> None:
        self._forward(event, "moved", raw_path=event.dest_path)

    def _forward(self, event: FileSystemEvent, event_type: str, raw_path: str | None = None) -> None:
        if event.is_directory:
            return
        self.service.handle_filesystem_event(Path(raw_path or event.src_path), event_type)


class RansomwareProtectionService(QObject):
    status_changed = Signal(str)
    threat_detected = Signal(object)

    def __init__(self, logger) -> None:
        super().__init__()
        self.logger = logger
        self._config = ProtectionConfig()
        self._observer: Observer | None = None
        self._watch_roots: list[Path] = []
        self._status_message = "Protecao anti-ransomware aguardando configuracao."
        self._last_alert_time = 0.0
        self._last_defender_scan_time = 0.0
        self._scan_lock = threading.Lock()
        self._suspicious_events: deque[float] = deque()
        self._set_status(self._status_message)

    @property
    def status_message(self) -> str:
        return self._status_message

    def apply_config(self, config: AppConfig) -> None:
        protection = ProtectionConfig.from_dict(config.protection.to_dict())
        roots = self._resolve_watch_roots(config)
        self._config = protection
        self._restart_observer(roots)

    def shutdown(self) -> None:
        observer = self._observer
        self._observer = None
        if observer is None:
            return
        observer.stop()
        observer.join(timeout=3)

    def trigger_manual_defender_scan(self) -> tuple[bool, str]:
        return self._launch_defender_quick_scan(manual=True)

    def handle_filesystem_event(self, path: Path, event_type: str) -> None:
        if not self._config.enabled:
            return

        lowered_name = path.name.lower()
        lowered_suffix = path.suffix.lower()

        if self._looks_like_ransom_note(lowered_name, lowered_suffix):
            self._emit_detection(
                path=path,
                reason="Arquivo com padrao de pedido de resgate foi detectado.",
                immediate=True,
            )
            return

        if lowered_suffix in set(self._config.suspicious_extensions):
            self._emit_detection(
                path=path,
                reason=f"Extensao suspeita detectada apos evento {event_type}.",
                immediate=False,
            )

    def _restart_observer(self, roots: list[Path]) -> None:
        self.shutdown()
        self._watch_roots = roots
        self._suspicious_events.clear()

        if not self._config.enabled:
            self._set_status("Protecao anti-ransomware desativada.")
            return

        if not roots:
            self._set_status("Protecao ativa, mas sem pastas validas para monitorar.")
            return

        observer = Observer(timeout=1.0)
        handler = _ProtectionEventHandler(self)
        try:
            for root in roots:
                observer.schedule(handler, str(root), recursive=True)
            observer.start()
        except Exception:
            observer.stop()
            observer.join(timeout=3)
            self.logger.exception("Falha ao iniciar o monitor anti-ransomware")
            self._set_status("Falha ao iniciar o monitor anti-ransomware.")
            return

        self._observer = observer
        self._set_status(f"Protecao anti-ransomware ativa em {len(roots)} pasta(s).")

    def _emit_detection(self, path: Path, reason: str, *, immediate: bool) -> None:
        now = time.monotonic()
        if immediate:
            should_alert = True
        else:
            self._suspicious_events.append(now)
            self._prune_suspicious_events(now)
            should_alert = len(self._suspicious_events) >= max(2, self._config.suspicious_event_threshold)

        if not should_alert or (now - self._last_alert_time) < ALERT_COOLDOWN_SECONDS:
            return

        self._last_alert_time = now
        defender_ok = False
        defender_message = ""
        if self._config.auto_defender_scan:
            defender_ok, defender_message = self._launch_defender_quick_scan(manual=False)

        message = f"Possivel ransomware detectado em {path}. {reason}"
        if defender_message:
            message = f"{message} {defender_message}"

        self.logger.warning(message)
        payload = {
            "path": str(path),
            "reason": reason,
            "message": message,
            "defender_triggered": defender_ok,
        }
        self._set_status(message)
        self.threat_detected.emit(payload)

    def _launch_defender_quick_scan(self, *, manual: bool) -> tuple[bool, str]:
        now = time.monotonic()
        with self._scan_lock:
            if not manual and (now - self._last_defender_scan_time) < DEFENDER_SCAN_COOLDOWN_SECONDS:
                return True, "A verificacao rapida do Microsoft Defender ja foi acionada recentemente."

            for command in self._build_defender_commands():
                try:
                    subprocess.Popen(
                        command,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                    self._last_defender_scan_time = now
                    return True, "Verificacao rapida do Microsoft Defender acionada."
                except FileNotFoundError:
                    continue
                except Exception as exc:
                    self.logger.warning("Falha ao iniciar verificacao rapida do Defender: %s", exc)
                    return False, f"Falha ao iniciar o Microsoft Defender: {exc}"

        return False, "Microsoft Defender nao encontrado para iniciar a verificacao rapida."

    @staticmethod
    def _build_defender_commands() -> list[list[str]]:
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        defender_cli = Path(program_files) / "Windows Defender" / "MpCmdRun.exe"
        commands: list[list[str]] = []
        if defender_cli.exists():
            commands.append([str(defender_cli), "-Scan", "-ScanType", "1"])
        commands.append([
            "powershell.exe",
            "-NoProfile",
            "-WindowStyle",
            "Hidden",
            "-Command",
            "Start-MpScan -ScanType QuickScan",
        ])
        return commands

    def _looks_like_ransom_note(self, lowered_name: str, lowered_suffix: str) -> bool:
        if lowered_name in set(self._config.ransom_note_names):
            return True
        if lowered_suffix not in RANSOM_NOTE_EXTENSIONS:
            return False
        return any(keyword in lowered_name for keyword in RANSOM_NOTE_KEYWORDS)

    def _prune_suspicious_events(self, now: float) -> None:
        cutoff = now - SUSPICIOUS_EVENT_WINDOW_SECONDS
        while self._suspicious_events and self._suspicious_events[0] < cutoff:
            self._suspicious_events.popleft()

    def _resolve_watch_roots(self, config: AppConfig) -> list[Path]:
        roots: list[Path] = []
        seen: set[Path] = set()
        for source in config.sources:
            candidate = Path(source.path)
            if source.source_type == "file":
                candidate = candidate.parent
            elif not candidate.is_dir() and candidate.exists():
                candidate = candidate.parent
            if not candidate.exists() or not candidate.is_dir():
                continue
            resolved = candidate.resolve()
            if resolved not in seen:
                seen.add(resolved)
                roots.append(resolved)
        return roots

    def _set_status(self, message: str) -> None:
        self._status_message = message
        self.status_changed.emit(message)