import os
import sqlite3
from pathlib import Path
from threading import Lock

from .core import compact_context
from .models import ClaimResult


class ClaimMemoryStore:
    def __init__(self, database_path: str | None = None):
        path = database_path or os.getenv("MEMORY_DB_PATH", "claim_memory.db")
        self.database_path = path
        self._lock = Lock()
        if path != ":memory:":
            Path(path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self._create_table()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _create_table(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS claim_memory (
                    memory_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    claim_id TEXT,
                    status TEXT NOT NULL,
                    codes TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def save(self, result: ClaimResult) -> str:
        memory_id = f"MEM-{result.operation_id or result.patient_id}-{result.retry_count}"
        summary = compact_context(result.history)
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO claim_memory
                    (memory_id, patient_id, claim_id, status, codes, summary)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_id,
                    result.patient_id,
                    result.claim_id,
                    result.status,
                    ",".join(result.codes),
                    summary,
                ),
            )
        return memory_id

    def recent(self, limit: int = 10) -> list[dict[str, object]]:
        safe_limit = max(1, min(limit, 100))
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT memory_id, patient_id, claim_id, status, codes, summary, created_at
                FROM claim_memory
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        return [dict(row) for row in rows]


memory_store = ClaimMemoryStore()

