---
description: 决策收件箱卸载：删协作规则段、卸掉巡视提醒、归档巡视会话（有旧的巡视定时任务也删掉），状态目录保留
argument-hint: <协作组>
allowed-tools: Bash, mcp__ccd_session_mgmt__send_message, mcp__ccd_session_mgmt__archive_session, mcp__scheduled-tasks__list_scheduled_tasks, mcp__scheduled-tasks__delete_scheduled_task
---

参数：$ARGUMENTS（缺了就先运行 `"${CLAUDE_PLUGIN_ROOT}/bin/decision-inbox" whoami` 取得）。`~/.decision-inbox` 下的状态目录保留，不删。

1. 预览：运行 `"${CLAUDE_PLUGIN_ROOT}/bin/decision-inbox" onboard teardown <协作组>`，把输出给用户看。
2. 等用户确认后，同一条命令加 `--confirm` 再运行（装过巡视提醒的，这一步会一起卸掉 launchd 任务）。用户没确认就停在这里。
3. 按输出的「后续步骤」逐条做：先用 `send_message` 给巡视会话发「停止巡视」，等它回「已停」，再用 `archive_session` 归档巡视会话（归档的是巡视会话，不是本会话；它不认这句话或归档被拒时，请用户在那个会话里停掉循环，或从侧边栏归档）；以前建过巡视定时任务的，用 `delete_scheduled_task` 删除；输出说没记下编号时，先用 `list_scheduled_tasks` 核对，再删。
