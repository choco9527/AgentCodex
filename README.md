# AgentCodex (Remote Control Bridge for Lobster Assistant)

**AgentCodex** 是 **Agent龙虾助手** 的远程控制中枢。它通过 Python 直连 Codex App 的底层通信协议，让你能够突破物理设备的限制，随时随地通过龙虾助手远程操控公司电脑上的 Codex。

## 🎯 核心价值：打破空间限制

想象一下：你的高性能开发机在公司，但你现在在家里或路上。通过 **AgentCodex** + **龙虾助手**，你可以：
1.  **远程唤醒**：在任何设备上与龙虾助手对话，即可连接公司的 Codex 实例。
2.  **无缝接力**：在家继续处理公司电脑上的复杂代码任务，无需打开远程桌面。
3.  **状态同步**：实时获取公司电脑的 Git 进度、文件状态和开发上下文。

---

## 🚀 功能特性

*   **JSON-RPC 深度桥接**：绕过官方 CLI 的限制，直接与 `codex app-server` 进行底层通信。
*   **会话全量提取**：不仅获取列表，还能深入 `.jsonl` 日志还原真实的 User/Assistant 对话流。
*   **轻量级纯 Python**：零重型依赖，作为后台服务稳定运行，随时等待龙虾助手的远程指令。

## 📦 安装与使用

### 1. 环境要求
确保目标机器（如公司电脑）已安装并启动了 Codex：
```bash
brew install codex
codex app-server # 确保后端服务正在运行
```

### 2. 运行桥接服务
```bash
cd AgentCodex
python3 codex_client.py
```

## 🛠️ Agent Skills (for AI Agents)

如果你是 AI Agent 开发者，可以将本项目中的 `agents/skills` 目录集成到你的 Agent 系统中，赋予其远程控制能力。

*   **Skill: `remote_codex_controller`**
    *   **描述**: 允许 Agent 跨越网络边界，向指定的 Codex 实例发送指令。
    *   **用途**: 实现“手机端发起需求 -> 公司电脑执行代码 -> 结果回传手机端”的闭环。

## 📂 项目结构

*   `codex_client.py`: 核心客户端逻辑，包含 JSON-RPC 握手与会话解析。
*   `agents/skills/`: 针对 AI Agent 的远程控制指引文件。

## 📝 协议说明

本项目通过以下 JSON-RPC 方法与 `codex app-server` 交互：
*   `initialize`: 初始化握手。
*   `thread/list`: 获取会话列表。
*   `thread/read`: 读取会话详情。

---
*Empowering your Agent to control Codex from anywhere.*
