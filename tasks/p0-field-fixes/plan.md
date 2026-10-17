<!-- spec-guard: review pending -->
# Implementation Plan: p0-field-fixes

> 依据：`spec/p0-field-fixes.md`（用户 2026-10-18 批准）。任务清单：`tasks/p0-field-fixes/todo.md`。

## Overview

五个代码与文档任务，加一次实测。顺序：先做互不相干、风险最小的契约升级，再做巡视卡住（F-P0-5）和叫醒（F-P0-2、F-P0-3）这两处影响 S1 重测的修改，然后是退回说明与约定块（F-P0-1），最后是文档与版本（F-P0-4）。每个任务都先写失败的测试，再改代码。

## Architecture Decisions

- **F-P0-5**：在 `decision_inbox/__main__.py` 加一个 `_consume(path)`：读完文件后，只有当路径在 `$TMPDIR`（含 `/tmp`、`/private/tmp`、`/private/var/folders`）或协作组 `io/` 目录下时才删除。只用于收件枢纽与巡视的命令：`patrol plan --agents`、`patrol record --plan`、`inbox receive --inbox`、`inbox reply --text-file/--agents`、`view --agents/--outbox`。只读查询命令（`query …`、`doctor`）不删。命令失败（解析出错）时不删，便于排查。
- **F-P0-2、F-P0-3**：`patrol._wakes` 的条件扩成「停着且有积压」或「空闲（`activity == "idle"`）且 `waiting_oldest_at` 距今 ≥ `IDLE_WAKE_MINUTES = 5`」；收件枢纽也走同一判断，沿用 `_wake` 的每次积压只叫一次、叫不醒通知用户。`_wake_hub` 保留，同一轮已叫过就不重复。
- **建议文字**：`view._ADVICE_BY_CODE["idle-backlog"]` 按宿主分：Claude「巡视会叫醒 {who}；叫不醒就打开它」，Codex「打开 {who} 的任务」。
- **F-P0-1**：`items._receive_wait_user` 处理【取代 #N】时，若 `#N` 不是本会话的事项、但等于本会话某项待答事项的 `relayId`，退回说明改写为「#N 是邮箱号，对应事项 #M；去掉【取代】靠默认取代，或改写【取代 #M】」；问题代码仍为 `not-owner`（契约不变）。`onboard.py` 约定块第 128 行那条按规格改写。
- **版本**：两份 `plugin.json` 0.0.12。

## Task List

- [ ] Task 1：契约升到 v1.5（Spec 验收 5）
- [ ] Task 2：命令读完输入文件即删除（F-P0-5，Spec 验收 4）
- [ ] Task 3：巡视叫醒空闲积压的会话与收件枢纽，建议文字按宿主分（F-P0-2、F-P0-3，Spec 验收 2）
- [ ] Task 4：取代写邮箱号的退回说明与约定块（F-P0-1，Spec 验收 1）
- [ ] Task 5：文档与版本 0.0.12（F-P0-4，Spec 验收 3、6）

### Checkpoint（gate）：S1 重测

- [ ] 开始前另问用户：升级 di-p0 用的插件（Claude 侧 `claude plugin update`、Codex 侧重装，都改用户配置），重开收件枢纽与负责人会话（会话号会变，名册要重跑接入）；然后给空闲的负责人发一条关闭唤醒的消息，看一轮巡视内是否被叫醒并回复；记录 3 轮巡视耗时。
- [ ] 不过就记成新任务修，再重测。

### Checkpoint（gate）：模块最终验收

- [ ] 全部测试全绿；7 条验收标准逐条有证据；列出实际改动的文件
- [ ] 本 Plan 获批即授权：Task 1–5 的代码、测试、文档修改；每个任务完成后本地提交并推送本分支；给契约负责人发升级通知
- [ ] 不授权：改契约仓库、改用户的 Claude／Codex 插件配置（S1 重测前另问）、开或合并 PR、碰真实协作组
