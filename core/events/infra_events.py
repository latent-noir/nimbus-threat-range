"""
Infrastructure-domain events emitted when resource or network conditions change.
"""

from __future__ import annotations

from enum import Enum
from .base import BaseEvent, EventPriority


class ResourceType(str, Enum):
    CPU    = "cpu"
    MEMORY = "memory"
    DISK   = "disk"


class FailureMode(str, Enum):
    PARTITION   = "partition"     # network split
    LATENCY     = "latency"      # added latency
    PACKET_LOSS = "packet_loss"  # dropped packets
    TOTAL       = "total"        # full outage


class ResourceSpikeEvent(BaseEvent):
    """
    A resource metric has spiked beyond a threshold.

    Attributes:
        resource_type:  Which resource (CPU / Memory / Disk).
        target_id:      ID of the affected VM or Container.
        spike_value:    The new resource value (e.g. 98.5 for CPU %).
        threshold:      The threshold that was exceeded.
    """
    event_type: str = "infra.resource_spike"
    source: str = "infrastructure"

    resource_type: ResourceType = ResourceType.CPU
    target_id: str = ""
    spike_value: float = 0.0
    threshold: float = 90.0


class NetworkFailureEvent(BaseEvent):
    """
    A network-level failure has occurred.

    Attributes:
        affected_subnet:  Subnet CIDR or ID.
        failure_mode:     How the failure manifests.
        packet_loss_pct:  0-100, only relevant for PACKET_LOSS mode.
    """
    event_type: str = "infra.network_failure"
    priority: int = EventPriority.CRITICAL
    source: str = "infrastructure"

    affected_subnet: str = ""
    failure_mode: FailureMode = FailureMode.TOTAL
    packet_loss_pct: float = 100.0


class ContainerCrashEvent(BaseEvent):
    """Emitted when a container's status transitions to CRASHED."""
    event_type: str = "infra.container_crash"
    priority: int = EventPriority.HIGH
    source: str = "infrastructure"

    container_id: str = ""
    reason: str = "oom"  # out-of-memory, cpu_throttle, manual
