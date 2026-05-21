# AgentCodex (Lobster Assistant Core)

**AgentCodex** 是 **Agent龙虾助手** 的核心记忆组件。它通过 Python 直接连接 Codex App 的后端通信层，让龙虾助手能够实时感知你的开发进度并实现跨会话的上下文同步。

## 🎯 核心职责

1.  **龙虾助手的记忆中枢**：帮助龙虾助手读取你之前的 Codex 对话历史，不再“聊完即忘”。
2.  **上下文自动同步**：当你在不同项目间切换时，自动提取关键的 Git 分支和任务摘要。
3.  **智能代理接口**：为龙虾助手提供发送指令、查询状态的标准化通道。

---

## 🚀 功能特性

*   **深度会话解析**：不仅获取列表，还能深入 `.jsonl` 日志提取真实的 User/Assistant 对话流。
*   **零依赖运行**：纯 Python 实现，不依赖 OpenCodex 等重型框架，轻量且稳定。
*   **Git 集成感知**：自动关联 Codex 会话与本地 Git 工作区状态。

## 📦 安装与使用

### 1. 环境要求
确保你的系统中已经安装了官方的 Codex CLI：
```bash
brew install codex
# 或者通过 npm 安装
npm install -g @openai/codex
```

### 2. 运行项目
```bash
cd AgentCodex
python3 codex_client.py
```

## 🛠️ Agent Skills (for AI Agents)

如果你是 AI Agent 开发者，可以将本项目中的 `agents/skills` 目录集成到你的 Agent 系统中。

*   **Skill: `codex_session_reader`**
    *   **描述**: 允许 Agent 读取用户本地的 Codex 会话历史，理解之前的开发上下文。
    *   **用途**: 当用户问“我之前那个项目聊到哪了？”时，Agent 可以调用此技能获取实时进度。

*   **Skill: `codex_message_sender`**
    *   **描述**: 允许 Agent 代理用户向 Codex 发送复杂的编程指令。
    *   **用途**: 实现跨平台的 Codex 远程控制或自动化任务调度。

## 📂 项目结构

*   `codex_client.py`: 核心客户端逻辑，包含 JSON-RPC 握手与会话解析。
*   `agents/skills/`: 针对 AI Agent 的指引文件。
*   `.gitignore`: 忽略 Python 缓存及系统文件。

## 📝 协议说明

本项目通过以下 JSON-RPC 方法与 `codex app-server` 交互：
*   `initialize`: 初始化握手。
*   `thread/list`: 获取会话列表。
*   `thread/read`: 读取会话详情（需提供 `threadId`）。

---
*Created for efficient Codex interaction.*
