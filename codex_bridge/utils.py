"""Shared utility functions for AgentCodex."""

from __future__ import annotations

import datetime as dt
import json
import unicodedata
from pathlib import Path
from typing import Any, Dict, Iterable, List


def first_value(source: Dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        value = source.get(key)
        if value not in (None, ""):
            return value
    return None


def nested_value(source: Dict[str, Any], path: Iterable[str]) -> Any:
    current: Any = source
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\n", " ").split())


def truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: max(limit - 1, 0)] + "..."


def project_name(path_or_name: str) -> str:
    if not path_or_name:
        return ""
    return Path(path_or_name).name or path_or_name


def format_time(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, (int, float)):
        timestamp = value / 1000 if value > 10_000_000_000 else value
        return dt.datetime.fromtimestamp(timestamp).strftime("%m-%d %H:%M")
    text = str(value).strip()
    try:
        parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.astimezone().strftime("%m-%d %H:%M")
    except ValueError:
        return text


def parse_sort_time(value: str) -> float:
    if not value or value == "-":
        return 0
    try:
        current_year = dt.datetime.now().year
        parsed = dt.datetime.strptime("{} {}".format(current_year, value), "%Y %m-%d %H:%M")
        return parsed.timestamp()
    except ValueError:
        return 0


def display_width(text: str) -> int:
    width = 0
    for char in str(text):
        width += 2 if unicodedata.east_asian_width(char) in ("F", "W") else 1
    return width


def format_row(row: Iterable[str], widths: List[int]) -> str:
    cells = []
    for index, value in enumerate(row):
        text = str(value)
        cells.append(text + " " * max(widths[index] - display_width(text), 0))
    return " | ".join(cells)


def stable_json_key(method: str, params: Dict[str, Any]) -> str:
    try:
        return "{}:{}".format(method, json.dumps(params or {}, sort_keys=True, ensure_ascii=False))
    except (TypeError, ValueError):
        return ""
