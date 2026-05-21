# -*- coding: utf-8 -*-
"""Small JSON-RPC bridge for local Codex app-server sessions."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import threading
import time
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


DEFAULT_CODEX_BINARY = "/Applications/Codex.app/Contents/Resources/codex"
DEFAULT_TIMEOUT_SECONDS = 15
TABLE_HEADERS = {
    "en": ("Index", "Title", "Project", "Branch", "Updated"),
    "zh": ("序号", "标题", "项目", "分支", "最后时间"),
}
MESSAGES = {
    "en": {
        "available": "Codex app-server is available",
        "restarted": "Codex app-server restarted",
        "no_process": "No app-server process is owned by this bridge command",
        "session_list": "Codex sessions (top {}):",
    },
    "zh": {
        "available": "Codex app-server 可用",
        "restarted": "Codex app-server 已重启",
        "no_process": "当前桥接进程没有运行中的 app-server",
        "session_list": "Codex 会话列表（前 {} 个）:",
    },
}


class CodexBridgeError(RuntimeError):
    """Raised when the bridge cannot communicate with Codex."""


@dataclass
class PendingRequest:
    event: threading.Event
    result: Any = None
    error: Any = None


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


class CodexClient:
    def __init__(
        self,
        codex_binary: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        verbose: bool = False,
    ):
        self.codex_binary = codex_binary or os.environ.get("CODEX_BINARY", DEFAULT_CODEX_BINARY)
        self.timeout = timeout
        self.verbose = verbose
        self.process: Optional[subprocess.Popen[bytes]] = None
        self.request_id = 1
        self.pending_requests: Dict[int, PendingRequest] = {}
        self.lock = threading.Lock()
        self._stdout_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None

    def connect(self) -> None:
        if self.process and self.process.poll() is None:
            return

        if not os.path.exists(self.codex_binary):
            raise CodexBridgeError(
                "找不到 Codex 可执行文件: {}。可通过 CODEX_BINARY 指定路径。".format(
                    self.codex_binary
                )
            )

        self._log("正在启动 Codex app-server...")
        self.process = subprocess.Popen(
            [self.codex_binary, "app-server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        self._stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
        self._stdout_thread = threading.Thread(target=self._read_stdout, daemon=True)
        self._stderr_thread.start()
        self._stdout_thread.start()

        time.sleep(0.3)
        if self.process.poll() is not None:
            raise CodexBridgeError("app-server 进程意外退出")

        self._send_request(
            "initialize",
            {
                "clientInfo": {
                    "name": "agentcodex-python-client",
                    "title": "AgentCodex Python Client",
                    "version": "0.1.0",
                },
                "capabilities": {
                    "experimentalApi": True,
                    "requestAttestation": False,
                },
            },
        )
        self._log("连接成功")

    def _log(self, message: str) -> None:
        if self.verbose:
            print("[CodexBridge] {}".format(message), file=sys.stderr)

    def _read_stderr(self) -> None:
        if not self.process or not self.process.stderr:
            return
        for line in iter(self.process.stderr.readline, b""):
            text = line.decode("utf-8", errors="replace").strip()
            if text and self.verbose:
                print("[CodexServer] {}".format(text), file=sys.stderr)

    def _read_stdout(self) -> None:
        if not self.process or not self.process.stdout:
            return
        for raw_line in iter(self.process.stdout.readline, b""):
            if not raw_line.strip():
                continue
            try:
                message = json.loads(raw_line.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                self._log("跳过无法解析的响应: {}".format(exc))
                continue
            self._handle_message(message)

    def _handle_message(self, message: Dict[str, Any]) -> None:
        req_id = message.get("id")
        if req_id is None:
            return
        with self.lock:
            entry = self.pending_requests.pop(req_id, None)
        if not entry:
            return
        entry.error = message.get("error")
        entry.result = message.get("result")
        entry.event.set()

    def _next_request_id(self) -> int:
        with self.lock:
            req_id = self.request_id
            self.request_id += 1
        return req_id

    def _send_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        if not self.process or not self.process.stdin or self.process.poll() is not None:
            raise CodexBridgeError("Codex app-server 未连接")

        req_id = self._next_request_id()
        entry = PendingRequest(event=threading.Event())
        with self.lock:
            self.pending_requests[req_id] = entry

        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": req_id,
        }
        try:
            self.process.stdin.write((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
            self.process.stdin.flush()
        except BrokenPipeError as exc:
            with self.lock:
                self.pending_requests.pop(req_id, None)
            raise CodexBridgeError("发送请求失败，app-server 管道已关闭") from exc

        if not entry.event.wait(self.timeout):
            with self.lock:
                self.pending_requests.pop(req_id, None)
            raise CodexBridgeError("Request {} timed out after {}s".format(method, self.timeout))

        if entry.error:
            raise CodexBridgeError(str(entry.error))
        return entry.result

    def list_sessions(self) -> Any:
        return self._send_request("thread/list")

    def get_session(self, thread_id: str) -> Any:
        return self._send_request("thread/read", {"threadId": thread_id, "thread_id": thread_id})

    def send_message(self, thread_id: str, text: str) -> Any:
        return self._send_request(
            "turn:start",
            {
                "thread_id": thread_id,
                "threadId": thread_id,
                "input": [{"role": "user", "content": [{"type": "text", "text": text}]}],
            },
        )

    def close(self) -> None:
        if not self.process:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)

    def __enter__(self) -> "CodexClient":
        self.connect()
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


def normalize_sessions(
    sessions_data: Any,
    codex_home: Optional[Path] = None,
    limit: Optional[int] = None,
) -> List[SessionSummary]:
    raw_sessions = extract_session_list(sessions_data)
    codex_home = codex_home or Path.home() / ".codex"
    index = read_session_index(codex_home)

    summaries = [build_session_summary(item, index, codex_home) for item in raw_sessions]
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
    roots = [codex_home / "sessions", codex_home / "archived_sessions"]
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.jsonl"):
            if thread_id in path.name:
                return str(path)
    return ""


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
    return value[: max(limit - 1, 0)] + "…"


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


def render_table(summaries: List[SessionSummary], lang: str = "en") -> str:
    headers = TABLE_HEADERS.get(lang, TABLE_HEADERS["en"])
    rows = [
        (
            str(item.index),
            ("[置顶] " if item.pinned else "") + item.title,
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Agent-friendly Codex app-server bridge")
    parser.add_argument("--json", action="store_true", help="Output stable JSON for agents")
    parser.add_argument("--verbose", action="store_true", help="Print bridge debug logs")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS, help="JSON-RPC timeout seconds")
    parser.add_argument("--lang", choices=("en", "zh"), default="en", help="Human-readable output language")
    subparsers = parser.add_subparsers(dest="command")

    list_parser = subparsers.add_parser("list", help="List Codex sessions")
    list_parser.add_argument("--limit", type=int, default=10, help="Number of sessions to return")

    read_parser = subparsers.add_parser("read", help="Read a Codex session")
    read_parser.add_argument("thread_id", nargs="?")
    read_parser.add_argument("--index", type=int, help="Read by current list index")
    read_parser.add_argument("--limit", type=int, default=10, help="List range used when reading by index")

    send_parser = subparsers.add_parser("send", help="Send a message to a Codex session")
    send_parser.add_argument("thread_id")
    send_parser.add_argument("message")

    subparsers.add_parser("start", help="Start and check Codex app-server")
    subparsers.add_parser("check", help="Check Codex app-server")
    subparsers.add_parser("restart", help="Restart app-server owned by this bridge command")
    subparsers.add_parser("stop", help="Stop app-server owned by this bridge command")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "list"
    messages = MESSAGES.get(args.lang, MESSAGES["en"])

    client = CodexClient(timeout=args.timeout, verbose=args.verbose)
    try:
        if command == "stop":
            client.close()
            print(messages["no_process"] if not args.json else json.dumps({"ok": True}))
            return 0

        client.connect()

        if command in ("start", "check"):
            output = {"ok": True, "message": messages["available"]}
        elif command == "restart":
            client.close()
            client.connect()
            output = {"ok": True, "message": messages["restarted"]}
        elif command == "list":
            limit = getattr(args, "limit", 10)
            sessions = normalize_sessions(client.list_sessions(), limit=limit)
            if args.json:
                output = {"ok": True, "sessions": [asdict(item) for item in sessions]}
            else:
                print(messages["session_list"].format(limit))
                print(render_table(sessions, lang=args.lang))
                return 0
        elif command == "read":
            thread_id = args.thread_id
            if args.index is not None:
                sessions = normalize_sessions(client.list_sessions(), limit=args.limit)
                if args.index < 1 or args.index > len(sessions):
                    raise CodexBridgeError("序号 {} 不在当前会话列表范围内".format(args.index))
                thread_id = sessions[args.index - 1].thread_id
            if not thread_id:
                raise CodexBridgeError("请提供 thread_id，或使用 --index 指定列表序号")
            output = {"ok": True, "thread": client.get_session(thread_id)}
        elif command == "send":
            output = {"ok": True, "result": client.send_message(args.thread_id, args.message)}
        else:
            parser.print_help()
            return 2

        print(json.dumps(output, ensure_ascii=False, indent=2) if args.json else output["message"])
        return 0
    except Exception as exc:
        error = {"ok": False, "error": str(exc)}
        print(json.dumps(error, ensure_ascii=False, indent=2) if args.json else "错误: {}".format(exc), file=sys.stderr)
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
