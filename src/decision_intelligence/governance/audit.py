"""Append-only audit log — every optimization event is recorded here."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AuditEntry:
    event: str
    request_id: str
    payload: dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AuditLog:
    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def record(self, event: str, request_id: str, payload: dict[str, Any] | None = None) -> None:
        entry = AuditEntry(event=event, request_id=request_id, payload=payload or {})
        self._entries.append(entry)
        logger.debug("AUDIT %s request_id=%s %s", event, request_id, payload)

    def get_history(self, request_id: str) -> list[AuditEntry]:
        return [e for e in self._entries if e.request_id == request_id]

    def all_entries(self) -> list[AuditEntry]:
        return list(self._entries)
