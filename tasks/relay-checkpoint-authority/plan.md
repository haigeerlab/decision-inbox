<!-- spec-guard: review approved -->
# Implementation Plan: relay-checkpoint-authority

> 依据：`spec/relay-checkpoint-authority.md`（已批准）。任务清单：`tasks/relay-checkpoint-authority/todo.md`。

## Overview

先做接入相关的三件（R1 核对、R2 选项、R3 一节），它们都改 `onboard.py`，依次做；再做四件互相独立的小返工（R4 组合答复、F13 提示、问状态附主视图、补 `patrolTaskAt`）；然后改技能、命令、README 和版本；最后在 di-e2e 做守卫对照实测。每个任务先写失败的测试，再实现到全绿，单独提交。

## Architecture Decisions

- **R1**：新增纯函数 `onboard.codex_loads(rules_file, session_cwd) -> list[str]`，只读文件系统：
  - 从 `session_cwd` 往上找第一个含 `.git` 的目录作项目根；找不到就只认 `session_cwd`。
  - 规则文件目录不在「项目根 → 工作目录」这条链上：返回原因。
  - 同目录有 `AGENTS.override.md`：返回原因。
  - 链上各份 `AGENTS.md` 的字节数加上本次写入后的规则文件超过 32768：返回原因。
  - `join` 在 `host == "codex-desktop"` 时调用，结果放进 `Outcome.warnings`（新字段，默认空）。`_print_outcome` 把 warnings 打在最前面，每条前加「⚠ 」，并附「Codex 不加载不受信任项目的 AGENTS.md，请确认已信任这个项目」和「按 Codex 默认规则判断」两句。
- **R2**：`block(role, group, hub_relay, checkpoint_authority=False)`，打开时在 `_COMMON` 的「答复的有效性」之后插入常量 `_AUTHORITY` 的原文（`{hub}` 代入）。`join` 加参数 `checkpoint_authority`，名册条目记 `checkpointAuthority: True`，不打开时不写这个键（重新接入整块替换，所以自然去掉）。R1 有警告且打开 R2 时，warnings 多一条「当前目录下这份授权不会被守卫看到」。
- **R3**：常量 `_AUTONOMY` 放在 `_COMMON` 的「被挡住与收工」之前，三个角色共用。`join` 读写入前的规则文件（块外部分），匹配「首错即停」「遇错即停」「出错先问」「出错即停」任一词时，warnings 加一条「项目规则比约定块默认值更严格，以项目规则为准」。
- **R4**：`view.render` 在卡片之后、计数行之前加 `_combined(g)`：取 `items.pending(g)` 中有推荐的项，按卡片顺序拼 `"{no} {letter}"`，用「，」连接；至少 2 项时输出「一次答完（全按推荐）：」+ 代码块；没有推荐的项在代码块后写「#N 没有推荐，要单独回」。hub-view 规格样例只有一项待答，不受影响。
- **F13**：`tickets._resolve_end` 已在「是事项」时返回 None；在这里加参数 `kind`，`kind != "resumed"` 时加 `Issue("end-is-item", "#N 是事项，不是等待；结束事项要发【已恢复】")`。调用处 `_close_by_end_line` 透传 `msg.kind`。
- **问状态**：`hub.reply` 拿到 `items.interpret_reply` 的问题「没看出这句是答哪一项的…」，且 `items.pending(g)` 为空时，返回问题加空行加 `main_view(...)`。用一个模块常量标出这句问题，避免靠字符串匹配散落各处。
- **补 `patrolTaskAt`**：`onboard.hub` 的 `_commit` 之后，同一事务里若 `patrolTask` 存在而 `patrolTaskAt` 缺失，补当前时间。
- **版本**：两份 `plugin.json` 升到 0.0.5，`test_packaging` 跟着改。

## 影响面

- 修改：`decision_inbox/onboard.py`、`__main__.py`、`view.py`、`tickets.py`、`hub.py`；`skills/decision-inbox-join/SKILL.md`、`commands/join.md`、`README.md`、两份 `plugin.json`；测试 `tests/test_onboard.py`、`test_view.py`、`test_tickets.py`、`test_hub.py`、`test_packaging.py`；`spec/relay-checkpoint-authority.md`（实测记录）、本模块 `todo.md`。
- 用户可见界面：接入预览的警告、约定块两节新文字、主视图组合答复块、F13 提示、问状态时的回复。都由测试逐字核对；实测时在真实会话里看到。

## Task List

### Phase 1：接入

- [ ] Task 1：R1 核对 Codex 会话能否加载约定块（Spec 验收 1）
- [ ] Task 2：R2 检查点答复即授权（Spec 验收 2、3）
- [ ] Task 3：R3 检查点之间自主处理，项目规则更严格时提示（Spec 验收 4）

### Checkpoint 1（report）

- [ ] 全部测试全绿

### Phase 2：小返工

- [ ] Task 4：R4 组合答复复制块（Spec 验收 5）
- [ ] Task 5：F13 结束行指向事项时提示（Spec 验收 6）
- [ ] Task 6：没有待答事项时，认不出编号的话附主视图（Spec 验收 7）
- [ ] Task 7：重新接入收件枢纽时补 `patrolTaskAt`（Spec 验收 8）

### Checkpoint 2（report）

- [ ] 全部测试全绿；scratchpad 临时协作组用命令行跑一遍：Codex 接入在错误目录时的警告、打开 R2 的约定块、组合答复、F13 提示、问状态，记下输出

### Phase 3：说明与版本

- [ ] Task 8：接入技能、`/join` 命令、README、版本 0.0.5（Spec 验收 9）

### Checkpoint 3（report）

- [ ] 全部测试全绿；推送本分支（PR #2 合并前不另开 PR，合并后再开）

### Phase 4：实测

- [ ] Task 9：di-e2e 守卫对照实测（Spec 验收 10）。先问用户；本会话驱动；对照组、实验组各至少 2 次；结果写进规格并抄送 spec-guard-monitor

### Checkpoint 4（gate）：模块最终验收

- [ ] 全部测试全绿；10 条验收标准逐条有测试或实测记录；列出实际改动的文件；原样附上规格的改动差异
- [ ] 本 Plan 获批即授权：
  - 返工 onboarding、hub-loop、hub-view、wait-tickets 的代码；
  - 版本号升到 0.0.5；
  - 每个任务完成后在当前分支做一次本地提交，并推送本分支；
  - 在 scratchpad 里建临时协作组。
- [ ] 不授权：Task 9 的实测（到时另外问你）、开或合并 PR、改用户的 Codex 配置、改任何真实项目的规则文件
