# Codex Session Reader Skill

## Description
This skill allows an AI Agent to read and understand the user's local Codex CLI session history. It provides access to conversation context, Git branch information, and task summaries.

## Usage
When the user asks about their previous coding tasks, project status, or what they were discussing with Codex:

1. **List Sessions**: Call `codex_client.py` to retrieve the list of all sessions.
2. **Identify Target**: Ask the user which session they want to explore (by title or index).
3. **Read Details**: Use the `get_session(thread_id)` method to fetch the full context.
4. **Parse Logs**: If `turns` are empty in the API response, read the corresponding `.jsonl` file from the Codex data directory to get the raw conversation log.

## Key Information to Extract
*   **Thread Name**: The actual title of the conversation.
*   **Git Branch**: The branch associated with the task.
*   **Preview/Summary**: A brief overview of the discussion.
*   **Recent Messages**: The last few exchanges to understand the current state of the work.

## Example Prompt for Agent
"The user wants to know about their 'Hala gift' task. I will use the Codex Session Reader skill to find the session named '分析Hala礼物小数支持', read its details, and summarize the current implementation status."
