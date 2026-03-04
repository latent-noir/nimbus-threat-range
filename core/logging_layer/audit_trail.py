"""
Security-focused audit trail.

Captures security-relevant events (attacks, IDS alerts, firewall blocks)
in an append-only log. Uses the structured logging infrastructure to
write to the security.log domain file.
"""

from __future__ import annotations

import logging
from collections import deque
from typing import TYPE_CHECKING, Deque, List

from .log_config import get_domain_logger

if TYPE_CHECKING:
    from engine.event_bus import EventBus
    from events.base import BaseEvent


class AuditTrail:
    """
    Append-only security audit log.

    Subscribes to attack.* and security.* events and records them
    both in-memory and via the structured security logger.
    """

    SECURITY_PREFIXES = ("attack.", "security.")

    def __init__(self) -> None:
        self._entries: Deque[dict] = deque(maxlen=50_000)
        self._logger = get_domain_logger("security")

    # ── Public API ────────────────────────────────────────────

    def get_entries(self, last_n: int = 100) -> List[dict]:
        return list(self._entries)[-last_n:]

    def count(self) -> int:
        return len(self._entries)

    # ── Event Handling ────────────────────────────────────────

    def register_handlers(self, bus: EventBus) -> None:
        """Subscribe to security-scoped events."""
        from events.base import EventPriority
        bus.subscribe("attack.*", self.record, priority=EventPriority.LOW)
        bus.subscribe("security.*", self.record, priority=EventPriority.LOW)

    async def record(self, event: BaseEvent) -> None:
        """Append a security event to the audit trail."""
        entry = event.model_dump()
        entry["_audit"] = True
        self._entries.append(entry)

        # Also emit a structured log entry to security.log
        self._logger.warning(
            f"[AUDIT] {entry.get('event_type', 'unknown')}",
            extra={
                "event_type": entry.get("event_type", "unknown"),
                "resource_id": getattr(event, "target_id", None)
                    or getattr(event, "blocked_source", None),
                "severity": "critical",
                "metrics_snapshot": None,
                "extra_data": entry,
            },
        )
