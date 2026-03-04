"""
Firewall rules engine.

Evaluates traffic against a rule set and emits FirewallBlockEvent
when malicious or policy-violating traffic is detected.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from events.security_events import FirewallBlockEvent

if TYPE_CHECKING:
    from engine.event_bus import EventBus
    from events.base import BaseEvent

logger = logging.getLogger("cloud_sim.firewall")


class FirewallAction(str, Enum):
    ALLOW = "allow"
    DENY  = "deny"
    LOG   = "log"


class FirewallRule:
    """A single firewall policy rule."""

    def __init__(
        self,
        rule_id: str,
        source: str = "*",
        destination: str = "*",
        port: int = 0,
        protocol: str = "tcp",
        action: FirewallAction = FirewallAction.DENY,
    ) -> None:
        self.rule_id = rule_id
        self.source = source
        self.destination = destination
        self.port = port
        self.protocol = protocol
        self.action = action

    def matches(self, src: str, dst: str, port: int, proto: str) -> bool:
        """
        Check whether this rule matches the given traffic parameters.

        Wildcard '*' matches any value. Port 0 matches any port.
        """
        if self.source != "*" and self.source != src:
            return False
        if self.destination != "*" and self.destination != dst:
            return False
        if self.port != 0 and self.port != port:
            return False
        if self.protocol != proto:
            return False
        return True

    def evaluate(self, src: str, dst: str, port: int, proto: str) -> Optional[FirewallAction]:
        """Return the action if this rule matches, else None."""
        if self.matches(src, dst, port, proto):
            return self.action
        return None


class Firewall:
    """
    Stateless packet-filter firewall.

    Rules are evaluated in order; first match wins.
    Blocked traffic generates a FirewallBlockEvent.
    """

    def __init__(self) -> None:
        self.rules: List[FirewallRule] = []
        self.block_count: int = 0
        self.allow_count: int = 0
        self._bus: Optional[EventBus] = None

    # ── Configuration ─────────────────────────────────────────

    def add_rule(self, rule: FirewallRule) -> None:
        self.rules.append(rule)

    def load_default_rules(self) -> None:
        """Sensible defaults: block known-bad ports, allow rest."""
        self.rules = [
            FirewallRule("FW001", source="*", port=22, protocol="tcp", action=FirewallAction.DENY),
            FirewallRule("FW002", source="*", port=23, protocol="tcp", action=FirewallAction.DENY),
            FirewallRule("FW003", source="*", port=3389, protocol="tcp", action=FirewallAction.DENY),
            # Default allow — must be last
            FirewallRule("FW999", source="*", destination="*", port=0, action=FirewallAction.ALLOW),
        ]

    # ── Traffic Evaluation ────────────────────────────────────

    def check_traffic(
        self, src: str, dst: str, port: int, proto: str = "tcp"
    ) -> FirewallAction:
        """
        Evaluate traffic against rules in order. First match wins.
        Returns ALLOW if no rules match (default open).
        """
        for rule in self.rules:
            result = rule.evaluate(src, dst, port, proto)
            if result is not None:
                if result == FirewallAction.DENY:
                    self.block_count += 1
                elif result == FirewallAction.ALLOW:
                    self.allow_count += 1
                # LOG action: do not count as allow or block
                return result
        self.allow_count += 1
        return FirewallAction.ALLOW

    # ── Event Handling ────────────────────────────────────────

    def register_handlers(self, bus: EventBus) -> None:
        """Subscribe to attack events to evaluate traffic."""
        self._bus = bus
        bus.subscribe("attack.*", self.evaluate_traffic)

    async def evaluate_traffic(self, event: BaseEvent) -> None:
        """
        Evaluate simulated traffic against firewall rules.
        Emit FirewallBlockEvent if traffic is denied.
        """
        target_id = getattr(event, "target_id", "unknown")
        source_ip = getattr(event, "payload", {}).get("source_ip", "10.0.0.99")
        port = getattr(event, "payload", {}).get("port", 80)

        action = self.check_traffic(source_ip, target_id, port, "tcp")

        if action == FirewallAction.DENY and self._bus:
            block_event = FirewallBlockEvent(
                tick=getattr(event, "tick", 0),
                blocked_source=source_ip,
                blocked_dest=target_id,
                rule_matched=self._get_matching_rule_id(source_ip, target_id, port, "tcp"),
                protocol="tcp",
            )
            await self._bus.publish(block_event)
            logger.info(
                "Firewall blocked traffic from %s to %s on port %d",
                source_ip, target_id, port,
            )

    def _get_matching_rule_id(self, src: str, dst: str, port: int, proto: str) -> str:
        """Return the rule_id of the first matching rule."""
        for rule in self.rules:
            if rule.matches(src, dst, port, proto):
                return rule.rule_id
        return "DEFAULT"
