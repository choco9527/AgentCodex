# -*- coding: utf-8 -*-
"""Compatibility entrypoint for AgentCodex.

New code should import from `codex_bridge`.
"""

from codex_bridge import (  # noqa: F401
    CacheEntry,
    CodexBridgeError,
    CodexClient,
    PendingRequest,
    SessionSummary,
    cache_key,
    normalize_params,
    normalize_sessions,
    normalize_thread_id,
    render_table,
    thread_id_from_result,
)
from codex_bridge.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
