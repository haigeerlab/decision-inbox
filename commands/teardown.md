---
description: 决策收件箱卸载：删协作规则段、归档巡视会话（有旧的巡视定时任务也删掉），状态目录保留
argument-hint: <协作组>
allowed-tools: Bash, mcp__ccd_session_mgmt__archive_session, mcp__scheduled-tasks__list_scheduled_tasks, mcp__scheduled-tasks__delete_scheduled_task
---

参数：$ARGUMENTS（缺了就先运行 `"${CLAUDE_PLUGIN_ROOT}/bin/decision-inbox" whoami` 取得）。`~/.decision-inbox` 下的状态目录保留，不删。

1. 预览：运行 `"${CLAUDE_PLUGIN_ROOT}/bin/decision-inbox" onboard teardown <协作组>`，把输出给用户看。
2. 等用户确认后，同一条命令加 `--confirm` 再运行。用户没确认就停在这里。
3. 按输出的「后续步骤」逐条做：归档巡视会话用 `archive_session`（归档的是巡视会话，不是本会话）；以前建过巡视定时任务的，用 `delete_scheduled_task` 删除；输出说没记下编号时，先用 `list_scheduled_tasks` 核对，再删。
