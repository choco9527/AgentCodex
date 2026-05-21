# AgentCodex

AgentCodex is an agent-oriented bridge for local Codex App sessions.

It is designed for Lobster Agent and similar agent systems. It provides stable session discovery, context reading, and session operation capabilities so an Agent can understand the current Codex state and, after explicit confirmation, send follow-up instructions to the selected Codex session.

## Core Responsibilities

- Expose local Codex session capabilities to Agent systems through a lightweight bridge.
- Normalize session metadata into Agent-friendly fields: index, title, project, branch, and last updated time.
- Read session details so Agents can recover task context before acting.
- Send follow-up instructions to a confirmed Codex session.
- Provide layered Agent skills for lifecycle management, session discovery, session reading, and session operation.

## Scope

AgentCodex is a control-plane bridge for Codex. It does not replace Codex, store business code, implement remote desktop behavior, or define project-specific development workflows.

Concrete operation rules are intentionally kept in skills instead of this README. Agents should load the relevant skill and follow it as the source of truth for commands, matching rules, and safety policy.

## Agent Entry

`agents/skills/`

Agents should choose a skill by task intent:

- `codex_bridge_lifecycle`: Start, check, restart, and stop the AgentCodex bridge.
- `codex_session_reader`: Read Codex session lists and session details.
- `codex_session_operator`: Select a target session, safely send follow-up instructions, and format Codex relay messages.

## Start Bridge

Enter the AgentCodex project directory:

```bash
cd /xxx/AgentCodex
```

Start and check the Codex bridge:

```bash
python3 codex_client.py --json start
```

`ok: true` means the bridge is available. Session reading and operation flows are guided by the skills in `agents/skills/`.

## Human-Readable Output

English is the default language for human-readable CLI output:

```bash
python3 codex_client.py list --limit 10
```

Default table header:

```text
Index | Title | Project | Branch | Updated
```

Use Chinese output explicitly when needed:

```bash
python3 codex_client.py --lang zh list --limit 10
```

Agent-facing JSON fields are always stable English keys.

## Repository Layout

- `codex_client.py`: Python Codex JSON-RPC client and Agent-friendly CLI.
- `codex-client.js`: Lightweight Node.js client.
- `agents/skills/`: Layered skill instructions for Lobster Agent.
