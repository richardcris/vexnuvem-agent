from __future__ import annotations

from dataclasses import asdict, dataclass
import json

from .paths import PENDING_UPDATE_NOTICE_FILE


@dataclass
class PendingUpdateNotice:
    version: str
    previous_version: str = ""
    notes: str = ""
    published_at: str = ""
    release_url: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "PendingUpdateNotice":
        return cls(
            version=str(data.get("version", "") or ""),
            previous_version=str(data.get("previous_version", "") or ""),
            notes=str(data.get("notes", "") or ""),
            published_at=str(data.get("published_at", "") or ""),
            release_url=str(data.get("release_url", "") or ""),
        )

    def to_dict(self) -> dict:
        return asdict(self)


def save_pending_update_notice(notice: PendingUpdateNotice) -> None:
    PENDING_UPDATE_NOTICE_FILE.write_text(
        json.dumps(notice.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def load_pending_update_notice() -> PendingUpdateNotice | None:
    if not PENDING_UPDATE_NOTICE_FILE.exists():
        return None

    try:
        payload = json.loads(PENDING_UPDATE_NOTICE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        clear_pending_update_notice()
        return None

    if not isinstance(payload, dict):
        clear_pending_update_notice()
        return None

    notice = PendingUpdateNotice.from_dict(payload)
    return notice if notice.version else None


def clear_pending_update_notice() -> None:
    try:
        if PENDING_UPDATE_NOTICE_FILE.exists():
            PENDING_UPDATE_NOTICE_FILE.unlink()
    except OSError:
        pass