<!-- spec-guard: review approved -->
# Implementation Plan: hub-patrol

> 依据：`spec/hub-patrol.md`（用户 2026-10-18 批准，假设均确认）。用户批准规格时授权「计划写完直接开工，不用再单独交审」。任务清单：`tasks/hub-patrol/todo.md`。

## Overview

四个任务，加一次实测。每个任务先写失败的测试再改。

## Architecture Decisions

- `hub.patrol_due(g, now)`：巡视登记过，且 `patrol.lastRunAt`（没有就看 `onboarding.patrolTaskAt`）距今 > `HUB_PATROL_MINUTES = 10`。`inbox receive`、`inbox reply` 的 JSON 输出加 `patrolDue`。
- `patrol.plan(..., from_hub=False)`：为真时 `_wakes` 与 `_wake_hub` 都跳过收件枢纽自己；`patrol plan` 加 `--from-hub`，计划文件记 `by`。
- `patrol.record` 把计划里的 `by`（缺省 `schedule`）写进 `patrol.run` 事件；`query.stats` 加 `patrol_by_hub`、`patrol_by_schedule`。
- 约定块 `hub.CONVENTION` 加「顺带巡视」一节：用 `{io}/agents.json`、`{io}/plan.json`（读完即删，沿用 F-P0-5）。
- 版本 0.0.14。

## Task List

- [ ] Task 1：`patrolDue` 与 `--from-hub`（Spec 验收 1、2）
- [ ] Task 2：巡视记录来源与按来源统计（Spec 验收 3）
- [ ] Task 3：约定块加「顺带巡视」（Spec 验收 4）
- [ ] Task 4：文档与版本 0.0.14（Spec 验收 5）

### Checkpoint（gate）：实测，开始前另问用户

- [ ] 升级插件、di-p0 收件枢纽重跑 hub-setup，触发一轮收件枢纽顺带巡视，核对事件 `by: hub`

### Checkpoint（gate）：模块最终验收

- [ ] 全部测试全绿；验收标准逐条有证据；列出实际改动的文件
- [ ] 授权：Task 1–4 的代码、测试、文档；每个任务完成后提交并推送本分支
- [ ] 不授权：改用户配置（实测前另问）、开或合并 PR、碰真实协作组
