"""
Tests for the core simulation engine.

Validates initialization, tick execution, state snapshots, and attack injection.
"""

import pytest
import asyncio
from engine.engine import SimulationEngine


@pytest.mark.asyncio
async def test_engine_initialization():
    """Engine should bootstrap VMs and containers correctly."""
    engine = SimulationEngine()
    engine.initialize(vm_count=3, containers_per_vm=2)

    state = engine.get_state()
    assert state["metrics"]["total_vms"] == 3
    assert state["metrics"]["total_containers"] == 6
    assert len(state["vms"]) == 3
    assert len(state["containers"]) == 6

    # Verify container IDs follow expected pattern
    container_ids = {c["id"] for c in state["containers"]}
    assert "c-000-00" in container_ids
    assert "c-002-01" in container_ids


@pytest.mark.asyncio
async def test_engine_tick():
    """A single tick should cause CPU/memory drift on containers."""
    engine = SimulationEngine()
    engine.initialize(vm_count=1, containers_per_vm=1)

    # Run multiple ticks to ensure drift occurs
    for _ in range(5):
        await engine.tick()

    state = engine.get_state()
    containers = state["containers"]
    assert len(containers) == 1

    # After 5 ticks, CPU or memory should have drifted from initial 0
    c = containers[0]
    assert c["cpu_usage"] != 0.0 or c["memory_usage"] != 0


@pytest.mark.asyncio
async def test_engine_attack_injection():
    """Injecting an attack should generate events in the log."""
    engine = SimulationEngine()
    engine.initialize(vm_count=1, containers_per_vm=1)

    # Inject a DDoS attack
    container_id = "c-000-00"
    await engine.inject_attack(container_id, "ddos", severity=90, duration_ms=3000)

    # Flush events
    await engine.bus.flush()

    # Check that attack events were recorded
    recent = engine.event_logger.get_recent(50)
    attack_events = [e for e in recent if e.get("event_type", "").startswith("attack.")]
    assert len(attack_events) > 0


@pytest.mark.asyncio
async def test_get_state_structure():
    """get_state() should return all expected keys."""
    engine = SimulationEngine()
    engine.initialize(vm_count=2, containers_per_vm=1)

    state = engine.get_state()
    assert "tick" in state
    assert "timestamp" in state
    assert "vms" in state
    assert "containers" in state
    assert "networks" in state
    assert "metrics" in state
    assert "recent_events" in state
    assert "total_vms" in state["metrics"]
    assert "total_containers" in state["metrics"]
    assert "global_cpu_load" in state["metrics"]


@pytest.mark.asyncio
async def test_engine_stop():
    """Stopping the engine should set running to False."""
    engine = SimulationEngine()
    engine.initialize(vm_count=1, containers_per_vm=1)
    engine.running = True
    engine.stop()
    assert engine.running is False
