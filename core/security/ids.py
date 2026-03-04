"""
Intrusion Detection System (IDS).

Production-grade anomaly detection engine that monitors the simulation
event stream and generates structured alerts. Implements two detection
strategies:

    1. **CPU Anomaly Detector** — detects abnormal CPU spikes using
       both a static threshold and a rate-of-change analysis.

    2. **Connection Failure Tracker** — counts failed connection
       attempts per source within a sliding time window and flags
       brute-force / scan patterns.

Emits IDSAlertEvent with severity levels:  low | medium | high | critical.
All alerts are routed through the EventBus and the structured logging system.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Deque, Dict, List, Optional, Tuple

from events.base import BaseEvent, EventPriority
from events.security_events import IDSAlertEvent, ThreatLevel
from logging_layer.log_config import get_domain_logger

if TYPE_CHECKING:
    from engine.event_bus import EventBus

logger = get_domain_logger("security")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Detection Rules
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class RuleAction(str, Enum):
    ALERT = "alert"
    BLOCK = "block"
    LOG   = "log"


@dataclass
class IDSRule:
    """
    Declarative detection rule evaluated against incoming events.

    Attributes:
        rule_id:        Unique rule identifier (e.g. "IDS-001").
        event_pattern:  Glob pattern matched against event_type.
        threat_level:   Severity assigned when rule triggers.
        description:    Human-readable explanation.
        action:         What to do on match (alert, block, log).
        cooldown_sec:   Minimum seconds between repeated firings for
                        the same target (prevents alert storms).
        enabled:        Toggle rule on/off without removing it.
    """
    rule_id: str
    event_pattern: str
    threat_level: ThreatLevel
    description: str
    action: RuleAction = RuleAction.ALERT
    cooldown_sec: float = 5.0
    enabled: bool = True

    # Track last fire time per target to enforce cooldown
    _last_fired: Dict[str, float] = field(default_factory=dict, repr=False)

    def matches(self, event_type: str) -> bool:
        """Glob-style pattern matching (prefix.* or exact)."""
        if not self.enabled:
            return False
        if self.event_pattern == "*":
            return True
        if self.event_pattern.endswith(".*"):
            return event_type.startswith(self.event_pattern[:-2])
        return event_type == self.event_pattern

    def can_fire(self, target_id: str) -> bool:
        """Respect cooldown — avoid alert storms for the same target."""
        now = time.time()
        last = self._last_fired.get(target_id, 0.0)
        return (now - last) >= self.cooldown_sec

    def mark_fired(self, target_id: str) -> None:
        self._last_fired[target_id] = time.time()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Anomaly Detectors
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class CPUAnomalyDetector:
    """
    Detect abnormal CPU spikes using two strategies:

    1. **Absolute threshold** — CPU > threshold triggers immediately.
    2. **Rate-of-change** — a sudden delta (e.g. +40% in one tick)
       suggests injection even if absolute value is moderate.

    Maintains a per-entity sliding window of recent CPU values.
    """

    WINDOW_SIZE = 30    # ticks of history to keep

    def __init__(
        self,
        absolute_threshold: float = 90.0,
        delta_threshold: float = 40.0,
    ) -> None:
        self.absolute_threshold = absolute_threshold
        self.delta_threshold = delta_threshold
        self._history: Dict[str, Deque[float]] = defaultdict(
            lambda: deque(maxlen=self.WINDOW_SIZE)
        )

    def record(self, entity_id: str, cpu_value: float) -> None:
        """Record a CPU sample for an entity."""
        self._history[entity_id].append(cpu_value)

    def analyze(self, entity_id: str, cpu_value: float) -> Optional[Tuple[ThreatLevel, str]]:
        """
        Analyze a new CPU reading.

        Returns:
            (ThreatLevel, description) if anomaly detected, else None.
        """
        history = self._history.get(entity_id, deque())

        # ── Absolute threshold ────────────────────────────────
        if cpu_value >= self.absolute_threshold:
            severity = ThreatLevel.CRITICAL if cpu_value >= 98.0 else ThreatLevel.HIGH
            return (
                severity,
                f"CPU at {cpu_value:.1f}% exceeds threshold "
                f"({self.absolute_threshold}%) on {entity_id}",
            )

        # ── Rate-of-change (delta) ────────────────────────────
        if len(history) >= 2:
            prev = history[-2]  # second-to-last (last is current)
            delta = cpu_value - prev
            if delta >= self.delta_threshold:
                return (
                    ThreatLevel.HIGH,
                    f"CPU spike of +{delta:.1f}% in one tick on {entity_id} "
                    f"({prev:.1f}% → {cpu_value:.1f}%)",
                )

        # ── Sustained elevated usage ─────────────────────────
        if len(history) >= 10:
            recent_avg = sum(list(history)[-10:]) / 10
            if recent_avg > 80.0:
                return (
                    ThreatLevel.MEDIUM,
                    f"Sustained high CPU (avg {recent_avg:.1f}%) over "
                    f"last 10 ticks on {entity_id}",
                )

        return None


class ConnectionFailureTracker:
    """
    Track failed connection attempts per source IP within a sliding
    time window.  Flags potential brute-force or port-scan activity.

    Uses a time-bucketed counter with configurable window and threshold.
    """

    def __init__(
        self,
        window_sec: float = 60.0,
        threshold: int = 10,
    ) -> None:
        self.window_sec = window_sec
        self.threshold = threshold
        # source_ip → list of (timestamp) of failures
        self._failures: Dict[str, Deque[float]] = defaultdict(
            lambda: deque(maxlen=1000)
        )
        self._alerted: Dict[str, float] = {}  # source_ip → last alert time

    def record_failure(self, source_ip: str, ts: Optional[float] = None) -> Optional[Tuple[ThreatLevel, str]]:
        """
        Record a failed connection attempt.

        Returns:
            (ThreatLevel, description) if threshold breached, else None.
        """
        now = ts or time.time()
        window = self._failures[source_ip]
        window.append(now)

        # Evict entries outside the sliding window
        cutoff = now - self.window_sec
        while window and window[0] < cutoff:
            window.popleft()

        count = len(window)

        if count < self.threshold:
            return None

        # Cooldown: don't re-alert for same IP within window
        last_alert = self._alerted.get(source_ip, 0.0)
        if (now - last_alert) < self.window_sec:
            return None

        self._alerted[source_ip] = now

        # Severity escalation based on count
        if count >= self.threshold * 5:
            severity, label = ThreatLevel.CRITICAL, "Aggressive"
        elif count >= self.threshold * 2:
            severity, label = ThreatLevel.HIGH, "Repeated"
        else:
            severity, label = ThreatLevel.MEDIUM, "Suspicious"

        return (
            severity,
            f"{label} connection failures from {source_ip}: "
            f"{count} failures in {self.window_sec}s window "
            f"(threshold: {self.threshold})",
        )

    def get_top_offenders(self, n: int = 5) -> List[Tuple[str, int]]:
        """Return the top N source IPs by failure count."""
        now = time.time()
        cutoff = now - self.window_sec
        counts = []
        for ip, timestamps in self._failures.items():
            active = sum(1 for t in timestamps if t >= cutoff)
            if active > 0:
                counts.append((ip, active))
        counts.sort(key=lambda x: x[1], reverse=True)
        return counts[:n]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Main IDS Class
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class IntrusionDetectionSystem:
    """
    Production-grade Intrusion Detection System.

    Combines rule-based event matching with behavioral anomaly
    detectors (CPU spikes, connection failures).  All alerts are
    emitted as IDSAlertEvent through the EventBus and simultaneously
    logged to security.log via structured logging.

    Architecture:
        EventBus ──publish──▶ IDS.evaluate()
                                │
                    ┌───────────┼────────────┐
                    ▼           ▼            ▼
              Rule Engine   CPU Detector  Conn Tracker
                    │           │            │
                    └───────────┼────────────┘
                                ▼
                        IDSAlertEvent ──▶ EventBus
    """

    def __init__(self) -> None:
        # Rule engine
        self.rules: List[IDSRule] = []
        self.alert_history: Deque[dict] = deque(maxlen=10_000)

        # Behavioral detectors
        self.cpu_detector = CPUAnomalyDetector()
        self.conn_tracker = ConnectionFailureTracker()

        # Statistics
        self.stats: Dict[str, int] = {
            "events_analyzed": 0,
            "alerts_generated": 0,
            "rules_matched": 0,
        }

        # EventBus reference (set during register_handlers)
        self._bus: Optional[EventBus] = None

    # ── Configuration ─────────────────────────────────────────

    def add_rule(self, rule: IDSRule) -> None:
        self.rules.append(rule)

    def load_default_rules(self) -> None:
        """Load production detection ruleset."""
        self.rules = [
            # ── Attack detection ──────────────────────────────
            IDSRule(
                rule_id="IDS-001",
                event_pattern="attack.*",
                threat_level=ThreatLevel.HIGH,
                description="Direct attack event detected",
                cooldown_sec=3.0,
            ),
            IDSRule(
                rule_id="IDS-002",
                event_pattern="attack.launched",
                threat_level=ThreatLevel.CRITICAL,
                description="Active attack launched against infrastructure",
                action=RuleAction.ALERT,
                cooldown_sec=1.0,
            ),

            # ── Infrastructure anomalies ──────────────────────
            IDSRule(
                rule_id="IDS-003",
                event_pattern="infra.resource_spike",
                threat_level=ThreatLevel.MEDIUM,
                description="Abnormal resource usage detected",
                cooldown_sec=10.0,
            ),
            IDSRule(
                rule_id="IDS-004",
                event_pattern="infra.network_failure",
                threat_level=ThreatLevel.CRITICAL,
                description="Network failure — possible attack vector",
                cooldown_sec=5.0,
            ),
            IDSRule(
                rule_id="IDS-005",
                event_pattern="infra.container_crash",
                threat_level=ThreatLevel.HIGH,
                description="Container crash — may indicate exploitation",
                cooldown_sec=5.0,
            ),

            # ── Firewall events ───────────────────────────────
            IDSRule(
                rule_id="IDS-006",
                event_pattern="security.firewall_block",
                threat_level=ThreatLevel.LOW,
                description="Firewall blocked traffic (informational)",
                action=RuleAction.LOG,
                cooldown_sec=15.0,
            ),
        ]

    # ── EventBus Integration ──────────────────────────────────

    def register_handlers(self, bus: EventBus) -> None:
        """Subscribe to all events for passive monitoring."""
        self._bus = bus
        bus.subscribe("*", self.evaluate, priority=EventPriority.NORMAL)

    # ── Core Analysis Pipeline ────────────────────────────────

    async def evaluate(self, event: BaseEvent) -> None:
        """
        Main analysis entry point — called for every event.

        Pipeline:
            1. Run rule-based matching.
            2. Feed data to behavioral detectors.
            3. Generate and publish alerts.
        """
        self.stats["events_analyzed"] += 1
        event_type = getattr(event, "event_type", "")

        # ── Guard: skip our own alert events to prevent recursion ──
        if event_type == "security.ids_alert":
            return

        # ── Phase 1: Rule-based detection ─────────────────────
        await self._evaluate_rules(event)

        # ── Phase 2: CPU anomaly detection ────────────────────
        if event_type == "infra.resource_spike":
            target_id = getattr(event, "target_id", "unknown")
            spike_val = getattr(event, "spike_value", 0.0)

            self.cpu_detector.record(target_id, spike_val)
            result = self.cpu_detector.analyze(target_id, spike_val)
            if result:
                threat_level, description = result
                await self._emit_alert(
                    rule_id="IDS-CPU-ANOMALY",
                    threat_level=threat_level,
                    description=description,
                    source_ip="",
                    related_event=event,
                )

        # ── Phase 3: Connection failure tracking ──────────────
        if event_type == "security.firewall_block":
            source_ip = getattr(event, "blocked_source", "unknown")
            result = self.conn_tracker.record_failure(
                source_ip, ts=getattr(event, "timestamp", time.time())
            )
            if result:
                threat_level, description = result
                await self._emit_alert(
                    rule_id="IDS-CONN-FLOOD",
                    threat_level=threat_level,
                    description=description,
                    source_ip=source_ip,
                    related_event=event,
                )

        # Also track attack events as potential connection floods
        if event_type.startswith("attack."):
            target_id = getattr(event, "target_id", "unknown")
            # Simulate a source IP from the attack metadata
            src = getattr(event, "payload", {}).get("source_ip", f"attacker-{target_id}")
            result = self.conn_tracker.record_failure(src)
            if result:
                threat_level, description = result
                await self._emit_alert(
                    rule_id="IDS-ATTACK-FLOOD",
                    threat_level=threat_level,
                    description=description,
                    source_ip=src,
                    related_event=event,
                )

    # ── Rule Engine ───────────────────────────────────────────

    async def _evaluate_rules(self, event: BaseEvent) -> None:
        """Match event against all active rules."""
        event_type = getattr(event, "event_type", "")
        target_id = (
            getattr(event, "target_id", None)
            or getattr(event, "container_id", None)
            or getattr(event, "affected_subnet", None)
            or "system"
        )

        for rule in self.rules:
            if not rule.matches(event_type):
                continue
            if not rule.can_fire(target_id):
                continue

            self.stats["rules_matched"] += 1
            rule.mark_fired(target_id)

            if rule.action in (RuleAction.ALERT, RuleAction.BLOCK):
                await self._emit_alert(
                    rule_id=rule.rule_id,
                    threat_level=rule.threat_level,
                    description=f"{rule.description} — event: {event_type}",
                    source_ip=getattr(event, "source_ip", ""),
                    related_event=event,
                )

            if rule.action == RuleAction.LOG:
                self._log_rule_match(rule, event)

    # ── Alert Emission ────────────────────────────────────────

    async def _emit_alert(
        self,
        rule_id: str,
        threat_level: ThreatLevel,
        description: str,
        source_ip: str = "",
        related_event: Optional[BaseEvent] = None,
    ) -> None:
        """Create an IDSAlertEvent and publish it on the EventBus."""
        self.stats["alerts_generated"] += 1

        alert = IDSAlertEvent(
            tick=getattr(related_event, "tick", 0),
            rule_id=rule_id,
            threat_level=threat_level,
            description=description,
            source_ip=source_ip,
        )

        # In-memory history
        alert_record = alert.model_dump()
        alert_record["related_event_id"] = (
            getattr(related_event, "id", None) if related_event else None
        )
        self.alert_history.append(alert_record)

        # Structured log
        _LOG_LEVELS = {
            ThreatLevel.INFO: 20,       # logging.INFO
            ThreatLevel.LOW: 20,        # logging.INFO
            ThreatLevel.MEDIUM: 30,     # logging.WARNING
            ThreatLevel.HIGH: 40,       # logging.ERROR
            ThreatLevel.CRITICAL: 50,   # logging.CRITICAL
        }
        numeric_level = _LOG_LEVELS.get(threat_level, 30)

        logger.log(
            numeric_level,
            f"[IDS ALERT] [{threat_level.value.upper()}] {description}",
            extra={
                "event_type": "security.ids_alert",
                "resource_id": source_ip or getattr(related_event, "target_id", None),
                "severity": threat_level.value,
                "metrics_snapshot": {
                    "events_analyzed": self.stats["events_analyzed"],
                    "total_alerts": self.stats["alerts_generated"],
                    "rule_id": rule_id,
                },
                "extra_data": alert_record,
            },
        )

        # Publish alert event (but avoid infinite recursion —
        # IDS alerts are published with a different event_type prefix
        # and our own subscription pattern excludes security.ids_alert
        # from triggering rule IDS-001/IDS-002)
        if self._bus:
            await self._bus.publish(alert)

    def _log_rule_match(self, rule: IDSRule, event: BaseEvent) -> None:
        """Log-only action for informational rules."""
        logger.info(
            f"[IDS LOG] Rule {rule.rule_id} matched: {rule.description}",
            extra={
                "event_type": event.event_type,
                "resource_id": getattr(event, "target_id", None),
                "severity": rule.threat_level.value,
                "metrics_snapshot": None,
            },
        )

    # ── Public Query API ──────────────────────────────────────

    def get_recent_alerts(self, count: int = 50) -> List[dict]:
        """Return the N most recent IDS alerts."""
        return list(self.alert_history)[-count:]

    def get_alerts_by_severity(self, min_level: ThreatLevel) -> List[dict]:
        """Return alerts at or above a given severity."""
        severity_order = {
            ThreatLevel.INFO: 0,
            ThreatLevel.LOW: 1,
            ThreatLevel.MEDIUM: 2,
            ThreatLevel.HIGH: 3,
            ThreatLevel.CRITICAL: 4,
        }
        min_val = severity_order.get(min_level, 0)
        return [
            a for a in self.alert_history
            if severity_order.get(ThreatLevel(a.get("threat_level", "info")), 0) >= min_val
        ]

    def get_stats(self) -> Dict[str, int]:
        return dict(self.stats)

    def get_top_offenders(self, n: int = 5) -> List[Tuple[str, int]]:
        """Delegate to the connection failure tracker."""
        return self.conn_tracker.get_top_offenders(n)
