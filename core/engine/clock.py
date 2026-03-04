"""
Simulation clock — manages discrete time steps.

The clock is the heartbeat of the simulation. Each call to advance()
increments the tick counter and returns the new tick number.
"""

from __future__ import annotations


class SimulationClock:
    """
    Discrete-time clock for the simulation engine.

    Attributes:
        current_tick:    The current simulation tick (starts at 0).
        tick_interval:   Wall-clock seconds between ticks.
        max_ticks:       Optional upper bound (0 = unlimited).
    """

    def __init__(self, tick_interval: float = 1.0, max_ticks: int = 0) -> None:
        self.current_tick: int = 0
        self.tick_interval: float = tick_interval
        self.max_ticks: int = max_ticks

    def advance(self) -> int:
        """Increment the tick counter and return the new value."""
        self.current_tick += 1
        return self.current_tick

    def reset(self) -> None:
        """Reset the clock to tick 0."""
        self.current_tick = 0

    @property
    def is_expired(self) -> bool:
        """True if max_ticks is set and we've reached it."""
        if self.max_ticks <= 0:
            return False
        return self.current_tick >= self.max_ticks

    def __repr__(self) -> str:
        return f"SimulationClock(tick={self.current_tick}, interval={self.tick_interval}s)"
