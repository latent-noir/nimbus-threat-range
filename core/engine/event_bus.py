"""
Event Bus — publish / subscribe dispatcher with priority ordering.

The EventBus is the central nervous system of the simulation.
Components publish events, and registered handlers receive them
in priority order.
"""

from __future__ import annotations

import asyncio
import heapq
import logging
from typing import Any, Callable, Coroutine, Dict, List, Tuple, Type

from events.base import BaseEvent, EventPriority

logger = logging.getLogger("cloud_sim.event_bus")

# Type alias for async event handlers
EventHandler = Callable[[BaseEvent], Coroutine[Any, Any, None]]


class _Subscription:
    """Internal record for a handler subscription."""

    def __init__(self, event_pattern: str, handler: EventHandler, priority: int) -> None:
        self.event_pattern = event_pattern
        self.handler = handler
        self.priority = priority

    def matches(self, event_type: str) -> bool:
        """Check if event_type matches this subscription's pattern."""
        if self.event_pattern == "*":
            return True
        if self.event_pattern.endswith(".*"):
            prefix = self.event_pattern[:-2]
            return event_type.startswith(prefix)
        return event_type == self.event_pattern


class EventBus:
    """
    Async pub/sub event dispatcher.

    Usage:
        bus = EventBus()
        bus.subscribe("attack.*", my_handler, priority=10)
        await bus.publish(some_event)

    Events are dispatched to matching handlers sorted by priority (lowest first).
    """

    def __init__(self) -> None:
        self._subscriptions: List[_Subscription] = []
        self._queue: List[Tuple[int, int, BaseEvent]] = []  # heapq: (priority, seq, event)
        self._seq: int = 0  # monotonic counter for stable sort

    # ── Subscribe ─────────────────────────────────────────────

    def subscribe(
        self,
        event_pattern: str,
        handler: EventHandler,
        priority: int = EventPriority.NORMAL,
    ) -> None:
        """
        Register a handler for events matching a pattern.

        Args:
            event_pattern: Exact type or glob (e.g. "attack.*", "*").
            handler:       Async callable(event) -> None.
            priority:      Dispatch order (lower = earlier).
        """
        sub = _Subscription(event_pattern, handler, priority)
        self._subscriptions.append(sub)
        logger.debug("Subscribed %s to pattern '%s'", handler.__qualname__, event_pattern)

    # ── Publish ───────────────────────────────────────────────

    async def publish(self, event: BaseEvent) -> None:
        """
        Enqueue an event for immediate dispatch to matching handlers.
        """
        matching = [
            (sub.priority, sub.handler)
            for sub in self._subscriptions
            if sub.matches(event.event_type)
        ]
        # Sort by priority (stable)
        matching.sort(key=lambda x: x[0])

        for _, handler in matching:
            try:
                await handler(event)
            except Exception:
                logger.exception("Handler %s failed for event %s", handler.__qualname__, event.event_type)

    # ── Queue-based batch dispatch (alternative) ──────────────

    def enqueue(self, event: BaseEvent) -> None:
        """Add event to the priority queue for batch processing."""
        self._seq += 1
        heapq.heappush(self._queue, (event.priority, self._seq, event))

    async def flush(self) -> int:
        """Process all queued events in priority order. Returns count processed."""
        count = 0
        while self._queue:
            _, _, event = heapq.heappop(self._queue)
            await self.publish(event)
            count += 1
        return count
