<!-- spec-guard: review approved -->
# Implementation Plan: hub-cutover-settings

> 依据：`spec/hub-cutover-settings.md`（用户 2026-10-18 批准）。任务清单：`tasks/hub-cutover-settings/todo.md`。分支 `claude/livesaas-seam`，接在 crew-coordinator-seam 之后做。

## Overview

一共两个任务：编号起点；把「欠回复不进主视图和巡视」固定成测试，并补上文档。和 crew-coordinator-seam 合发 0.0.16，不单独升版本。

## Architecture Decisions

- `store.set_start_number(g, n)`：在一次事务里检查三件事：`counter.json` 的 `next == 1`、没有事项、没有等待单。有一条不满足就抛 `StartNumberError`（中文写明原因），什么都不改；都满足就把 `next` 写成 n。n 必须是 1 到 1000000 的整数。
- `onboard.hub(..., start_number=None)`：预览时检查 n 合不合法、这个组能不能设起点（组还不存在就算能设），在 steps 里写一句「事项和等待单从 #N 开始编号」；确认时，先 `init_group`，再 `set_start_number`，最后 `_commit`。检查不过时抛 `JoinError`，命令返回退出码 2。
- `__main__`：`onboard hub` 加参数 `--start-number`，类型是 int。
- 欠回复：不改代码。加一个测试：在 relay 的数据里放进 `owesReplies`，断言主视图、巡视计划、doctor 的输出里都不出现它（也不出现「欠回复」字样）。
- 文档：README「换收件枢纽」一节；`commands/hub-setup.md` 加一句，替换已有收件枢纽时问用户编号起点。

## Task List

- [x] Task 1：编号起点（Spec 验收 1–3）
- [x] Task 2：欠回复回归测试和文档（Spec 验收 4、5）

### Checkpoint（gate）：模块最终验收

- [x] 全部测试通过；验收标准逐条有证据；列出实际改动的文件
- [x] 授权范围：Task 1–2 的代码、测试、文档；每个任务完成后提交并推送 `claude/livesaas-seam`
- [x] 不授权：改用户配置、开 PR 或合并 PR、碰 LIVE-SAAS
- [ ] 实测（Spec 验收 6）放到联合演练阶段，开始前另问用户

## Risks

| 风险 | 预防 |
|---|---|
| 已有组被改了起点 | 只在「next 为 1，且没有事项、没有等待单」时允许，测试覆盖已编号的情况 |
| 收件枢纽重跑接入时又带上了 `--start-number` | 组已经编过号就报错并说明原因；没编过号时重设同一个值不出错 |
