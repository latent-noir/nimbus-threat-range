"""
Production logging configuration.

Sets up structured JSON logging with domain-specific log files:
    - logs/infrastructure.log  →  infra.* events
    - logs/attacks.log         →  attack.* events
    - logs/security.log        →  security.* events

Each log record contains:
    timestamp, event_type, resource_id, severity, metrics_snapshot

Uses Python's built-in logging with a custom JSON formatter — no
third-party dependencies required.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Any, Dict

# ── Constants ─────────────────────────────────────────────────

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")

DOMAIN_MAP: Dict[str, str] = {
    "infrastructure": "infrastructure.log",
    "attacks":        "attacks.log",
    "security":       "security.log",
}

MAX_BYTES    = 10 * 1024 * 1024   # 10 MB per file
BACKUP_COUNT = 5                   # keep 5 rotated files


# ── JSON Formatter ────────────────────────────────────────────

class StructuredJSONFormatter(logging.Formatter):
    """
    Produces one JSON object per line.

    Output schema:
    {
        "timestamp":        "2026-02-17T23:16:36.123456Z",
        "level":            "INFO",
        "logger":           "cloud_sim.infra",
        "event_type":       "infra.resource_spike",
        "resource_id":      "vm-001",
        "severity":         "high",
        "message":          "...",
        "metrics_snapshot":  { ... },
        "extra":            { ... }
    }
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level":       record.levelname,
            "logger":      record.name,
            "event_type":  getattr(record, "event_type", "system"),
            "resource_id": getattr(record, "resource_id", None),
            "severity":    getattr(record, "severity", "info"),
            "message":     record.getMessage(),
            "metrics_snapshot": getattr(record, "metrics_snapshot", None),
        }

        # Merge any extra fields passed via `extra={}`
        extra = getattr(record, "extra_data", None)
        if extra:
            log_entry["extra"] = extra

        # Include exception info if present
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


# ── Logger Factory ────────────────────────────────────────────

def _ensure_log_dir() -> None:
    os.makedirs(LOG_DIR, exist_ok=True)


def _create_file_handler(filename: str) -> RotatingFileHandler:
    """Rotating file handler writing JSON lines."""
    _ensure_log_dir()
    handler = RotatingFileHandler(
        os.path.join(LOG_DIR, filename),
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(StructuredJSONFormatter())
    handler.setLevel(logging.DEBUG)
    return handler


def _create_console_handler() -> logging.StreamHandler:
    """Stderr handler for real-time visibility during development."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(StructuredJSONFormatter())
    handler.setLevel(logging.INFO)
    return handler


def setup_logging(console: bool = True) -> Dict[str, logging.Logger]:
    """
    Configure and return the three domain loggers.

    Returns:
        {
            "infrastructure": Logger,
            "attacks":        Logger,
            "security":       Logger,
        }

    Usage:
        loggers = setup_logging()
        loggers["infrastructure"].info(
            "CPU spike on vm-001",
            extra={
                "event_type": "infra.resource_spike",
                "resource_id": "vm-001",
                "severity": "high",
                "metrics_snapshot": {"cpu": 98.2},
            },
        )
    """
    loggers: Dict[str, logging.Logger] = {}

    for domain, filename in DOMAIN_MAP.items():
        logger = logging.getLogger(f"cloud_sim.{domain}")
        logger.setLevel(logging.DEBUG)
        logger.propagate = False  # prevent duplicate output

        # Clear any existing handlers (enables re-initialization)
        logger.handlers.clear()

        # File handler: rotated JSON lines
        logger.addHandler(_create_file_handler(filename))

        # Console handler: optional stderr output
        if console:
            logger.addHandler(_create_console_handler())

        loggers[domain] = logger

    return loggers


def get_domain_logger(domain: str) -> logging.Logger:
    """
    Shortcut to retrieve an already-configured domain logger.

    Args:
        domain: One of "infrastructure", "attacks", "security".
    """
    return logging.getLogger(f"cloud_sim.{domain}")
