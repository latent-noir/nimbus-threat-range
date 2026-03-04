"""
Network topology and failure simulation manager.

Manages subnets, inter-VM routing, and handles NetworkFailureEvent.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Dict, Optional

from .models import Network, Subnet

if TYPE_CHECKING:
    from engine.event_bus import EventBus
    from events.infra_events import NetworkFailureEvent


class NetworkManager:
    """
    Manages the simulated network topology.

    Each VM is assigned to a Subnet. Network failures affect
    all VMs within the targeted subnet.
    """

    def __init__(self) -> None:
        self.networks: Dict[str, Network] = {}

    # ── Public API ────────────────────────────────────────────

    def create_network(self, net_id: str, name: str = "default") -> Network:
        net = Network(id=net_id, name=name)
        self.networks[net_id] = net
        return net

    def add_subnet(self, net_id: str, subnet_id: str, cidr: str) -> Optional[Subnet]:
        net = self.networks.get(net_id)
        if net is None:
            return None
        subnet = Subnet(id=subnet_id, cidr=cidr)
        net.subnets[subnet_id] = subnet
        return subnet

    def update(self, tick: int) -> None:
        """Per-tick network health checks — small chance of latency drift."""
        for net in self.networks.values():
            for subnet in net.subnets.values():
                # Small chance of health flicker for simulation realism
                if random.random() < 0.005:
                    subnet.is_healthy = not subnet.is_healthy

    # ── Event Handlers ────────────────────────────────────────

    def register_handlers(self, bus: EventBus) -> None:
        """Subscribe to network failure events."""
        bus.subscribe("infra.network_failure", self.handle_failure)

    async def handle_failure(self, event: NetworkFailureEvent) -> None:
        """Apply network failure effects to the targeted subnet."""
        affected_subnet_id = getattr(event, "affected_subnet", "")
        for net in self.networks.values():
            for sub_id, subnet in net.subnets.items():
                if sub_id == affected_subnet_id or subnet.cidr == affected_subnet_id:
                    subnet.is_healthy = False
