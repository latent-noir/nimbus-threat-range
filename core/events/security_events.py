"""
Security-domain events emitted by IDS and Firewall subsystems.
"""

from __future__ import annotations

from enum import Enum
from .base import BaseEvent, EventPriority


class ThreatLevel(str, Enum):
    INFO     = "info"
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


class IDSAlertEvent(BaseEvent):
    """
    The Intrusion Detection System has flagged suspicious activity.

    Attributes:
        rule_id:       ID of the IDS rule that triggered.
        threat_level:  Assessed threat severity.
        description:   Human-readable alert text.
        source_ip:     Simulated source address.
    """
    event_type: str = "security.ids_alert"
    priority: int = EventPriority.HIGH
    source: str = "security.ids"

    rule_id: str = ""
    threat_level: ThreatLevel = ThreatLevel.MEDIUM
    description: str = ""
    source_ip: str = ""


class FirewallBlockEvent(BaseEvent):
    """
    The Firewall has blocked traffic based on a rule match.

    Attributes:
        blocked_source:  Source IP / Subnet that was blocked.
        blocked_dest:    Destination that was protected.
        rule_matched:    ID of the firewall rule that matched.
        protocol:        Protocol of the blocked traffic.
    """
    event_type: str = "security.firewall_block"
    source: str = "security.firewall"

    blocked_source: str = ""
    blocked_dest: str = ""
    rule_matched: str = ""
    protocol: str = "tcp"
