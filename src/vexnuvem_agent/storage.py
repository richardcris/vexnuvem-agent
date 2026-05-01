from __future__ import annotations

import sqlite3
from typing import Any

from .paths import DATABASE_FILE


class BackupHistoryStore:
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or str(DATABASE_FILE)
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS backup_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    status TEXT NOT NULL,
                    trigger_type TEXT NOT NULL,
                    archive_path TEXT,
                    size_bytes INTEGER NOT NULL DEFAULT 0,
                    ftp_server TEXT,
                    remote_path TEXT,
                    error_message TEXT
                )
                """
            )

    def add_record(self, record: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO backup_history (
                    started_at,
                    finished_at,
                    status,
                    trigger_type,
                    archive_path,
                    size_bytes,
                    ftp_server,
                    remote_path,
                    error_message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.get("started_at", ""),
                    record.get("finished_at", ""),
                    record.get("status", "error"),
                    record.get("trigger_type", "manual"),
                    record.get("archive_path", ""),
                    int(record.get("size_bytes", 0) or 0),
                    record.get("ftp_server", ""),
                    record.get("remote_path", ""),
                    record.get("error_message", ""),
                ),
            )

    def list_records(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM backup_history
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_summary(self) -> dict[str, Any]:
        with self._connect() as connection:
            summary = connection.execute(
                """
                SELECT
                    COUNT(*) AS total_backups,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_count,
                    SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS error_count,
                    COALESCE(SUM(size_bytes), 0) AS total_bytes
                FROM backup_history
                """
            ).fetchone()
            latest = connection.execute(
                """
                SELECT status, finished_at
                FROM backup_history
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()

        return {
            "total_backups": int(summary["total_backups"] or 0),
            "success_count": int(summary["success_count"] or 0),
            "error_count": int(summary["error_count"] or 0),
            "total_bytes": int(summary["total_bytes"] or 0),
            "last_status": latest["status"] if latest else "Nunca executado",
            "last_finished_at": latest["finished_at"] if latest else "",
        }
