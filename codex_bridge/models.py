"""Data models for AgentCodex."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any


@dataclass
class PendingRequest:
    event: threading.Event
    result: Any = None
    error: Any = None


@dataclass
class CacheEntry:
    value: Any
    stored_at: float
    fresh_ttl: int
    stale_ttl: int


@dataclass
class SessionSummary:
    index: int
    title: str
    project: str
    branch: str
    updated_at: str
    thread_id: str
    pinned: bool = False
    preview: str = ""
    path: str = ""
