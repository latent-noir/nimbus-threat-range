"""
VM lifecycle manager.

Responsible for creating, destroying, and updating Virtual Machines.
Subscribes to ResourceSpikeEvent to react to VM-level resource anomalies.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Dict, Optional

from .models import VM, VMStatus

if TYPE_CHECKING:
    from engine.event_bus import EventBus
    from events.infra_events import ResourceSpikeEvent


class VMManager:
    """
    Manages the fleet of Virtual Machines.

    Lifecycle:
        1. Engine creates VMManager at startup.
        2. VMManager registers event handlers on the EventBus.
        3. On each tick, the engine calls vm_manager.update(tick).
    """

    def __init__(self) -> None:
        self.vms: Dict[str, VM] = {}

    # ── Public API ────────────────────────────────────────────

    def create_vm(self, vm_id: str, name: str, **kwargs) -> VM:
        """Provision a new VM and register it internally."""
        vm = VM(id=vm_id, name=name, **kwargs)
        self.vms[vm_id] = vm
        return vm

    def destroy_vm(self, vm_id: str) -> None:
        """Tear down a VM (and orphan its containers)."""
        self.vms.pop(vm_id, None)

    def get_vm(self, vm_id: str) -> Optional[VM]:
        return self.vms.get(vm_id)

    def update(self, tick: int) -> None:
        """
        Called once per simulation tick.
        Apply resource drift, check thresholds.
        """
        for vm in self.vms.values():
            if vm.status == VMStatus.RUNNING:
                # Simulate CPU drift: small random walk
                drift = random.uniform(-3.0, 4.0)
                vm.cpu_usage = max(0.0, min(100.0, vm.cpu_usage + drift))

                # Simulate memory drift
                mem_drift = random.randint(-512 * 1024, 1024 * 1024)
                vm.memory_used = max(0, min(vm.memory_total, vm.memory_used + mem_drift))

    # ── Event Handlers ────────────────────────────────────────

    def register_handlers(self, bus: EventBus) -> None:
        """Subscribe to events this manager cares about."""
        bus.subscribe("infra.resource_spike", self.handle_resource_spike)

    async def handle_resource_spike(self, event: ResourceSpikeEvent) -> None:
        """React to a resource spike on one of our VMs."""
        target_id = getattr(event, "target_id", "")
        vm = self.vms.get(target_id)
        if vm is None:
            return

        spike_value = getattr(event, "spike_value", 0.0)
        if spike_value >= 95.0:
            vm.status = VMStatus.COMPROMISED
        elif spike_value >= 80.0:
            vm.cpu_usage = min(100.0, vm.cpu_usage + spike_value * 0.3)
