from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock


@dataclass
class IdempotencyRecord:
    status: str
    response: dict[str, object] | None
    created_at: str
    updated_at: str


class InMemoryIdempotencyStore:
    """In-memory idempotency store for request deduplication."""

    def __init__(self):
        self._lock = Lock()
        self._records: dict[str, IdempotencyRecord] = {}

    def begin(self, scope: str, key: str) -> tuple[str, dict[str, object] | None]:
        record_key = _build_record_key(scope, key)
        with self._lock:
            record = self._records.get(record_key)
            if record is None:
                now = _utc_now_iso()
                self._records[record_key] = IdempotencyRecord(
                    status="in_progress",
                    response=None,
                    created_at=now,
                    updated_at=now,
                )
                return "started", None

            if record.status == "completed" and record.response is not None:
                return "replay", dict(record.response)
            return "in_progress", None

    def complete(self, scope: str, key: str, response: dict[str, object]) -> None:
        record_key = _build_record_key(scope, key)
        with self._lock:
            existing = self._records.get(record_key)
            now = _utc_now_iso()
            if existing is None:
                self._records[record_key] = IdempotencyRecord(
                    status="completed",
                    response=dict(response),
                    created_at=now,
                    updated_at=now,
                )
                return
            existing.status = "completed"
            existing.response = dict(response)
            existing.updated_at = now

    def discard(self, scope: str, key: str) -> None:
        record_key = _build_record_key(scope, key)
        with self._lock:
            existing = self._records.get(record_key)
            if existing is None:
                return
            if existing.status == "in_progress":
                del self._records[record_key]


def _build_record_key(scope: str, key: str) -> str:
    return f"{scope}::{key}"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
