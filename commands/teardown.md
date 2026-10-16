---
description: 收件枢纽卸载：删约定块和巡视定时任务，状态目录保留
argument-hint: <协作组>
allowed-tools: Bash, mcp__scheduled-tasks__list_scheduled_tasks, mcp__scheduled-tasks__delete_scheduled_task
---

参数：$ARGUMENTS（缺了就先运行 `"${CLAUDE_PLUGIN_ROOT:-$PLUGIN_ROOT}/bin/decision-inbox" whoami` 取得）。`~/.decision-inbox` 下的状态目录保留，不删。

1. 预览：运行 `"${CLAUDE_PLUGIN_ROOT:-$PLUGIN_ROOT}/bin/decision-inbox" onboard teardown <协作组>`，把输出给用户看。
2. 等用户确认后，同一条命令加 `--confirm` 再运行。用户没确认就停在这里。
3. 按输出的「后续步骤」用 `delete_scheduled_task` 删除巡视任务；输出说没记下编号时，先用 `list_scheduled_tasks` 核对，再删。
