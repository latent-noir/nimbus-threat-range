"""
WebSocket endpoint for real-time event streaming.

The visualization dashboard connects here to receive live
simulation events and state updates without polling.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

if TYPE_CHECKING:
    from engine.engine import SimulationEngine

router = APIRouter()
logger = logging.getLogger("cloud_sim.websocket")

# Will be set by routes.py after engine creation
_engine: SimulationEngine | None = None


def set_engine(engine: SimulationEngine) -> None:
    """Called by routes.py to wire the engine reference."""
    global _engine
    _engine = engine


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    """
    Stream simulation state to the connected dashboard.

    Protocol:
        - Server pushes a JSON state snapshot every tick.
        - Client can send JSON commands: {"action": "inject", ...}
    """
    await ws.accept()
    logger.info("WebSocket client connected")

    async def send_loop() -> None:
        """Continuously push state snapshots to the client."""
        try:
            while True:
                if _engine is not None:
                    state = _engine.get_state()
                    await ws.send_json(state)
                await asyncio.sleep(1.0)
        except Exception:
            pass  # Connection closed

    async def receive_loop() -> None:
        """Listen for client commands and process them."""
        try:
            while True:
                data = await ws.receive_text()
                try:
                    message = json.loads(data)
                    action = message.get("action")

                    if action == "inject" and _engine is not None:
                        target_id = str(message.get("target_id", "")).strip()
                        attack_type = str(message.get("attack_type", "ddos"))
                        severity = message.get("severity", 80)
                        duration_ms = message.get("duration_ms", 5000)

                        # ── Input validation ────────────────────
                        if not target_id:
                            await ws.send_json({"type": "error", "message": "target_id is required"})
                            continue
                        if not isinstance(severity, (int, float)):
                            severity = 80
                        severity = max(1, min(100, int(severity)))
                        if not isinstance(duration_ms, (int, float)):
                            duration_ms = 5000
                        duration_ms = max(100, min(60000, int(duration_ms)))

                        await _engine.inject_attack(
                            target_id, attack_type, severity, duration_ms
                        )
                        await ws.send_json({
                            "type": "response",
                            "status": "injected",
                            "target": target_id,
                        })
                    elif action == "state" and _engine is not None:
                        state = _engine.get_state()
                        await ws.send_json(state)
                    else:
                        await ws.send_json({
                            "type": "error",
                            "message": f"Unknown action: {action}",
                        })
                except json.JSONDecodeError:
                    await ws.send_json({
                        "type": "error",
                        "message": "Invalid JSON",
                    })
        except WebSocketDisconnect:
            pass
        except Exception:
            pass

    try:
        # Run send and receive concurrently
        send_task = asyncio.create_task(send_loop())
        receive_task = asyncio.create_task(receive_loop())

        # Wait for either to complete (usually means disconnect)
        done, pending = await asyncio.wait(
            [send_task, receive_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Cancel the remaining task
        for task in pending:
            task.cancel()

    except WebSocketDisconnect:
        pass
    finally:
        logger.info("WebSocket client disconnected")
