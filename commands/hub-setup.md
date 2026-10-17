---
description: 把本会话接入为某个协作组的收件枢纽，并建巡视定时任务
argument-hint: <协作组名> <本会话在 agent-relay 的身份名>
allowed-tools: Bash, mcp__ccd_session_mgmt__get_session, mcp__agent-relay__bridge_register, mcp__scheduled-tasks__create_scheduled_task
---

参数：$ARGUMENTS（第一个是协作组名，第二个是身份名；缺了就问用户，不要自己起名）。会改本目录的 CLAUDE.md、建协作组、建定时任务，每一步都先预览、经用户确认。

1. 调用 `get_session`（session_id 填 `self`），取得本会话编号（`local_` 开头）。
2. 预览：运行 `"${CLAUDE_PLUGIN_ROOT}/bin/decision-inbox" onboard hub <协作组> --relay-name <身份名> --desktop-session <本会话编号> --project "$PWD"`，把输出（要写的文件、名册条目、约定块全文）给用户看。
3. 等用户确认后，同一条命令加 `--confirm` 再运行。用户没确认就停在这里。
4. 按输出的「后续步骤」做：
   - 调用 `bridge_register`（`agent` 为身份名，`wake` 为 `"auto"`）；
   - 调用 `create_scheduled_task`：`taskId` 用建议的编号，`cronExpression` 用 `*/5 * * * *`，`prompt` 用输出的巡视提示词原文，`description` 写「decision-inbox 巡视」；
   - 运行 `"${CLAUDE_PLUGIN_ROOT}/bin/decision-inbox" onboard task <协作组> --task-id <实际建成的编号>`；
   - 请用户在定时任务列表里手动「立即运行」一次这个任务（第一次手动运行之前定时不会触发），把弹出的权限确认都批完；等用户说做完后，按本目录 CLAUDE.md 约定块的第 7 步读状态并运行 `"${CLAUDE_PLUGIN_ROOT}/bin/decision-inbox" view …`，核对主视图第一行没有「巡视还没跑完过」。15 分钟内还看不出来，就请用户在定时任务列表里看这个任务最近一次运行是否停在权限确认上；
   - 告诉用户在 Claude Code 和 Codex 里各信任一次插件自带的停止钩子，以及其他会话怎么接入。
