---
name: codex_session_reader
description: Read and summarize local Codex session lists and session details through AgentCodex, including title, project, branch, update time, pinned state, preview, and thread id.
---

# Codex Session Reader

Use this skill when Lobster Agent needs to discover or inspect local Codex sessions before deciding what to do next.

## When To Use

- The user asks what Codex sessions exist on the machine.
- The user asks about previous Codex tasks, project status, or branch context.
- The agent needs a `thread_id` before operating a session.
- The agent needs to inspect a selected session before continuing it.

## Read Session List

Prefer JSON for agent parsing:

```bash
python3 codex_client.py --json list --limit 10
```

Use table output only for direct human display:

```bash
python3 codex_client.py list --limit 10
```

The default table column order is stable and uses English headers:

```text
Index | Title | Project | Branch | Updated
```

Use Chinese headers only when explicitly needed:

```bash
python3 codex_client.py --lang zh list --limit 10
```

Each JSON session contains:

- `index`: 1-based display index for selecting a session from the current list.
- `title`: Agent-facing task title.
- `project`: Project directory name when it can be inferred.
- `branch`: Git branch when Codex exposes it.
- `updated_at`: Local display time.
- `thread_id`: Codex thread id for follow-up operations.
- `pinned`: Whether a pin/star/favorite marker was found.
- `preview`: Short API preview text when available.
- `path`: Local jsonl path when discovered.

## Read One Session

After selecting a candidate session:

```bash
python3 codex_client.py --json read <thread_id>
```

If the user chooses by list number, read by index:

```bash
python3 codex_client.py --json read --index <index>
```

Extract only what is needed:

- Current thread metadata.
- Recent user and Codex messages.
- Workspace or project path.
- Git branch.
- Unfinished action, failure, or next step mentioned in the latest turns.

## Matching Guidance

Prefer exact or near-exact title matches. If the title is vague, use project and branch as tie breakers. If still ambiguous, show the top candidates and ask the user to choose.

When asking the user to choose from candidates, show the `index` and let the user reply with the number. Resolve that number with `read --index <index>` or by mapping it to the matching `thread_id` from the JSON list.

Pinned sessions, when detectable, should be preferred for broad requests such as “继续之前那个任务”. If `pinned` is false for every session, do not assume there are no pinned sessions; Codex may simply not expose that state.

## Privacy Rules

- Treat local session logs as private developer context.
- Do not expose raw logs unless the user asks.
- Summarize only the minimum context needed to support the next action.

## Failure Handling

- If the command fails with bridge errors, use `codex_bridge_lifecycle`.
- If the list is empty, confirm Codex has local sessions and check `~/.codex/session_index.jsonl`.
- If project is missing, fall back to title, branch, and `thread_id`.
