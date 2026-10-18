<!-- spec-guard: review pending -->

# Implementation Plan: patrol-stop-fixes

> 依据：`spec/patrol-stop-fixes.md`（用户 2026-10-19 批准）。任务清单：`tasks/patrol-stop-fixes/todo.md`。分支 `claude/patrol-stop-fixes`（从 main 开出，main 已含 0.0.23）。

## Overview

两个任务，各自先写失败的测试再改：先做「停止巡视」约定和卸载先停再归档，再改「身份」用词。最后做一次最终验收。不升版本号。

## Architecture Decisions

- **停止约定**：在 `onboard.py` 加一个常量 `PATROL_STOP`，写「收到『停止巡视』时，用 CronDelete 删掉这个循环任务，回一句『已停』就结束」。开巡视会话的步骤、`hub.patrol_session_fix` 都引用它，保证写法只有一份。
- **卸载步骤**（`onboard.teardown`）：登记过巡视会话时，输出两条步骤：
  1. 「用 send_message 给巡视会话 <编号> 发『停止巡视』，等它回『已停』」；
  2. 「用 archive_session 归档巡视会话 <编号>；它不认这句话（旧版巡视会话）或归档仍被拒时，请用户在那个会话里停掉循环，或从侧边栏归档」。

  旧定时任务那一条的逻辑不动。
- **命令文件**：`commands/teardown.md` 的允许工具加上 `mcp__ccd_session_mgmt__send_message`，第 3 步改成先停再归档。
- **「身份」**：
  - `tests/test_glossary.py` 的 `OLD` 加上「身份」→「邮箱名」；
  - 改 `patrol.PROMPT`、`stophook`、`query` 三处，以及 README 里的几处；
  - 「身份名」已经在词表里，不重复处理。

## Task List

- **Task 1 停止巡视与卸载**（Spec 验收 1–3）：先写测试（确认失败）。
  - 验证：`tests/test_onboard.py` 中：
    - 开巡视会话的步骤含「停止巡视」「CronDelete」「已停」；
    - 卸载时 send_message 那一步排在 archive_session 之前，并写明旧会话怎么办；
    - 只有旧定时任务时，原有断言不变。
  - 验证：`tests/test_hub.py` 中，`patrol_session_fix` 含停止约定。
  - 验证：`tests/test_packaging.py` 中，卸载命令允许 send_message、正文先停再归档。
- **Task 2 「身份」改名与 README**（Spec 验收 4、5）：词表加上「身份」，先跑一遍扫描看命中了哪些地方，再逐处改。README 改用词，在升级一节加上旧巡视会话的说明。
  - 验证：旧称扫描全部通过；改动的断言同步更新；全量测试通过。

## Checkpoint（gate）：模块最终验收

列出改动的文件、每条验收标准的证据和测试数，然后开 PR（base main）。

## 影响面

- 开巡视会话的提示词：新开的巡视会话才会生效；
- 卸载步骤；
- 三处提示文字；
- README。

不改协作规则段，已接入的线不用重新接入。

## 风险

| 风险 | 对策 |
|---|---|
| 旧巡视会话不认「停止巡视」，卸载卡住 | 卸载步骤第 2 条写明手动停、从侧边栏归档；README 升级一节说明 |
| 「身份」加进词表后误伤（例如契约里的字段） | 扫描本来就先去掉标签和字段名；如果有必要保留的例外，逐条写原因 |
