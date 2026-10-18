<!-- spec-guard: review pending -->

# Implementation Plan: teardown-patrol-session

> 依据：`spec/teardown-patrol-session.md`（用户 2026-10-19 批准）。任务清单：`tasks/teardown-patrol-session/todo.md`。分支 `claude/teardown-patrol-session`（从 main 开出，main 已含 0.0.22）。

## Overview

一个任务：先在打包测试里写断言（应当失败），再改 `commands/teardown.md` 和 README 卸载一节，跑全量测试。不改 CLI，不升版本号。

## Architecture Decisions

- **测试**（`tests/test_packaging.py`）：
  - 卸载命令的 frontmatter `allowed-tools` 含 `mcp__ccd_session_mgmt__archive_session`，原有的 `delete_scheduled_task`、`list_scheduled_tasks` 仍在；
  - 正文含 `archive_session` 和「后续步骤」；
  - `description` 含「归档巡视会话」；
  - README 卸载一节含「归档巡视会话」。
- **命令文件**：说明、第 3 步、允许的工具按 Spec「要做的」第 1 条改；第 1、2 步（预览、确认）不动。
- **README**：卸载第 2 条按 Spec「要做的」第 2 条改。

## Task List

- **Task 1 卸载命令与 README**（Spec 验收 1–4）：
  - 先写上面的断言，确认失败；
  - 改 `commands/teardown.md` 和 README；
  - 验证：`tests/test_packaging.py` 通过；`tests/test_onboard.py` 里 `onboard teardown` 原有测试照旧通过；全量测试通过。

## Checkpoint（gate）：模块最终验收

列出改动的文件、每条验收标准的证据、测试数，然后开 PR（base main）。

## 影响面

只有卸载命令的说明文字和 README；已接入的组不受影响，不用重新接入。

## 风险

| 风险 | 对策 |
|---|---|
| 工具名写错，命令里调不到归档工具 | 和 hub-setup 用的桌面版会话工具同一前缀；实测时在测试组里跑一次卸载核对 |
