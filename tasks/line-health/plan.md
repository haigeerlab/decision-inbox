<!-- spec-guard: review approved -->
# Implementation Plan: line-health

> 依据：`spec/line-health.md`（已批准）。任务清单：`tasks/line-health/todo.md`。

## Overview

先搭输入整理与进度快照（所有判断都要用到「上次有进展的时间」），再做 7 个状态词，然后分两批做 10 个信号：会话与积压类（1、2、4、5、10），进度与审查类（3、6、7、8、9）。每个任务先写失败的测试，再实现到全绿，单独提交。代码在 `decision_inbox/health.py`。

## Architecture Decisions

- 入口 `assess(g, now, relay, maps, previous)`。内部先把输入整理成每个会话一份 `Facts`（名册条目、agent-relay 事实、spec-guard 读取结果、该会话的开着的等待单、待答事项、上次有进展时间），状态词和信号都只读 `Facts`，不再各自去取数据。
- 等待单、待答事项、审查轮数分别用 wait-tickets、decision-queue、review-registry 已有的读取函数或快照（`tickets.open_tickets`、`items.pending`、`reviews.round_stats`），不另写读取逻辑。
- 「当前模块」取 spec-guard 结果里的 `active_module` 对应的 `ModuleFact`；「已批准、没勾完」= `step == "build"`、`review_plan == "approved"`、`progress_done < progress_total`。
- 进度快照结构：`{"version": 1, "at": now, "sessions": {relayName: {moduleId: {"done": n, "changedAt": t|None}}}}`，可直接 JSON 保存。
- 时间一律转绝对时间计算；小时数向下取整，至少 1。

## 影响面

新增：`decision_inbox/health.py`、`tests/test_health.py`。修改：`tasks/line-health/todo.md`（勾选）、`.agent/state.json`（最终验收时切换当前模块）。不改其他已有文件，不涉及用户可见界面。

## Task List

### Phase 1：基础

- [ ] Task 1：输入整理、进度快照与常量（Spec 验收 11、12）
- [ ] Task 2：7 个状态词（Spec 验收 1～5）

### Checkpoint 1（report）

- [ ] 全部测试全绿

### Phase 2：信号

- [ ] Task 3：会话与积压类信号 1、2、4、5、10（Spec 验收 6、7）
- [ ] Task 4：进度与审查类信号 3、6、7、8、9（Spec 验收 4 的信号部分、8、9、10）

### Checkpoint 2（gate）：模块最终验收

- [ ] 全部测试全绿；12 条验收标准逐条对应测试；列出实际改动的文件
- [ ] 本 Plan 获批即授权：每个任务完成后在当前分支做一次本地提交；不授权推送、不授权开 PR

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| 构造测试数据繁琐（名册、等待单、事项、审查、relay、spec-guard 六路） | 中 | 测试基类提供一组构造函数，每个用例只改与它相关的那一项 |
| 状态词判定顺序写错导致互相遮蔽 | 中 | 验收 1 专门用「同时满足两个条件」的用例锁定顺序 |
| 依赖模块的读取函数不足以表达所需事实 | 低 | 若需改动已完成模块，按返工流程停下来问，不在本模块里绕过 |

## Open Questions

无。
