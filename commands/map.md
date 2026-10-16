---
description: 能力图进度：某条线或全部线做到哪了（只读）
argument-hint: [线|all] [全部]
allowed-tools: Bash
---

只读查询。参数：$ARGUMENTS（不给就是 all）

1. 运行 `"${CLAUDE_PLUGIN_ROOT:-$PLUGIN_ROOT}/bin/decision-inbox" whoami`，从输出的 JSON 取 `group`。认不出就把 stderr 原样告诉用户，到此为止。
2. 运行 `"${CLAUDE_PLUGIN_ROOT:-$PLUGIN_ROOT}/bin/decision-inbox" map <group> <线或 all> [全部]`。
3. 把输出原样显示给用户，不改写、不总结。
