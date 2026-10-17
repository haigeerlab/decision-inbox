<!-- spec-guard: review approved -->
# Implementation Plan: answer-handoff-gaps

> 依据：`spec/answer-handoff-gaps.md`（已批准）。任务清单：`tasks/answer-handoff-gaps/todo.md`。

## Overview

规格里的三处返工互相独立，各做一个任务：停止钩子、巡视、收件枢纽的【答复告知】。之后改约定块，并把版本升到 0.0.3。最后实测【答复告知】能真的送到。每个任务先写失败的测试，再实现到全绿，单独提交。

## Architecture Decisions

- **钩子**：在 `stophook.decide` 里，原有的「有人在等你」判断之后，再取本会话已答未恢复的事项。两部分各自算出几行文字，最后合成一条 `reason`。只要有一部分不为空就拦。已答未恢复用 `items.by_status(g, "forwarded", "picked", "acknowledged")` 筛出 `sender` 是本会话的事项。原话取事项 `answers` 里最后一次的 `original`。
- **巡视**：新增 `_handoffs(ctx)`，放在 `_user_notices` 之前调用，保证它的通知先进入动作列表。叫醒复用 `_wake` 的去重：它把负责人加进 `live["wakes"]`，这一轮没叫过才出 `wake:` 动作。`_cap` 原本按出现顺序保留前 2 条，这类通知已经排在最前，所以超过 3 条时会先合并别的通知。
- **【答复告知】**：`protocol.format_answer_notice` 生成正文。`hub._queue_answers` 在每个事项的答复入队后，按规则给开发线入队 `kind: "notice"` 的消息。`hub.sent` 原本只对 `answer` 调 `record_sent`，`notice` 不进事项状态，所以不用改。
- **约定块**：只往三段常量文本里各加一条，测试在原有的要点表里补关键词。

## 影响面

- 修改：
  - `decision_inbox/stophook.py`、`patrol.py`、`hub.py`、`protocol.py`、`onboard.py`；
  - `.claude-plugin/plugin.json`、`.codex-plugin/plugin.json`；
  - `README.md`：一句关于【答复告知】的说明；
  - 对应测试：`tests/test_stophook.py`、`test_patrol.py`、`test_hub.py`、`test_onboard.py`、`test_packaging.py`；
  - `spec/answer-handoff-gaps.md`：实测记录；
  - `tasks/answer-handoff-gaps/todo.md`。
- 用户可见界面：钩子的拦截说明、桌面通知文字、【答复告知】正文、约定块。都由测试逐字核对；【答复告知】在 Task 5 实测时看到实际收件。

## Task List

### Phase 1：三处返工

- [ ] Task 1：停止钩子拦「已答未恢复」（Spec 验收 1、2、3；H17 回归场景）
- [ ] Task 2：巡视处理离线负责人压着的答复（Spec 验收 4、5、6）
- [ ] Task 3：收件枢纽抄送【答复告知】（Spec 验收 7、8）

### Checkpoint 1（report）

- [ ] 全部测试全绿

### Phase 2：约定与版本

- [ ] Task 4：约定块加三条、README 一句、版本 0.0.3（Spec 验收 9、10）

### Checkpoint 2（report）

- [ ] 全部测试全绿；在 scratchpad 临时协作组上用命令行跑一遍：已答未恢复时钩子拦截、离线负责人时巡视计划、负责人事项答复后生成【答复告知】，记下输出

### Phase 3：实测

- [ ] Task 5：实测【答复告知】送达（Spec 验收 11）。先问用户：登记测试身份、发消息。结果写进规格的实测记录

### Checkpoint 3（gate）：模块最终验收

- [ ] 全部测试全绿；11 条验收标准逐条有测试或实测记录；列出实际改动的文件；原样附上规格的改动差异；列出拟回告
- [ ] 本 Plan 获批即授权：
  - 返工 stop-hook、patrol、hub-loop、onboarding 的代码；
  - 版本号升到 0.0.3；
  - 每个任务完成后在当前分支做一次本地提交；
  - 在 scratchpad 里建临时协作组。
- [ ] 不授权：Task 5 的实测（到时另外问你）、推送、开 PR、回告

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| 新的拦截条件误拦：会话已经做完却忘了发【已恢复】，每轮收工都被拦一次 | 中 | 这正是想要的提醒；每轮只拦一次，说明里写清怎么解除；原有的放行规则照旧优先 |
| 叫醒重复：原有规则和新规则同一轮都叫醒同一个负责人 | 低 | 动作编号都是 `wake:<身份名>`，生成前查重；用测试核对只出现一次 |
| 开发线把【答复告知】当成批准 | 中 | 正文和开发线约定块都写明不是批准；用测试逐字核对 |

## Open Questions

无。
