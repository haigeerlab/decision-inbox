---
description: 我在等什么、谁在等我：本会话开的等待记录和没结的待决事项，以及别人在等本会话的（只读）
allowed-tools: Bash, Write, mcp__agent-relay__bridge_agents
---

只读查询，不给任何会话发消息，也不催办。

1. 运行 `"${CLAUDE_PLUGIN_ROOT}/bin/decision-inbox" whoami`，从输出的 JSON 取 `group` 和 `relayName`。认不出（退出码 4 或 5）就把它的 stderr 原样告诉用户，到此为止。
2. 调用 agent-relay 的 `bridge_agents`（不带参数），把返回的 JSON 原样写入 `~/.decision-inbox/<group>/io/agents.json`。调用失败就跳过这一步，第 3 步不带 `--agents`（这样不判断对方是否离线）。
3. 运行 `"${CLAUDE_PLUGIN_ROOT}/bin/decision-inbox" query waits <group> --me <relayName> --agents ~/.decision-inbox/<group>/io/agents.json`。
4. 把输出原样显示给用户，不改写、不总结、不补充判断。
