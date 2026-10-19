<!-- spec-guard: review approved -->

# Implementation Plan: my-waits

> 依据：`spec/my-waits.md`。任务清单：`tasks/my-waits/todo.md`。分支 `claude/waiting-queries`（从 main 11384b3）。

需要的外部条件：无。

## Overview

三个任务，每个先写在 11384b3 上失败的测试：渲染函数 → 命令行与斜杠命令 → 文档与版本。之后最终验收、开 PR（base main，由用户合并），不打标签。

## Architecture Decisions

- `query.render_waits(g, me, now, relay=None)` 放在 `query.py`，与 `render_lines` 并列；等待记录直接用 `tickets.open_tickets(g, now, relay)` 的 `TicketView`（标记、等了多久都现成），「可能已失效」用 `TicketView.maybe_stale`／`stale_item`。
- 「是我」的判断：`me` 是 agent-relay 名；名册里查到我的 `shortName`；等待记录 `targetRelay == me`，或 `target` 等于我的 `shortName`／`me`。
- 待决事项：`items` 状态里 `sender == me` 且状态不在 `items.FINAL`；按 Spec 假设 2 的三种写法，用 `items.delivered`、`items.is_go_to_session`。
- 决策收件箱：名册里我的 `role == "hub"` 时只输出提示。`me` 不在名册时报错退出 2（与组不存在同样处理）。
- 命令行 `query waits <组> --me <名> [--agents <文件>]`；`--agents` 可省，省了就不判断离线。

## Task List

- **Task 1 渲染「我在等什么／谁在等我」**（Spec 要做的 1；验收 1～4）：`tests/test_query.py` 新类，造名册（两条开发线 + 决策收件箱）、等待记录、三种状态的待决事项和已结束的事项，断言输出行；带／不带 relay 快照各一次。
- **Task 2 命令行与斜杠命令**（要做的 2、3；验收 5）：子进程跑 `query waits`，比对运行前后状态目录不变；`me` 不在名册退出 2；`commands/waits.md` 照 `/lines`；打包测试的命令清单加 `waits`。
- **Task 3 README 与版本号**（要做的 4）：「查询命令」加一行；两份 `plugin.json` 升到 0.0.33；升级说明加一句（没改协作规则段，不用重跑接入）；全量测试。

## Checkpoint（gate）：模块最终验收

列出改动文件与测试数，批准后开 PR。（不改界面，没有 UI 自验；本机实跑一次 `query waits` 对 di-p0 的某条线给你看输出。）

## 风险

| 风险 | 对策 |
|---|---|
| 「在等谁」写昵称认不出 | 与主视图一致，只认会话名和 agent-relay 名；Spec 已写明 |
| 打包测试对命令清单、README 有硬编码检查 | Task 2、3 一并更新 |
