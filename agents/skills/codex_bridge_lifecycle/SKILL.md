---
name: codex_bridge_lifecycle
description: Start, check, restart, or stop the local AgentCodex bridge for Lobster Agent before reading or operating Codex sessions.
---

# Codex Bridge Lifecycle

Use this skill when Lobster Agent needs to prepare or recover the AgentCodex bridge before working with Codex sessions.

## When To Use

- The user asks to start AgentCodex or connect to local Codex.
- A session command failed with timeout, broken pipe, or app-server startup errors.
- The agent needs to verify that local Codex app-server is reachable.
- The user asks to restart or stop the bridge.

## Commands

Run from the AgentCodex project root.

### Start

```bash
python3 codex_client.py --json start
```

Use `start` before the first session operation when bridge state is unknown.

### Check

```bash
python3 codex_client.py --json check
```

Use `check` after an error or before reporting that Codex is unavailable.

### Restart

```bash
python3 codex_client.py --json restart
```

Use `restart` once after timeouts, broken pipes, or unexpected app-server exits.

### Stop

```bash
python3 codex_client.py --json stop
```

Use `stop` only when the user asks to stop the bridge or when cleanup is explicitly needed.

## Failure Handling

- `timed out`: run `restart`, then retry the original command once.
- `app-server 未连接`: run `check`, then retry if successful.
- `找不到 Codex 可执行文件`: ask the user to set `CODEX_BINARY`.
- `Operation not permitted`: the bridge may require permission to start Codex outside the current sandbox.

## Output Rule

Report bridge state briefly. Do not expose app-server logs unless the user asks or the logs explain a failure.
