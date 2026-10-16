<!-- spec-guard: review approved -->
# Implementation Plan: wait-tickets

> 依据：`spec/wait-tickets.md`（已批准）。任务清单：`tasks/wait-tickets/todo.md`。

## Overview

先做登记和由消息触发的两种关单（理由 1、2），再做理由 3、4，然后是提醒标记，最后是「今天已关闭」与计数。每个任务先写失败的测试，再实现到全绿，单独提交。代码在 `decision_inbox/tickets.py`。

## Architecture Decisions

- 状态放 group-store 的领域 `tickets`（`state/tickets.json`），以编号为键；事件 `tickets.opened`、`tickets.closed` 的 `ref` 是单号。
- 编号用共用序列，所以结束行里的 `#N` 可能是等待单，也可能是【等待用户】事项：只在 `tickets` 快照里找；找不到就忽略（属于 decision-queue），找到但不是本人的给 `not-own-ticket`。
- 理由 3 读 decision-queue 的 `items` 快照（只读）：事项属于同一发件人、状态已在 `forwarded` 之后、`sent` 里有消息编号，取最早一条的编号作依据。
- 时间一律转成绝对时间比较；分钟数向下取整；HH:MM 与「今天」按本机时区（`datetime.astimezone()`）换算。测试里用固定的带时区时间，避免依赖运行机器的时区。
- 离线判断只用 relay-reader 的 `AgentFact.presence`（`offline`、`unreachable`）和积压字段，不另读 agent-relay。

## 影响面

新增：`decision_inbox/tickets.py`、`tests/test_tickets.py`。修改：`tasks/wait-tickets/todo.md`（勾选）、`.agent/state.json`（最终验收时切换当前模块）。不改其他已有文件，不涉及用户可见界面。

## Task List

### Phase 1：登记与关单

- [ ] Task 1：登记与理由 1、2（Spec 验收 1、2、3、8）
- [ ] Task 2：理由 3、4（Spec 验收 4、5）

### Checkpoint 1（report）

- [ ] 全部测试全绿

### Phase 2：提醒与汇总

- [ ] Task 3：提醒标记（Spec 验收 6、7）
- [ ] Task 4：今天已关闭与计数（Spec 验收 9、10）

### Checkpoint 2（gate）：模块最终验收

- [ ] 全部测试全绿；10 条验收标准逐条对应测试；列出实际改动的文件
- [ ] 本 Plan 获批即授权：每个任务完成后在当前分支做一次本地提交；不授权推送、不授权开 PR

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| 「今天」和 HH:MM 依赖运行机器的时区，测试在别的时区下不稳定 | 中 | 测试固定 `TZ=Asia/Shanghai` 环境变量并调用 `time.tzset()`，结束后恢复 |
| 结束行编号与事项编号共用序列，误关事项或误报 | 中 | 只在 `tickets` 快照里匹配；用例覆盖结束行写事项编号的情况 |

## Open Questions

无。
