"""
Domain models for the Infrastructure layer.

Replaces the old flat models.py with a richer hierarchy:
  VM → hosts Containers → runs Services
  Network → contains Subnets → connects VMs
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


# ── Status Enums ──────────────────────────────────────────────

class VMStatus(str, Enum):
    RUNNING      = "RUNNING"
    STOPPED      = "STOPPED"
    COMPROMISED  = "COMPROMISED"


class ContainerStatus(str, Enum):
    RUNNING  = "RUNNING"
    STOPPED  = "STOPPED"
    CRASHED  = "CRASHED"
    CREATING = "CREATING"


# ── Leaf Models ───────────────────────────────────────────────

class Service(BaseModel):
    """A process running inside a Container."""
    name: str
    port: int
    protocol: str = "tcp"
    healthy: bool = True


class Container(BaseModel):
    """
    Lightweight compute unit running inside a VM.

    Resources are expressed as fractions of the parent VM's capacity.
    """
    id: str
    name: str
    cpu_usage: float = 0.0       # 0-100 %
    memory_usage: int = 0        # bytes
    memory_limit: int = 512 * 1024 * 1024  # 512 MB default
    status: ContainerStatus = ContainerStatus.RUNNING
    services: List[Service] = Field(default_factory=list)
    vm_id: str = ""              # parent VM


class VM(BaseModel):
    """
    Virtual Machine — the primary compute host.

    A VM owns zero or more Containers and connects to one Subnet.
    """
    id: str
    name: str
    cpu_cores: int = 2
    cpu_usage: float = 0.0       # aggregate %
    memory_total: int = 4 * 1024 * 1024 * 1024   # 4 GB
    memory_used: int = 0
    status: VMStatus = VMStatus.RUNNING
    subnet_id: str = ""
    container_ids: List[str] = Field(default_factory=list)


# ── Network Models ────────────────────────────────────────────

class Subnet(BaseModel):
    """A logical network segment."""
    id: str
    cidr: str = "10.0.0.0/24"
    gateway: str = "10.0.0.1"
    is_healthy: bool = True


class Network(BaseModel):
    """Top-level network topology container."""
    id: str
    name: str = "default"
    subnets: Dict[str, Subnet] = Field(default_factory=dict)
