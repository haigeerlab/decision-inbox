<!-- spec-guard: review approved -->
# Implementation Plan: patrol-cadence

> 依据：`spec/patrol-cadence.md`（用户 2026-10-18 批准）。用户 2026-10-18 批准规格时授权「计划写完直接开工，不用再单独交审」。任务清单：`tasks/patrol-cadence/todo.md`。

## Overview

三个任务：停摆提示写两种原因；`query stats` 加巡视节奏；文档与版本。每个任务先写失败的测试再改。

## Architecture Decisions

- 提示文字集中在 `hub.patrol_alarm` 的 `fix`；doctor「巡视」一项复用同一句，不再各写一份。
- 巡视节奏：`query.stats` 从区间内的 `patrol.run` 事件按 `data.now`（缺省用事件 `at`）排序，算轮数、相邻最长间隔、间隔 > `hub.PATROL_STALE_MINUTES` 的次数；Stats 加 `patrol_runs`、`patrol_max_gap`、`patrol_stale` 三个字段，文本与 JSON 输出各加一行／三个字段。
- 版本 0.0.13。

## Task List

- [ ] Task 1：停摆提示写两种原因（Spec 验收 1）
- [ ] Task 2：`query stats` 加巡视节奏（Spec 验收 2）
- [ ] Task 3：文档与版本 0.0.13（Spec 验收 3、4）

### Checkpoint（gate）：模块最终验收

- [ ] 全部测试全绿；4 条验收标准逐条有证据；列出实际改动的文件
- [ ] 授权：Task 1–3 的代码、测试、文档修改；每个任务完成后提交并推送本分支
- [ ] 不授权：改用户配置、开或合并 PR、碰真实协作组
