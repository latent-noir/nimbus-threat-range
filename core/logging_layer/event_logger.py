"""
Domain-routed structured event logger.

Subscribes to ALL events on the EventBus and routes each event
to the correct domain log file based on its event_type prefix:

    infra.*     → infrastructure.log
    attack.*    → attacks.log
    security.*  → security.log

Each JSON log record includes: timestamp, event_type, resource_id,
severity, and a metrics_snapshot from the simulation engine.
"""

from __future__ import annotations

import logging
from collections import deque
from typing import TYPE_CHECKING, Any, Callable, Deque, Dict, List, Optional

from .log_config import get_domain_logger, setup_logging

if TYPE_CHECKING:
    from engine.event_bus import EventBus
    from events.base import BaseEvent


# ── Routing map: event_type prefix → logger domain ────────────
_ROUTE_TABLE: Dict[str, str] = {
    "infra.":    "infrastructure",
    "attack.":   "attacks",
    "security.": "security",
}


def _resolve_domain(event_type: str) -> str:
    """Map an event_type string to its logger domain."""
    for prefix, domain in _ROUTE_TABLE.items():
        if event_type.startswith(prefix):
            return domain
    return "infrastructure"  # fallback


def _extract_resource_id(event: BaseEvent) -> Optional[str]:
    """Pull the most relevant resource identifier from an event."""
    # Check common field names across event types
    for field in ("target_id", "container_id", "affected_subnet", "blocked_source"):
        val = getattr(event, field, None)
        if val:
            return val
    return None


def _severity_from_priority(priority: int) -> str:
    """Convert numeric EventPriority to a human-readable severity."""
    if priority <= 0:
        return "critical"
    elif priority <= 10:
        return "high"
    elif priority <= 20:
        return "medium"
    return "low"


class EventLogger:
    """
    Production-grade structured event logger.

    Responsibilities:
        1. Route events to the correct domain log file.
        2. Enrich log records with resource_id, severity, metrics.
        3. Maintain an in-memory rolling window for the API.
    """

    MAX_HISTORY = 10_000

    def __init__(
        self,
        metrics_provider: Optional[Callable[[], Dict[str, Any]]] = None,
        enable_console: bool = True,
    ) -> None:
        self._history: Deque[dict] = deque(maxlen=self.MAX_HISTORY)
        self._metrics_provider = metrics_provider
        self._loggers: Dict[str, logging.Logger] = setup_logging(console=enable_console)
        self._event_count: int = 0

    # ── Public API ────────────────────────────────────────────

    def get_recent(self, count: int = 50) -> List[dict]:
        """Return the N most recent events as dicts."""
        return list(self._history)[-count:]

    def get_by_type(self, event_type: str) -> List[dict]:
        """Filter events by type prefix."""
        return [e for e in self._history if e.get("event_type", "").startswith(event_type)]

    def get_by_domain(self, domain: str, count: int = 50) -> List[dict]:
        """Return events for a specific domain (infrastructure/attacks/security)."""
        prefix_map = {
            "infrastructure": "infra.",
            "attacks": "attack.",
            "security": "security.",
        }
        prefix = prefix_map.get(domain, domain)
        return [e for e in self._history if e.get("event_type", "").startswith(prefix)][-count:]

    @property
    def event_count(self) -> int:
        return self._event_count

    # ── Event Bus Integration ─────────────────────────────────

    def register_handlers(self, bus: EventBus) -> None:
        """Subscribe to every event for structured logging."""
        from events.base import EventPriority
        bus.subscribe("*", self.log_event, priority=EventPriority.LOW)

    async def log_event(self, event: BaseEvent) -> None:
        """
        Route a single event to the correct domain logger.

        Enriches the record with:
            - resource_id:      extracted from event fields
            - severity:         derived from event priority
            - metrics_snapshot: live metrics from the engine
        """
        self._event_count += 1

        event_type = getattr(event, "event_type", "unknown")
        resource_id = _extract_resource_id(event)
        severity = _severity_from_priority(getattr(event, "priority", 20))

        # Build metrics snapshot
        metrics_snapshot = None
        if self._metrics_provider:
            try:
                metrics_snapshot = self._metrics_provider()
            except Exception:
                metrics_snapshot = {"error": "metrics_unavailable"}

        # Serialize the full event payload
        record_data = event.model_dump()
        record_data["resource_id"] = resource_id
        record_data["severity"] = severity
        record_data["metrics_snapshot"] = metrics_snapshot

        # Store in memory for API access
        self._history.append(record_data)

        # Route to the correct domain logger
        domain = _resolve_domain(event_type)
        logger = self._loggers.get(domain, self._loggers.get("infrastructure"))

        if logger:
            logger.info(
                f"[{event_type}] {resource_id or 'system'}",
                extra={
                    "event_type": event_type,
                    "resource_id": resource_id,
                    "severity": severity,
                    "metrics_snapshot": metrics_snapshot,
                    "extra_data": record_data,
                },
            )
