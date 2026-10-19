---
description: 把本会话接入为某个协作组的决策收件箱，并开一个循环巡视的会话
argument-hint: <协作组名> <本会话在 agent-relay 的邮箱名>
allowed-tools: Bash, mcp__ccd_session_mgmt__get_session, mcp__agent-relay__bridge_register, mcp__ccd_session__start_session, mcp__scheduled-tasks__delete_scheduled_task
---

参数：$ARGUMENTS（第一个是协作组名，第二个是邮箱名；缺了就问用户，不要自己起名）。会改本目录的 CLAUDE.md、建协作组、开巡视会话（有旧的巡视定时任务时删掉它）、装巡视提醒（本机 launchd 任务），每一步都先预览、经用户确认。

1. 调用 `get_session`（session_id 填 `self`），取得本会话编号（`local_` 开头）。
2. 预览：运行 `"${CLAUDE_PLUGIN_ROOT}/bin/decision-inbox" onboard hub <协作组> --relay-name <邮箱名> --desktop-session <本会话编号> --project "$PWD"`，把输出（要写的文件、名册条目、协作规则段全文）给用户看。如果这是替换一个已经在用的决策收件箱（旧的那个已经编过号），先问用户新编号从几开始（例如 1001），用户给了就加 `--start-number <起始编号>`；起始编号只有在新组还没编过号时才能设。
3. 等用户确认后，同一条命令加 `--confirm` 再运行。用户没确认就停在这里。
4. 按输出的「后续步骤」做：
   - 调用 `bridge_register`（`agent` 为邮箱名，`wake` 为 `"auto"`）；
   - 后续步骤里有「删除旧巡视任务」时，先给用户看任务编号，确认后调用 `delete_scheduled_task`（它建过的会话会一起归档）；
   - 调用 `start_session` 开巡视会话：标题、权限模式、提示词照后续步骤写（提示词是「用 /loop 5m 执行下面的巡视提示词……」加输出的巡视提示词原文），开之前给用户看一遍；
   - 运行 `"${CLAUDE_PLUGIN_ROOT}/bin/decision-inbox" onboard patrol-session <协作组> --session <巡视会话编号>`；
   - 请用户打开巡视会话看第一轮，把弹出的权限确认都批完；等用户说做完后，按本目录 CLAUDE.md 协作规则段的第 7 步读状态并运行 `"${CLAUDE_PLUGIN_ROOT}/bin/decision-inbox" view …`，核对主视图第一行没有「巡视还没跑完过」；
   - 巡视提醒：运行 `"${CLAUDE_PLUGIN_ROOT}/bin/decision-inbox" onboard watch <协作组>`，把预览（launchd 任务和 plist 全文）给用户看；用户确认后加 `--confirm` 再运行。它在本机每 5 分钟检查一次巡视，停了就弹系统通知，写明去哪个会话做什么；用户不要就跳过；
   - 告诉用户在 Claude Code 和 Codex 里各信任一次插件自带的停止钩子，以及其他会话怎么接入。
