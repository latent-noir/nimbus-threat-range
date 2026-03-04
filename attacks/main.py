"""
Attack CLI — inject faults into the running simulation engine.

Uses Typer for CLI parsing and httpx for async HTTP requests.
"""

import typer
import httpx
import asyncio
import time
from rich.console import Console
from rich.table import Table

app = typer.Typer()
console = Console()
CORE_URL = "http://localhost:8000/simulation"


async def inject_fault(target: str, attack_type: str, duration: int) -> None:
    """Inject a single fault via the simulation API."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{CORE_URL}/inject",
                params={
                    "target_id": target,
                    "attack_type": attack_type,
                    "severity": 80,
                    "duration_ms": duration,
                },
            )
            response.raise_for_status()
            console.print(f"[green]Successfully injected {attack_type} on {target}[/green]")
        except httpx.HTTPStatusError as e:
            console.print(f"[red]HTTP error injecting fault: {e.response.status_code}[/red]")
        except Exception as e:
            console.print(f"[red]Failed to inject fault: {e}[/red]")


async def get_system_state() -> dict | None:
    """Fetch the current simulation state from the API."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{CORE_URL}/state")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            console.print(f"[red]Failed to get state: {e}[/red]")
            return None


@app.command()
def attack(target: str, attack_type: str = "ddos", duration: int = 5000) -> None:
    """Inject a fault into a specific container."""
    asyncio.run(inject_fault(target, attack_type, duration))


@app.command()
def scan() -> None:
    """List all active containers and their status."""
    data = asyncio.run(get_system_state())
    if data:
        table = Table(title="System State")
        table.add_column("Container ID", style="cyan")
        table.add_column("Name", style="magenta")
        table.add_column("CPU %", style="green")
        table.add_column("Status", style="yellow")

        for c in data.get("containers", []):
            table.add_row(c["id"], c["name"], f"{c['cpu_usage']:.1f}", c["status"])

        console.print(table)


@app.command()
def ddos(duration: int = 10000) -> None:
    """Simulate a DDoS attack by spiking CPU on all containers."""

    async def _run() -> None:
        data = await get_system_state()
        if not data:
            return
        containers = data.get("containers", [])
        if not containers:
            console.print("[yellow]No containers found.[/yellow]")
            return
        console.print(f"[bold red]Initializing DDoS on {len(containers)} containers...[/bold red]")
        tasks = [inject_fault(c["id"], "ddos", duration) for c in containers]
        await asyncio.gather(*tasks)

    asyncio.run(_run())


if __name__ == "__main__":
    app()
