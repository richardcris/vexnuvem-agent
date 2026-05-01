from __future__ import annotations

import os
from pathlib import Path


APP_NAME = "VexNuvem"


def _resolve_app_dir() -> Path:
    base = os.getenv("APPDATA")
    if base:
        root = Path(base) / APP_NAME
    else:
        root = Path.home() / f".{APP_NAME.lower()}"
    root.mkdir(parents=True, exist_ok=True)
    return root


APP_DIR = _resolve_app_dir()
LOG_DIR = APP_DIR / "logs"
ARCHIVE_DIR = APP_DIR / "archives"
TEMP_DIR = APP_DIR / "temp"
CONFIG_FILE = APP_DIR / "config.json"
DATABASE_FILE = APP_DIR / "history.sqlite3"
LOCAL_KEY_FILE = APP_DIR / "secret.key"
PENDING_UPDATE_NOTICE_FILE = APP_DIR / "pending_update_notice.json"
LOG_FILE = LOG_DIR / "vexnuvem.log"

for directory in (LOG_DIR, ARCHIVE_DIR, TEMP_DIR):
    directory.mkdir(parents=True, exist_ok=True)
