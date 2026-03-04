"""
Attack scheduling and execution engine.

Translates high-level AttackEvents into concrete infrastructure effects
(CPU spikes, container crashes, network partitions).
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Dict, List

from events.attack_events import AttackEvent, AttackType
from events.infra_events import ResourceSpikeEvent, ContainerCrashEvent, NetworkFailureEvent, ResourceType, FailureMode

if TYPE_CHECKING:
    from engine.event_bus import EventBus

logger = logging.getLogger("cloud_sim.attack_engine")


class ActiveAttack:
    """Tracks an in-progress attack for duration management."""

    def __init__(self, event: AttackEvent, start_tick: int) -> None:
        self.event = event
        self.start_tick = start_tick
        self.duration_ticks = max(1, event.duration_ms // 1000)

    def is_expired(self, current_tick: int) -> bool:
        return (current_tick - self.start_tick) >= self.duration_ticks


class AttackEngine:
    """
    Processes AttackEvents and applies their effects to the infrastructure.

    Workflow:
        1. Receives AttackEvent via EventBus subscription.
        2. Resolves target (VM / Container / Subnet).
        3. Emits derived infrastructure events (ResourceSpikeEvent, etc.).
        4. Schedules a recovery event after duration_ms.
    """

    def __init__(self) -> None:
        self.active_attacks: List[ActiveAttack] = []
        self._bus: EventBus | None = None

    # ── Public API ────────────────────────────────────────────

    def register_handlers(self, bus: EventBus) -> None:
        """Subscribe to AttackEvent on the EventBus."""
        self._bus = bus
        bus.subscribe("attack.launched", self.handle_attack)

    async def handle_attack(self, event: AttackEvent) -> None:
        """
        Process an incoming attack.

        Steps:
            1. Log the attack initiation.
            2. Translate attack_type to infra effects.
            3. Emit ResourceSpikeEvent / ContainerCrashEvent / NetworkFailureEvent.
            4. Track active attack for duration management.
        """
        logger.warning(
            "Attack received: type=%s target=%s severity=%d",
            event.attack_type, event.target_id, event.severity,
        )

        attack_record = ActiveAttack(event, event.tick)
        self.active_attacks.append(attack_record)

        # Translate attack type to infrastructure events
        if self._bus:
            await self._translate_attack(event)

    async def _translate_attack(self, event: AttackEvent) -> None:
        """Map attack types to concrete infrastructure effects."""
        attack_type = event.attack_type
        if isinstance(attack_type, str):
            attack_type = AttackType(attack_type)

        if attack_type in (AttackType.DDOS, AttackType.BRUTE_FORCE):
            # DDoS / brute-force → CPU spike
            spike = ResourceSpikeEvent(
                tick=event.tick,
                resource_type=ResourceType.CPU,
                target_id=event.target_id,
                spike_value=min(100.0, 50.0 + event.severity * 0.5),
                threshold=90.0,
            )
            await self._bus.publish(spike)

        elif attack_type == AttackType.RANSOMWARE:
            # Ransomware → container crash
            crash = ContainerCrashEvent(
                tick=event.tick,
                container_id=event.target_id,
                reason="ransomware_encryption",
            )
            await self._bus.publish(crash)

        elif attack_type == AttackType.SQL_INJECTION:
            # SQL injection → CPU spike (query overload)
            spike = ResourceSpikeEvent(
                tick=event.tick,
                resource_type=ResourceType.CPU,
                target_id=event.target_id,
                spike_value=min(100.0, 30.0 + event.severity * 0.7),
                threshold=90.0,
            )
            await self._bus.publish(spike)

        elif attack_type == AttackType.PRIVILEGE_ESC:
            # Privilege escalation → memory spike
            spike = ResourceSpikeEvent(
                tick=event.tick,
                resource_type=ResourceType.MEMORY,
                target_id=event.target_id,
                spike_value=min(100.0, 60.0 + event.severity * 0.4),
                threshold=90.0,
            )
            await self._bus.publish(spike)

    def update(self, tick: int) -> None:
        """
        Per-tick maintenance: check for expired attacks,
        remove them from active list.
        """
        expired = [a for a in self.active_attacks if a.is_expired(tick)]
        for attack in expired:
            logger.info(
                "Attack expired: type=%s target=%s (ran for %d ticks)",
                attack.event.attack_type, attack.event.target_id, attack.duration_ticks,
            )
        self.active_attacks = [a for a in self.active_attacks if not a.is_expired(tick)]
