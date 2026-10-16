---
description: 流畅度体检：卡在哪、谁等谁、积压在哪（只读）
allowed-tools: Bash, Write, mcp__agent-relay__bridge_agents, mcp__agent-relay__bridge_wake_status
---

只读查询，不给任何会话发消息。

1. 运行 `"${CLAUDE_PLUGIN_ROOT:-$PLUGIN_ROOT}/bin/decision-inbox" whoami`，从输出的 JSON 取 `group`。认不出就把 stderr 原样告诉用户，到此为止。
2. 调用 `bridge_agents`（不带参数），返回的 JSON 原样写入 `~/.decision-inbox/<group>/io/agents.json`。
3. 调用 `bridge_wake_status`（不带参数），返回的 JSON 原样写入 `~/.decision-inbox/<group>/io/wakes.json`。
4. 运行 `"${CLAUDE_PLUGIN_ROOT:-$PLUGIN_ROOT}/bin/decision-inbox" query flow <group> --agents ~/.decision-inbox/<group>/io/agents.json --wakes ~/.decision-inbox/<group>/io/wakes.json`。
5. 把输出原样显示给用户，不改写、不总结。
