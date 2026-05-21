"""Codex session normalization and display helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .models import SessionSummary
from .utils import (
    clean_text,
    display_width,
    first_value,
    format_row,
    format_time,
    nested_value,
    parse_sort_time,
    project_name,
    truncate,
)


TABLE_HEADERS = {
    "en": ("Index", "Title", "Project", "Branch", "Updated"),
    "zh": ("序号", "标题", "项目", "分支", "最后时间"),
}


def default_codex_home() -> Path:
    if env_path := os.getenv("CODEX_HOME"):
        return Path(env_path).expanduser().resolve()
    return Path.home() / ".codex"


def normalize_sessions(
    sessions_data: Any,
    codex_home: Optional[Path] = None,
    limit: Optional[int] = None,
) -> List[SessionSummary]:
    raw_sessions = extract_session_list(sessions_data)
    resolved_codex_home = codex_home or default_codex_home()
    index = read_session_index(resolved_codex_home)

    summaries = [build_session_summary(item, index, resolved_codex_home) for item in raw_sessions]
    summaries = sorted(summaries, key=lambda s: (s.pinned, parse_sort_time(s.updated_at)), reverse=True)
    for index, summary in enumerate(summaries, start=1):
        summary.index = index
    return summaries[:limit] if limit else summaries


def extract_session_list(sessions_data: Any) -> List[Dict[str, Any]]:
    if isinstance(sessions_data, list):
        return [item for item in sessions_data if isinstance(item, dict)]
    if not isinstance(sessions_data, dict):
        return []
    for key in ("threads", "items", "data", "result", "sessions"):
        value = sessions_data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def read_session_index(codex_home: Path) -> Dict[str, Dict[str, Any]]:
    index_path = codex_home / "session_index.jsonl"
    entries: Dict[str, Dict[str, Any]] = {}
    if not index_path.exists():
        return entries

    try:
        with index_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                thread_id = str(item.get("id") or "")
                if thread_id:
                    entries[thread_id] = {**entries.get(thread_id, {}), **item}
    except OSError:
        return entries
    return entries


def build_session_summary(
    session: Dict[str, Any],
    index: Dict[str, Dict[str, Any]],
    codex_home: Path,
) -> SessionSummary:
    thread_id = str(first_value(session, ("id", "thread_id", "threadId")) or "")
    indexed = index.get(thread_id, {})
    merged = {**session, **indexed}
    log_path = first_value(merged, ("path", "log_path", "logPath", "jsonl_path", "jsonlPath"))
    if not log_path and thread_id:
        log_path = find_session_log(codex_home, thread_id)
    log_meta = read_log_meta(Path(log_path)) if log_path else {}

    title = truncate(
        clean_text(
            first_value(
                {**merged, **log_meta},
                ("thread_name", "threadName", "title", "name", "summary", "preview"),
            )
        ),
        80,
    )
    if not title:
        title = first_user_message(Path(log_path)) if log_path else ""
    if not title:
        title = "[Untitled]"

    cwd = clean_text(
        first_value(
            {**log_meta, **merged},
            ("cwd", "workspace", "workspacePath", "projectPath", "repoPath"),
        )
    )
    project = project_name(cwd) or clean_text(first_value(merged, ("project", "repo", "repository"))) or "-"
    branch = clean_text(
        nested_value(merged, ("gitInfo", "branch"))
        or nested_value(merged, ("git_info", "branch"))
        or first_value(merged, ("branch", "gitBranch", "git_branch"))
        or "-"
    )
    updated_at = format_time(
        first_value(merged, ("updated_at", "updatedAt", "lastUpdatedAt", "created_at", "createdAt"))
        or first_value(log_meta, ("timestamp",))
    )
    pinned = bool(
        first_value(merged, ("pinned", "isPinned", "is_pinned", "pin", "starred", "favorite"))
        or first_value(log_meta, ("pinned", "isPinned", "is_pinned"))
        or first_value(merged, ("pinnedAt", "pinned_at"))
    )

    return SessionSummary(
        index=0,
        title=title,
        project=project,
        branch=branch,
        updated_at=updated_at or "-",
        thread_id=thread_id,
        pinned=pinned,
        preview=truncate(clean_text(first_value(merged, ("preview", "summary"))), 240),
        path=str(log_path or ""),
    )


def find_session_log(codex_home: Path, thread_id: str) -> str:
    path = find_session_path(codex_home, thread_id)
    return str(path) if path else ""


def find_session_path(codex_home: Path, thread_id: str) -> Optional[Path]:
    roots = [codex_home / "sessions", codex_home / "archived_sessions"]
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.jsonl"):
            if thread_id in path.name:
                return path
    return None


def read_log_meta(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            for _ in range(80):
                line = handle.readline()
                if not line:
                    break
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("type") == "session_meta":
                    payload = entry.get("payload")
                    return payload if isinstance(payload, dict) else {}
    except OSError:
        return {}
    return {}


def first_user_message(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        with path.open("r", encoding="utf-8") as handle:
            for _ in range(200):
                line = handle.readline()
                if not line:
                    break
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                payload = entry.get("payload")
                if isinstance(payload, dict):
                    message = payload.get("user_message")
                    if message:
                        return clean_text(message)[:80]
    except OSError:
        return ""
    return ""


def read_last_messages(path: Path, count: int = 5) -> List[str]:
    messages: List[str] = []
    if not path.exists():
        return messages
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                payload = entry.get("payload")
                if isinstance(payload, dict) and payload.get("user_message"):
                    messages.append(clean_text(payload.get("user_message")))
    except OSError:
        return messages
    return messages[-count:]


def render_table(summaries: List[SessionSummary], lang: str = "en") -> str:
    headers = TABLE_HEADERS.get(lang, TABLE_HEADERS["en"])
    rows = [
        (
            str(item.index),
            ("[Pinned] " if item.pinned and lang == "en" else "[置顶] " if item.pinned else "") + item.title,
            item.project,
            item.branch,
            item.updated_at,
        )
        for item in summaries
    ]
    widths = [
        max(display_width(row[index]) for row in [headers, *rows]) if rows else display_width(headers[index])
        for index in range(5)
    ]
    lines = [format_row(headers, widths), format_row(tuple("-" * width for width in widths), widths)]
    lines.extend(format_row(row, widths) for row in rows)
    return "\n".join(lines)
