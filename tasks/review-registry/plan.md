<!-- spec-guard: review approved -->
# Implementation Plan: review-registry

> 依据：`spec/review-registry.md`（已批准）。任务清单：`tasks/review-registry/todo.md`。

## Overview

三个任务依次做：登记（含历史与生效时间）、显示标签、审查结论与轮数。每个任务先写失败的测试，再实现到全绿，单独提交。全部基于 group-store 的事务和 message-protocol 的解析结果，不碰 agent-relay。

## Architecture Decisions

- 全部逻辑在 `decision_inbox/reviews.py`。状态放 group-store 的领域 `reviews`（`state/reviews.json`），每次变更在同一个事务里追加事件（`reviews.registered`、`reviews.unregistered`、`reviews.conclusion`）并替换快照。
- 快照结构：`registrations`（按会话的 relayName 记一个列表，每项带 `reviewer`、`nodes`、`since`、`until`、批准依据）与 `reviews`（按审查编号记送审方、审查者、节点、每轮的时间与结论、是否已结束）。修改登记 = 给当前那份写上 `until`，再追加一份新的。
- 名字对应：登记和发件人用 agent-relay 的身份名（`relayName`）；【审查结论】里的「送审方」写的是短名，用 group-store 的 `find_session(short_name=...)` 换成身份名。短名在名册里找不到时按 `bad-conclusion` 处理。
- 时间比较：生效时间与事项收到时间都是带时区的 ISO 8601，用 `datetime.fromisoformat` 转成绝对时间再比较，不比字符串。
- `mentions` 的取法：message-protocol 的解析结果不保留原文全文，所以从各字段的值里逐行找含「审查」的行，原样返回（不含已解析的「架构审查」那一行的字段名）。

## 影响面

新增：`decision_inbox/reviews.py`、`tests/test_reviews.py`。修改：`tasks/review-registry/todo.md`（勾选）、`.agent/state.json`（最终验收时切换当前模块）。不改其他已有文件，不涉及用户可见界面。

## Task List

### Phase 1

- [ ] Task 1：审查者登记（Spec 验收 1、2，以及 10 的登记部分）
- [ ] Task 2：显示标签（Spec 验收 3、4、5、6）

### Checkpoint 1（report）

- [ ] 全部测试全绿

### Phase 2

- [ ] Task 3：审查结论与轮数（Spec 验收 7、8、9，以及 10 的结论部分）

### Checkpoint 2（gate）：模块最终验收

- [ ] 全部测试全绿；10 条验收标准逐条对应测试；列出实际改动的文件
- [ ] 本 Plan 获批即授权：每个任务完成后在当前分支做一次本地提交；不授权推送、不授权开 PR

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| 生效时间与收到时间时区不同导致先后判断错 | 中 | 一律转成绝对时间比较；用例覆盖 `+08:00` 与 `Z` 混用 |
| 显示文字与需求第 4.3 节有细微出入（标点、全半角） | 中 | 测试里逐字写死需求表中的文字 |
| 短名改过后旧的【审查结论】对不上会话 | 低 | 结论按收到时的名册换算并存身份名，之后改短名不影响已记录的轮数 |

## Open Questions

无。
