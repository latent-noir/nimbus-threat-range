"""
Simulation Engine — the top-level orchestrator.

Owns the Clock, EventBus, and all layer managers.
Drives the simulation loop: advance clock → update layers → process events → snapshot.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional

from .clock import SimulationClock
from .event_bus import EventBus

# Infrastructure
from infrastructure.vm_manager import VMManager
from infrastructure.container_manager import ContainerManager
from infrastructure.network_manager import NetworkManager
from infrastructure.models import Service

# Security
from security.attack_engine import AttackEngine
from security.ids import IntrusionDetectionSystem
from security.firewall import Firewall

# Logging
from logging_layer.event_logger import EventLogger
from logging_layer.metric_store import MetricStore
from logging_layer.audit_trail import AuditTrail

# Events
from events.attack_events import AttackEvent, AttackType


class SimulationEngine:
    """
    Central orchestrator for the cloud simulation.

    Responsibilities:
        1. Manage simulation time via SimulationClock.
        2. Dispatch events via EventBus.
        3. Coordinate Infrastructure, Security, and Logging layers.
        4. Expose state snapshots for the API / Visualization layer.
    """

    def __init__(self, tick_interval: float = 1.0) -> None:
        # ── Core ──────────────────────────────────────────────
        self.clock = SimulationClock(tick_interval=tick_interval)
        self.bus = EventBus()
        self.running: bool = False

        # ── Infrastructure Layer ──────────────────────────────
        self.vm_manager = VMManager()
        self.container_manager = ContainerManager()
        self.network_manager = NetworkManager()

        # ── Security Layer ────────────────────────────────────
        self.attack_engine = AttackEngine()
        self.ids = IntrusionDetectionSystem()
        self.firewall = Firewall()

        # ── Logging Layer ─────────────────────────────────────
        self.event_logger = EventLogger(
            metrics_provider=self._get_metrics_snapshot,
            enable_console=True,
        )
        self.metric_store = MetricStore()
        self.audit_trail = AuditTrail()

    # ── Initialization ────────────────────────────────────────

    def initialize(self, vm_count: int = 3, containers_per_vm: int = 2) -> None:
        """
        Bootstrap the simulated infrastructure.

        Creates VMs, assigns containers to each, sets up default
        network, and registers all event handlers.
        """
        # Wire event handlers
        self._register_all_handlers()

        # Load security defaults
        self.ids.load_default_rules()
        self.firewall.load_default_rules()

        # Create network
        net = self.network_manager.create_network("net-001", "production")
        self.network_manager.add_subnet("net-001", "subnet-001", "10.0.1.0/24")

        # Create VMs and Containers
        for i in range(vm_count):
            vm_id = f"vm-{i:03d}"
            vm = self.vm_manager.create_vm(vm_id, f"host-{i}", subnet_id="subnet-001")

            for j in range(containers_per_vm):
                c_id = f"c-{i:03d}-{j:02d}"
                self.container_manager.create_container(
                    container_id=c_id,
                    name=f"worker-{i}-{j}",
                    vm_id=vm_id,
                    services=[Service(name="http-server", port=80 + j)],
                )
                vm.container_ids.append(c_id)

    def _register_all_handlers(self) -> None:
        """Wire every layer's event handlers to the bus."""
        self.vm_manager.register_handlers(self.bus)
        self.container_manager.register_handlers(self.bus)
        self.network_manager.register_handlers(self.bus)
        self.attack_engine.register_handlers(self.bus)
        self.ids.register_handlers(self.bus)
        self.firewall.register_handlers(self.bus)
        self.event_logger.register_handlers(self.bus)
        self.audit_trail.register_handlers(self.bus)

    # ── Simulation Loop ───────────────────────────────────────

    async def start(self) -> None:
        """Start the main simulation loop."""
        self.running = True
        while self.running and not self.clock.is_expired:
            await self.tick()
            await asyncio.sleep(self.clock.tick_interval)

    async def tick(self) -> None:
        """
        Execute one simulation step.

        Pipeline:
            1. Advance clock.
            2. Update infrastructure (resource drift).
            3. Update security (check active attacks).
            4. Flush event queue (dispatches to all handlers).
            5. Record metrics snapshot.
        """
        t = self.clock.advance()

        # Phase 1: Infrastructure update
        self.vm_manager.update(t)
        self.container_manager.update(t)
        self.network_manager.update(t)

        # Phase 2: Security update
        self.attack_engine.update(t)

        # Phase 3: Process any queued events
        await self.bus.flush()

        # Phase 4: Record metrics
        self._record_metrics(t)

    def stop(self) -> None:
        """Gracefully stop the simulation loop."""
        self.running = False

    # ── External Commands ─────────────────────────────────────

    async def inject_attack(
        self,
        target_id: str,
        attack_type: str = "ddos",
        severity: int = 80,
        duration_ms: int = 5000,
    ) -> None:
        """API entry point — schedule an attack via the event system."""
        event = AttackEvent(
            tick=self.clock.current_tick,
            attack_type=AttackType(attack_type),
            target_id=target_id,
            severity=severity,
            duration_ms=duration_ms,
        )
        await self.bus.publish(event)

    # ── State Snapshot ────────────────────────────────────────

    def get_state(self) -> Dict[str, Any]:
        """
        Build a read-only snapshot of the entire simulation state.

        This is what the API and visualization layer consume.
        """
        containers = [c.model_dump() for c in self.container_manager.containers.values()]
        vms = [vm.model_dump() for vm in self.vm_manager.vms.values()]

        total_cpu = sum(c.cpu_usage for c in self.container_manager.containers.values())
        count = len(self.container_manager.containers) or 1

        return {
            "tick": self.clock.current_tick,
            "timestamp": time.time(),
            "vms": vms,
            "containers": containers,
            "networks": {nid: n.model_dump() for nid, n in self.network_manager.networks.items()},
            "metrics": {
                "total_vms": len(self.vm_manager.vms),
                "total_containers": len(self.container_manager.containers),
                "global_cpu_load": total_cpu / count,
            },
            "recent_events": self.event_logger.get_recent(20),
        }

    # ── Internal Helpers ──────────────────────────────────────

    def _record_metrics(self, tick: int) -> None:
        """Snapshot current resource values into MetricStore."""
        for c in self.container_manager.containers.values():
            self.metric_store.record(c.id, "cpu_usage", tick, c.cpu_usage)
            self.metric_store.record(c.id, "memory_usage", tick, float(c.memory_usage))
        for vm in self.vm_manager.vms.values():
            self.metric_store.record(vm.id, "cpu_usage", tick, vm.cpu_usage)

    def _get_metrics_snapshot(self) -> Dict[str, Any]:
        """Provide a live metrics dict for the EventLogger to embed in log records."""
        total_cpu = sum(c.cpu_usage for c in self.container_manager.containers.values())
        count = len(self.container_manager.containers) or 1
        return {
            "tick": self.clock.current_tick,
            "total_vms": len(self.vm_manager.vms),
            "total_containers": count,
            "global_cpu_load": round(total_cpu / count, 2),
        }
