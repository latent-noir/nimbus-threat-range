"""
Container orchestration manager.

Handles container scheduling onto VMs, scaling, and crash recovery.
Subscribes to ContainerCrashEvent and resource events.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Dict, List, Optional

from .models import Container, ContainerStatus, Service

if TYPE_CHECKING:
    from engine.event_bus import EventBus
    from events.infra_events import ContainerCrashEvent, ResourceSpikeEvent


class ContainerManager:
    """
    Schedules and manages containers across the VM fleet.

    Works in tandem with VMManager — containers are assigned to VMs
    and their resource usage rolls up to the parent VM.
    """

    def __init__(self) -> None:
        self.containers: Dict[str, Container] = {}

    # ── Public API ────────────────────────────────────────────

    def create_container(
        self,
        container_id: str,
        name: str,
        vm_id: str,
        services: Optional[List[Service]] = None,
        **kwargs,
    ) -> Container:
        """Create and schedule a container onto a VM."""
        container = Container(
            id=container_id,
            name=name,
            vm_id=vm_id,
            services=services or [],
            **kwargs,
        )
        self.containers[container_id] = container
        return container

    def destroy_container(self, container_id: str) -> None:
        self.containers.pop(container_id, None)

    def get_container(self, container_id: str) -> Optional[Container]:
        return self.containers.get(container_id)

    def update(self, tick: int) -> None:
        """
        Per-tick update: simulate resource drift for all RUNNING containers.
        """
        for container in self.containers.values():
            if container.status == ContainerStatus.RUNNING:
                # CPU drift: small random walk
                drift = random.uniform(-5.0, 5.0)
                container.cpu_usage = max(0.0, min(100.0, container.cpu_usage + drift))

                # Memory drift: +/- 1MB
                mem_drift = random.randint(-1024 * 1024, 1024 * 1024)
                container.memory_usage = max(
                    0, min(container.memory_limit, container.memory_usage + mem_drift)
                )

    # ── Event Handlers ────────────────────────────────────────

    def register_handlers(self, bus: EventBus) -> None:
        """Subscribe to crash and resource events."""
        bus.subscribe("infra.container_crash", self.handle_crash)
        bus.subscribe("infra.resource_spike", self.handle_resource_spike)

    async def handle_crash(self, event: ContainerCrashEvent) -> None:
        """Mark container as CRASHED."""
        container_id = getattr(event, "container_id", "")
        container = self.containers.get(container_id)
        if container:
            container.status = ContainerStatus.CRASHED
            container.cpu_usage = 0.0

    async def handle_resource_spike(self, event: ResourceSpikeEvent) -> None:
        """Apply resource spike effect to a container."""
        target_id = getattr(event, "target_id", "")
        container = self.containers.get(target_id)
        if container and container.status == ContainerStatus.RUNNING:
            spike_value = getattr(event, "spike_value", 0.0)
            container.cpu_usage = min(100.0, container.cpu_usage + spike_value * 0.5)

            # Crash if sustained at 100%
            if container.cpu_usage >= 100.0:
                container.status = ContainerStatus.CRASHED
