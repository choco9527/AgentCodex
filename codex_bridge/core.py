"""JSON-RPC connection layer for the official Codex app-server."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import threading
import time
from typing import Any, Dict, List, Optional

from .models import CacheEntry, PendingRequest
from .utils import stable_json_key


DEFAULT_CODEX_BINARY = "/Applications/Codex.app/Contents/Resources/codex"
DEFAULT_TIMEOUT_SECONDS = 15
THREAD_LIST_FRESH_TTL_SECONDS = 30
THREAD_LIST_STALE_TTL_SECONDS = 5 * 60
CACHEABLE_METHODS = {
    "thread/list": (THREAD_LIST_FRESH_TTL_SECONDS, THREAD_LIST_STALE_TTL_SECONDS),
    "thread/loaded/list": (THREAD_LIST_FRESH_TTL_SECONDS, THREAD_LIST_STALE_TTL_SECONDS),
}
THREAD_LIST_INVALIDATING_NOTIFICATIONS = {
    "thread/started",
    "thread/archived",
    "thread/unarchived",
    "thread/closed",
    "thread/name/updated",
    "thread/status/changed",
}


class CodexBridgeError(RuntimeError):
    """Raised when AgentCodex cannot communicate with Codex app-server."""


def normalize_params(method: str, params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if params is not None:
        return params
    if method in {"initialize", "thread/list", "thread/loaded/list"}:
        return {}
    return {}


def cache_key(method: str, params: Dict[str, Any]) -> str:
    return stable_json_key(method, params)


def normalize_thread_id(value: Any) -> str:
    if isinstance(value, str) and value:
        return value
    if isinstance(value, dict):
        for key in ("threadId", "conversationId", "thread_id", "id"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate:
                return candidate
        thread = value.get("thread")
        if isinstance(thread, dict):
            candidate = thread.get("id")
            if isinstance(candidate, str) and candidate:
                return candidate
    raise CodexBridgeError("Missing threadId")


def thread_id_from_result(result: Any) -> str:
    try:
        return normalize_thread_id(result)
    except CodexBridgeError:
        return ""


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
        self.response_cache: Dict[str, CacheEntry] = {}
        self.lock = threading.Lock()
        self._stdout_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._stderr_tail: List[str] = []

    def connect(self) -> None:
        if self.process and self.process.poll() is None:
            return

        command = self._build_app_server_command()
        self._log("Starting Codex app-server: {}".format(" ".join(command)))
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        self._stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
        self._stdout_thread = threading.Thread(target=self._read_stdout, daemon=True)
        self._stderr_thread.start()
        self._stdout_thread.start()

        time.sleep(0.1)
        if self.process.poll() is not None:
            raise CodexBridgeError(self._process_exit_error())

        self.call_app_server(
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
            use_cache=False,
        )
        self._send_notification("initialized")
        self._log("Connected")

    def _build_app_server_command(self) -> List[str]:
        configured = os.environ.get("CODEX_APP_SERVER_CMD")
        if configured:
            return shlex.split(configured)

        listen = os.environ.get("CODEX_APP_SERVER_LISTEN", "stdio://")
        if listen != "stdio://":
            raise CodexBridgeError(
                "Only stdio:// is supported by this Python bridge. "
                "Set CODEX_APP_SERVER_CMD to a stdio app-server command."
            )
        if not os.path.exists(self.codex_binary):
            raise CodexBridgeError(
                "Codex binary not found: {}. Set CODEX_BINARY or CODEX_APP_SERVER_CMD.".format(
                    self.codex_binary
                )
            )
        return [self.codex_binary, "app-server", "--listen", "stdio://"]

    def _process_exit_error(self) -> str:
        detail = "\n".join(self._stderr_tail[-5:])
        return "app-server exited unexpectedly{}".format(": {}".format(detail) if detail else "")

    def _log(self, message: str) -> None:
        if self.verbose:
            print("[CodexBridge] {}".format(message), file=sys.stderr)

    def _read_stderr(self) -> None:
        if not self.process or not self.process.stderr:
            return
        for line in iter(self.process.stderr.readline, b""):
            text = line.decode("utf-8", errors="replace").strip()
            if text:
                self._stderr_tail.append(text)
                self._stderr_tail = self._stderr_tail[-20:]
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
                self._log("Skipped unparseable response: {}".format(exc))
                continue
            self._handle_message(message)

    def _handle_message(self, message: Dict[str, Any]) -> None:
        req_id = message.get("id")
        method = message.get("method")
        if isinstance(method, str):
            self._invalidate_cache_for_notification(method)
        if req_id is None:
            return
        with self.lock:
            entry = self.pending_requests.pop(req_id, None)
        if not entry:
            if isinstance(method, str):
                self._reply_to_unsupported_server_request(req_id, method)
            return
        entry.error = message.get("error")
        entry.result = message.get("result")
        entry.event.set()

    def _next_request_id(self) -> int:
        with self.lock:
            req_id = self.request_id
            self.request_id += 1
        return req_id

    def _send_payload(self, payload: Dict[str, Any]) -> None:
        if not self.process or not self.process.stdin or self.process.poll() is not None:
            raise CodexBridgeError("Codex app-server is not connected")

        try:
            self.process.stdin.write((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
            self.process.stdin.flush()
        except BrokenPipeError as exc:
            raise CodexBridgeError("Send failed, app-server pipe is closed") from exc

    def _send_notification(self, method: str, params: Optional[Dict[str, Any]] = None) -> None:
        payload = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        self._send_payload(payload)

    def _reply_to_unsupported_server_request(self, req_id: Any, method: str) -> None:
        try:
            self._send_payload(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": "AgentCodex does not implement server request {}".format(method),
                    },
                }
            )
        except CodexBridgeError:
            self._log("Could not reply to unsupported server request {}".format(method))

    def _send_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        if method.startswith("thread/") and method not in ("thread/list", "thread/loaded/list", "thread/read"):
            self._invalidate_thread_list_cache()

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
            self._send_payload(payload)
        except Exception:
            with self.lock:
                self.pending_requests.pop(req_id, None)
            raise

        if not entry.event.wait(self.timeout):
            with self.lock:
                self.pending_requests.pop(req_id, None)
            raise CodexBridgeError("Request {} timed out after {}s".format(method, self.timeout))

        if entry.error:
            raise CodexBridgeError(str(entry.error))
        return entry.result

    def call_app_server(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
    ) -> Any:
        normalized_params = normalize_params(method, params)
        key = cache_key(method, normalized_params)
        if use_cache and key:
            cached = self._cached_response(method, key)
            if cached is not None:
                return cached

        result = self._send_request(method, normalized_params)
        if use_cache and key and method in CACHEABLE_METHODS:
            fresh_ttl, stale_ttl = CACHEABLE_METHODS[method]
            self.response_cache[key] = CacheEntry(
                value=result,
                stored_at=time.time(),
                fresh_ttl=fresh_ttl,
                stale_ttl=stale_ttl,
            )
        return result

    def _cached_response(self, method: str, key: str) -> Any:
        if method not in CACHEABLE_METHODS:
            return None
        entry = self.response_cache.get(key)
        if not entry:
            return None
        age = time.time() - entry.stored_at
        if age <= entry.stale_ttl:
            return entry.value
        self.response_cache.pop(key, None)
        return None

    def _invalidate_cache_for_notification(self, method: str) -> None:
        if method in THREAD_LIST_INVALIDATING_NOTIFICATIONS:
            self._invalidate_thread_list_cache()

    def _invalidate_thread_list_cache(self) -> None:
        for key in list(self.response_cache.keys()):
            if key.startswith("thread/list:") or key.startswith("thread/loaded/list:"):
                self.response_cache.pop(key, None)

    def list_sessions(self) -> Any:
        return self.call_app_server("thread/list")

    def get_session(self, thread_id: Any) -> Any:
        return self.call_app_server("thread/read", {"threadId": normalize_thread_id(thread_id)}, use_cache=False)

    def resume_session(self, thread_id: Any) -> Any:
        return self.call_app_server("thread/resume", {"threadId": normalize_thread_id(thread_id)}, use_cache=False)

    def start_session(
        self,
        cwd: Optional[str] = None,
        workspace_roots: Optional[List[str]] = None,
        **extra_params: Any,
    ) -> str:
        resolved_cwd = cwd or os.getcwd()
        params = {
            "cwd": resolved_cwd,
            "workspaceRoots": workspace_roots or [resolved_cwd],
            **extra_params,
        }
        result = self.call_app_server("thread/start", params, use_cache=False)
        thread_id = thread_id_from_result(result)
        if not thread_id:
            raise CodexBridgeError("app-server thread/start did not return a threadId")
        return thread_id

    def set_session_name(self, thread_id: Any, name: str) -> Any:
        return self.call_app_server(
            "thread/name/set",
            {"threadId": normalize_thread_id(thread_id), "name": name},
            use_cache=False,
        )

    def send_message(self, thread_id: Any, text: str) -> Any:
        canonical_thread_id = normalize_thread_id(thread_id)
        return self.call_app_server(
            "turn/start",
            {
                "threadId": canonical_thread_id,
                "input": [{"role": "user", "content": [{"type": "text", "text": text}]}],
            },
            use_cache=False,
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
