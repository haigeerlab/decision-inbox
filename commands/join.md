---
description: 把本会话接入协作组（开发线、负责人或总协调）
argument-hint: <协作组> <角色 dev|owner|coordinator> <身份名> <短名> [线名…] [审查者身份名 节点]
allowed-tools: Bash, mcp__ccd_session_mgmt__get_session, mcp__agent-relay__bridge_register
---

参数：$ARGUMENTS。缺什么就问用户，不要猜；审查者和审查节点由用户说明。会改本目录的 CLAUDE.md、登记名册，先预览、经用户确认。

1. 调用 `get_session`（session_id 填 `self`），取得本会话编号（`local_` 开头）。
2. 预览：运行 `"${CLAUDE_PLUGIN_ROOT}/bin/decision-inbox" onboard join <协作组> --role <角色> --relay-name <身份名> --short-name <短名> --host claude-desktop --desktop-session <本会话编号> --project "$PWD"`，每条线加一个 `--line <线名>`；用户指定了审查者时加 `--reviewer <负责人身份名> --nodes <spec,plan,interface,final 中的若干个>`；用户明确要打开「检查点答复即授权」时加 `--checkpoint-authority`（默认不开，先问用户）。本会话是 module-crew 的协调会话、代表一条线接入时（用户明确说了才算），按开发线接入并加 `--crew-coordinator`：约定块会多一节「并行开发协调会话」，停止钩子不再因为模块的 todo 没勾完而拦它。协调会话开在集成 checkout 里时，再加 `--local-rules`，约定块就写进 `CLAUDE.local.md`，不会被提交，也不会被模块 worktree 继承；接入预览如果提示要改 `info/exclude`，或者提示「不再读 AGENTS.md」，要先告诉用户。把输出给用户看，开头的 `⚠` 行先单独告诉用户。
3. 等用户确认后，同一条命令加 `--confirm` 再运行。用户没确认就停在这里。
4. 按输出的「后续步骤」做：调用 `bridge_register`（`wake` 为 `"auto"`），并提醒用户信任插件自带的停止钩子。
