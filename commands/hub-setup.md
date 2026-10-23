---
description: 把本会话接入为某个协作组的决策收件箱，并装上由本机 launchd 跑的巡视
argument-hint: <协作组名> <本会话在 agent-relay 的邮箱名>
allowed-tools: Bash, mcp__ccd_session_mgmt__get_session, mcp__agent-relay__bridge_register, mcp__ccd_session_mgmt__send_message, mcp__ccd_session_mgmt__archive_session, mcp__scheduled-tasks__delete_scheduled_task
---

参数：$ARGUMENTS（第一个是协作组名，第二个是邮箱名；缺了就问用户，不要自己起名）。会改本目录的 CLAUDE.md、建协作组、记下巡视的脚本身份、装巡视定时任务（本机 launchd 任务，每 5 分钟跑一轮巡视）；有旧的巡视会话或巡视定时任务时先停掉它们。每一步都先预览、经用户确认。巡视不再开会话。

1. 调用 `get_session`（session_id 填 `self`），取得本会话编号（`local_` 开头）。
2. 预览：运行 `"${CLAUDE_PLUGIN_ROOT}/bin/decision-inbox" onboard hub <协作组> --relay-name <邮箱名> --desktop-session <本会话编号> --project "$PWD"`，把输出（要写的文件、名册条目、协作规则段全文）给用户看。本会话要开在决策收件箱自己的目录里，不要开在装着各成员目录的协作组上级目录：Claude 会沿父目录加载 CLAUDE.md，写在上级的规则段会套到下面每个成员身上。预览报「不能把协作规则段写进」时，把原因和建议的目录告诉用户，停在这里，请用户到那个目录开会话重跑。预览开头提示「旧规则文件……还留着」时，问用户要不要一并删掉；要的话加 `--drop-old`（只删旧文件里本插件的规则段，文件里别的内容不动）。如果这是替换一个已经在用的决策收件箱（旧的那个已经编过号），先问用户新编号从几开始（例如 1001），用户给了就加 `--start-number <起始编号>`；起始编号只有在新组还没编过号时才能设。
3. 等用户确认后，同一条命令加 `--confirm` 再运行。用户没确认就停在这里。
4. 按输出的「后续步骤」做：
   - 调用 `bridge_register`（`agent` 为邮箱名，`wake` 为 `"auto"`）；
   - 后续步骤里有「删除旧巡视任务」时，先给用户看任务编号，确认后调用 `delete_scheduled_task`（它建过的会话会一起归档）；
   - 后续步骤里有「停止并归档旧巡视会话」时，照做：先用 `send_message` 发「停止巡视」、等它回「已停」，再 `archive_session`；它旧的巡视目录 `~/.decision-inbox/<协作组>/patrol` 留着不删；
   - 登记脚本身份：把后续步骤里的 `~/.agent-relay/bin/agent-relay register-script-identity <名> --confirm` 给用户，**请用户自己在终端运行**（只能用户做；脚本身份不能和任何会话的邮箱名相同，默认名是「邮箱名-patrol」）；不要替用户运行。等用户说做完；
   - 运行 `"${CLAUDE_PLUGIN_ROOT}/bin/decision-inbox" onboard patrol-identity <协作组> --name <名>`，把预览给用户看（它会写明 agent-relay 里有没有登记这个脚本身份）；用户确认后加 `--confirm`；
   - 后续步骤里的 `onboard allow`：预览给用户看，确认后加 `--confirm`；
   - 巡视定时任务：运行 `"${CLAUDE_PLUGIN_ROOT}/bin/decision-inbox" onboard watch <协作组>`，把预览（launchd 任务和 plist 全文）给用户看；用户确认后加 `--confirm` 再运行。它每 5 分钟跑一轮 `patrol tick`：读 agent-relay、叫醒、提醒、弹通知，巡视停了也弹系统通知；
   - 装好后运行 `"${CLAUDE_PLUGIN_ROOT}/bin/decision-inbox" doctor --group <协作组>`，核对「巡视定时任务」正常；过 5 分钟后按本目录 CLAUDE.md 协作规则段的第 7 步读状态并运行 `"${CLAUDE_PLUGIN_ROOT}/bin/decision-inbox" view …`，核对主视图第一行没有「巡视还没跑完过」；
   - 告诉用户在 Claude Code 和 Codex 里各信任一次插件自带的停止钩子，以及其他会话怎么接入。
