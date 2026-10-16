---
description: 单项时间线：某个事项从收到到转达、取走、确认的全过程（只读）
argument-hint: <事项编号>
allowed-tools: Bash, Write, mcp__agent-relay__bridge_wake_status
---

只读查询，不给任何会话发消息。参数是收件枢纽的事项编号：$ARGUMENTS

1. 运行 `"${CLAUDE_PLUGIN_ROOT:-$PLUGIN_ROOT}/bin/decision-inbox" whoami`，从输出的 JSON 取 `group`。认不出就把 stderr 原样告诉用户，到此为止。
2. 运行 `"${CLAUDE_PLUGIN_ROOT:-$PLUGIN_ROOT}/bin/decision-inbox" query item-ids <group> <事项编号>`，它每行打印一个 agent-relay 消息编号。
3. 对每个消息编号调用一次 `bridge_wake_status`（`messageId` 填这个编号），返回的 JSON 原样写入 `~/.decision-inbox/<group>/io/status-<消息编号>.json`。只查给出的这些编号，不读消息正文。
4. 运行 `"${CLAUDE_PLUGIN_ROOT:-$PLUGIN_ROOT}/bin/decision-inbox" query item <group> <事项编号>`，每个状态文件加一个 `--status <文件>`。
5. 把输出原样显示给用户，不改写、不总结。
