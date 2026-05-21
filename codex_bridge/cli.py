"""Command-line interface for AgentCodex."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from typing import List, Optional

from .core import CodexBridgeError, CodexClient
from .sessions import normalize_sessions, render_table


MESSAGES = {
    "en": {
        "available": "Codex app-server is available",
        "restarted": "Codex app-server restarted",
        "no_process": "No app-server process is owned by this bridge command",
        "session_list": "Codex sessions (top {}):",
        "index_out_of_range": "Index {} is outside the current session list",
        "missing_thread": "Provide thread_id or use --index",
        "error": "Error: {}",
    },
    "zh": {
        "available": "Codex app-server 可用",
        "restarted": "Codex app-server 已重启",
        "no_process": "当前桥接进程没有运行中的 app-server",
        "session_list": "Codex 会话列表（前 {} 个）:",
        "index_out_of_range": "序号 {} 不在当前会话列表范围内",
        "missing_thread": "请提供 thread_id，或使用 --index 指定列表序号",
        "error": "错误: {}",
    },
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Agent-friendly Codex app-server bridge")
    parser.add_argument("--json", action="store_true", help="Output stable JSON for agents")
    parser.add_argument("--verbose", action="store_true", help="Print bridge debug logs")
    parser.add_argument("--timeout", type=int, default=15, help="JSON-RPC timeout seconds")
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
                    raise CodexBridgeError(messages["index_out_of_range"].format(args.index))
                thread_id = sessions[args.index - 1].thread_id
            if not thread_id:
                raise CodexBridgeError(messages["missing_thread"])
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
        print(json.dumps(error, ensure_ascii=False, indent=2) if args.json else messages["error"].format(exc), file=sys.stderr)
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
