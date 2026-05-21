---
name: session-extractor
description: Use this skill to list and search Codex conversation sessions.
---

# Session Extractor

This tool allows you to interact with your local Codex App's session data programmatically.

## Usage

```bash
cd /path/to/AgentCodex
PYTHONPATH=/path/to/AgentCodex python3 agents/skills/session_extractor/extract_session.py
```

## Features
- **List Sessions**: Retrieves the latest sessions with their titles and thread IDs.
- **Cross-Platform**: Automatically detects Codex home directory on macOS, Linux, and Windows.
- **Integration**: Built on top of `codex_client.py` for reliable JSON-RPC communication.

## Example Output
```
Found 5 sessions:
- 查看项目核心职责 (ID: 019e49cd...)
- 分析Hala礼物小数支持 (ID: 019e4961...)
- analytics (ID: 019e4914...)
```
