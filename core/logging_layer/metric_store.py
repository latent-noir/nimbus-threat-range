"""
In-memory time-series metric store.

Captures per-tick snapshots of resource usage for every VM and Container
so the visualization layer can render historical charts.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Deque, Dict, List, NamedTuple


class MetricPoint(NamedTuple):
    tick: int
    value: float


class MetricStore:
    """
    Ring-buffer metric store keyed by (entity_id, metric_name).

    Example keys:
        ("vm-001", "cpu_usage")
        ("c-003", "memory_usage")
    """

    MAX_POINTS = 3600  # ~1 hour at 1 tick/sec

    def __init__(self) -> None:
        self._series: Dict[str, Deque[MetricPoint]] = defaultdict(
            lambda: deque(maxlen=self.MAX_POINTS)
        )

    # ── Write ─────────────────────────────────────────────────

    def record(self, entity_id: str, metric_name: str, tick: int, value: float) -> None:
        """Append a single data point."""
        key = f"{entity_id}:{metric_name}"
        self._series[key].append(MetricPoint(tick=tick, value=value))

    # ── Read ──────────────────────────────────────────────────

    def get_series(self, entity_id: str, metric_name: str, last_n: int = 60) -> List[MetricPoint]:
        """Return the most recent N points for a metric."""
        key = f"{entity_id}:{metric_name}"
        series = self._series.get(key, deque())
        return list(series)[-last_n:]

    def get_latest(self, entity_id: str, metric_name: str) -> float | None:
        """Return the most recent value, or None."""
        key = f"{entity_id}:{metric_name}"
        series = self._series.get(key)
        if series:
            return series[-1].value
        return None

    def list_entities(self) -> List[str]:
        """Return all entity IDs that have recorded metrics."""
        return list({k.split(":")[0] for k in self._series})
