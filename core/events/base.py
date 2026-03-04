"""
Base event definitions for the event-driven simulation engine.

Every event in the system inherits from BaseEvent. Events are immutable
data records that flow through the EventBus to registered handlers.
"""

from __future__ import annotations

import uuid
import time
from enum import IntEnum
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class EventPriority(IntEnum):
    """Dispatch priority — lower value = processed first."""
    CRITICAL = 0
    HIGH     = 10
    NORMAL   = 20
    LOW      = 30


class BaseEvent(BaseModel):
    """
    Immutable base record for all simulation events.

    Attributes:
        id:         Unique event identifier (UUID).
        timestamp:  Wall-clock time the event was created.
        tick:       Simulation tick at which the event was emitted.
        source:     Subsystem that produced the event (e.g. "infra", "security").
        event_type: Dot-namespaced type string (e.g. "attack.ddos").
        priority:   Dispatch priority for the EventBus queue.
        payload:    Arbitrary extra data carried by the event.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = Field(default_factory=time.time)
    tick: int = 0
    source: str = "system"
    event_type: str = "base"
    priority: EventPriority = EventPriority.NORMAL
    payload: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True, use_enum_values=True)

    # -- Comparison helpers for heapq (priority queue) --
    def __lt__(self, other: BaseEvent) -> bool:
        return self.priority < other.priority
