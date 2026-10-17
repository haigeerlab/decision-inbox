<!-- spec-guard: review approved -->
# Implementation Plan: decision-queue

> 依据：`spec/decision-queue.md`（已批准）。任务清单：`tasks/decision-queue/todo.md`。

## Overview

按事项的生命周期顺序做：收单与退回 → 取代、撤回与排序 → 解析用户回复 → 生成并分发答复 → 状态推进与追溯。每个任务先写失败的测试，再实现到全绿，单独提交。代码在 `decision_inbox/items.py`。

## Architecture Decisions

- 状态放 group-store 的领域 `items`（`state/items.json`），每个事项以编号为键；每次变化在同一个事务里追加 `items.*` 事件并替换快照，事件的 `ref` 是事项编号，`/item` 直接按编号取事件。
- 收单时调用 review-registry 的 `display_label`，把标签文字、`warn`、`highlight` 存进事项，之后不再重算。
- 解析回复只依赖快照里的事项（选项字母、状态），不再重新解析原文。
- 多线分发：发件人一份用 `format_user_reply`；各适用会话用 `format_multiline_replies`，短名经名册换成 agent-relay 身份名作为收件人。
- 状态推进只前进不后退：`forwarded → picked → acknowledged → closed`；多收件人时取所有收件人里最慢的那一个（规格假设 2）。`superseded`、`withdrawn` 不再被投递事实或【已恢复】改动。
- 退回说明格式固定为「退回：你的【等待用户】没有收进待答表，原因：」加逐条中文说明，最后一句请补全后重新抛出。

## 影响面

新增：`decision_inbox/items.py`、`tests/test_items.py`。修改：`tasks/decision-queue/todo.md`（勾选）、`.agent/state.json`（最终验收时切换当前模块）。不改其他已有文件，不涉及用户可见界面。

## Task List

### Phase 1：收单

- [ ] Task 1：收单与退回（Spec 验收 1、2、3）
- [ ] Task 2：取代、撤回与排序（Spec 验收 4、5）

### Checkpoint 1（report）

- [ ] 全部测试全绿

### Phase 2：答复

- [ ] Task 3：解析用户回复（Spec 验收 6、7、8）
- [ ] Task 4：生成答复与多线分发（Spec 验收 9、10）

### Checkpoint 2（report）

- [ ] 全部测试全绿

### Phase 3：状态

- [ ] Task 5：状态推进与追溯（Spec 验收 11、12、13）

### Checkpoint 3（gate）：模块最终验收

- [ ] 全部测试全绿；13 条验收标准逐条对应测试；列出实际改动的文件
- [ ] 本 Plan 获批即授权：每个任务完成后在当前分支做一次本地提交；不授权推送、不授权开 PR

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| 回复切分把用户原话里的「，」误当成多项分隔 | 高 | 只有每一段都以已存在的编号开头时才切分；否则整句作为一项，没编号就问 |
| 多收件人时状态推进口径出错，事项过早显示「已确认」 | 中 | 用三收件人、只确认其中两个的用例覆盖 |
| 事项快照随事项增多变大 | 低 | 第一版事项量小（实验期一天几十项）；保留期限已定为永久，以后若变慢再按状态拆分，不在本模块预先优化 |

## Open Questions

无。
