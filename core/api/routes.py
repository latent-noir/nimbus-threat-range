"""
FastAPI REST routes for the simulation engine.

Provides endpoints for state observation, attack injection,
event log retrieval, and time-series metrics.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import APIRouter, Query

from engine.engine import SimulationEngine
from events.attack_events import AttackType
from api.websocket import set_engine

router = APIRouter()

# ── Engine singleton ──────────────────────────────────────────
engine = SimulationEngine()


@asynccontextmanager
async def lifespan(app) -> AsyncGenerator:
    """Initialize infrastructure and start the simulation loop."""
    engine.initialize(vm_count=3, containers_per_vm=2)
    set_engine(engine)  # Wire WebSocket endpoint
    task = asyncio.create_task(engine.start())
    yield
    engine.stop()
    task.cancel()


# ── State ─────────────────────────────────────────────────────

@router.get("/state")
async def get_state():
    """Full simulation state snapshot."""
    return engine.get_state()


# ── Attack Injection ──────────────────────────────────────────

@router.post("/inject")
async def inject_attack(
    target_id: str = Query(..., description="Target VM or container ID"),
    attack_type: str = Query("ddos", description="Attack type"),
    severity: int = Query(80, ge=1, le=100, description="Severity 1-100"),
    duration_ms: int = Query(5000, ge=100, le=60000, description="Duration in ms"),
):
    """Inject an attack event into the simulation."""
    # Validate attack type
    valid_types = {t.value for t in AttackType}
    if attack_type not in valid_types:
        return {"error": f"Invalid attack type. Valid: {sorted(valid_types)}"}

    await engine.inject_attack(target_id, attack_type, severity, duration_ms)
    return {"status": "injected", "target": target_id, "type": attack_type}


# ── Events & Metrics ─────────────────────────────────────────

@router.get("/events")
async def get_events(count: int = Query(50, ge=1, le=500)):
    """Retrieve recent events from the event logger."""
    return engine.event_logger.get_recent(count)


@router.get("/metrics/{entity_id}/{metric_name}")
async def get_metrics(entity_id: str, metric_name: str, last_n: int = 60):
    """Retrieve time-series data for a specific metric."""
    points = engine.metric_store.get_series(entity_id, metric_name, last_n)
    return [{"tick": p.tick, "value": p.value} for p in points]


@router.get("/audit")
async def get_audit(count: int = 100):
    """Retrieve security audit trail entries."""
    return engine.audit_trail.get_entries(count)


# ── IDS ───────────────────────────────────────────────────────

@router.get("/ids/alerts")
async def get_ids_alerts(count: int = 50, min_severity: str = "low"):
    """Retrieve recent IDS alerts, optionally filtered by severity."""
    from events.security_events import ThreatLevel
    if min_severity != "low":
        try:
            return engine.ids.get_alerts_by_severity(ThreatLevel(min_severity))
        except ValueError:
            return {"error": f"Invalid severity level: {min_severity}"}
    return engine.ids.get_recent_alerts(count)


@router.get("/ids/stats")
async def get_ids_stats():
    """IDS processing statistics."""
    return engine.ids.get_stats()


@router.get("/ids/offenders")
async def get_top_offenders(n: int = 5):
    """Top source IPs by connection failure count."""
    offenders = engine.ids.get_top_offenders(n)
    return [{"source_ip": ip, "failure_count": count} for ip, count in offenders]
