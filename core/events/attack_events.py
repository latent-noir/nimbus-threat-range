"""
Attack-domain events emitted by the Security layer.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from .base import BaseEvent, EventPriority


class AttackType(str, Enum):
    DDOS           = "ddos"
    PRIVILEGE_ESC  = "privilege_escalation"
    BRUTE_FORCE    = "brute_force"
    SQL_INJECTION  = "sql_injection"
    RANSOMWARE     = "ransomware"


class AttackEvent(BaseEvent):
    """
    Represents an attack being launched against infrastructure.

    Attributes:
        attack_type:  Category of attack.
        target_id:    ID of the targeted VM / Container / Service.
        severity:     0-100 severity score.
        duration_ms:  How long the attack lasts (simulation time).
    """
    event_type: str = "attack.launched"
    priority: int = EventPriority.HIGH
    source: str = "security"

    attack_type: AttackType = AttackType.DDOS
    target_id: str = ""
    severity: int = 50
    duration_ms: int = 5000
