---
name: codex_session_operator
description: Guide Lobster Agent through selecting a target Codex session and safely sending a follow-up instruction through AgentCodex.
---

# Codex Session Operator

Use this skill when Lobster Agent needs to continue, control, or send a new instruction to an existing Codex session.

## Required Preconditions

- The target session is identified with high confidence.
- The agent has read the session list through `codex_session_reader`.
- For non-trivial tasks, the agent has read the target session details.
- The user intent is clear enough to send as a Codex instruction.

## Conversation Flow

1. Read the session list with `codex_session_reader`.
2. Match candidate sessions by index, title, project, branch, pinned state, and update time.
3. If there is one clear match, read that session detail.
4. If multiple sessions match, ask the user to choose by list index.
5. Before sending, summarize the selected session:

```text
我找到的会话是：<标题>
项目：<项目>
分支：<分支>
最后时间：<最后时间>
```

6. Send the follow-up instruction only after the target is clear.

## Relay Mode

When Lobster Agent is relaying information from an active Codex conversation, make the reply visually distinct from Lobster Agent's own words.

Use Relay Mode when:

- The user asks for the latest response from Codex.
- The agent forwards a Codex result, question, error, or status update.
- The agent continues an existing Codex session and the message body mainly comes from Codex.
- The user needs to distinguish “Codex said this” from “Lobster Agent decided this”.

Relay Mode format:

```text
————Codex————
<Codex message body>
————Codex————
```

Do not put Lobster Agent commentary inside the delimiter block. If explanation is needed, place it before or after the block in normal prose.

If the content is a summary written by Lobster Agent rather than a direct Codex relay, do not use Relay Mode unless the user explicitly asks to present it as a Codex-facing message.

## Send Message

```bash
python3 codex_client.py --json send <thread_id> "用户的新指令"
```

Keep the instruction concise and self-contained. Include the user's actual requested change, any relevant constraints, and the expected result.

## When To Ask The User

Ask a short clarification when:

- Two or more sessions match equally well.
- The user says “继续那个任务” but no pinned or recent matching session is obvious.
- The requested operation could affect the wrong repository or branch.
- The session context conflicts with the user's current request.

When asking the user to choose, prefer this compact shape:

```text
Choose a Codex session index: 1 / 2 / 3
```

## Safety Rules

- Do not guess a target session for write operations.
- If the user chooses by number, resolve the number through the latest session list before sending.
- Do not send raw private context back into the session unless it is needed for the task.
- Do not issue destructive development instructions unless the user explicitly requested them.
- If sending fails, use `codex_bridge_lifecycle` to check or restart, then retry once.

## Result Reporting

After sending, report:

- Which session received the instruction.
- Whether AgentCodex accepted the request.
- Any returned error or next action required.

Do not claim Codex finished the task unless the returned session result proves completion.

When the result is a Codex-originated message, use Relay Mode.
