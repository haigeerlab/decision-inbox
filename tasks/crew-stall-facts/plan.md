<!-- spec-guard: review pending -->

# Implementation Plan: crew-stall-facts

> 依据：`spec/crew-stall-facts.md`（用户 2026-10-19 批准，含对假设 3 的两处补充）。任务清单：`tasks/crew-stall-facts/todo.md`。分支 `claude/crew-stall-facts`（从 main 开出，main 已含 0.0.25）。

## Overview

三个任务，各自先写失败的测试再改：先读字段，再做按模块判断与叫醒，最后做主视图、文档和实跑。最后做一次最终验收。不升版本号。

## Architecture Decisions

- **读字段**（`crew.py`）：`Module` 加 `started_at`、`last_commit_at`、`commits_error`、`asks`（`tuple[(node, tuple[at, ...])]`）、`waiting_user`（bool），都有默认值，`_parse` 用一个小函数宽松读取：形状不对就当没有，契约字段的校验不变。
- **按模块判断**（`stall.py`）：
  - 新函数 `_module_findings(now, crews, cfg)` 返回 `{key: where}`，键为 `<模块协调邮箱名>|stalled:<模块>`、`|repeat:<模块>`；`_findings` 合并它的结果，`asks` 加一个可选参数 `crews`。
  - `asks` 里按键前缀取线；模块键的叫醒文字用 `module_ask_text`：开头写「模块 <名>：<卡在哪>」，三个选项同 R14，挂起写「按 module-crew 的做法挂起这个模块」，不提 spec-guard 的 module-suspend。
  - 跳过条件、时间取法按 Spec「要做的」第 2 条。
- **巡视**（`patrol.plan`）：把已有的 `crews` 参数传给 `stall.asks`，不新增读取。
- **主视图**（`overdue_rows`）：键里有 `:<模块>` 时，行里写「<线名>（模块 <名>）」；其余不变。

## Task List

- **Task 1 读新字段**（Spec 验收 6、7 的解析部分）：
  - 先写测试：`tests/test_crew.py` 用 0.4.0 形状的一行（取自实跑输出）断言五个新值；0.3.x 形状（没有新字段）与各种坏形状（`commits` 不是对象、`ats` 不是列表等）新值都为空，原有字段照常。
  - 验证：新测试先失败后通过；`test_crew` 原有断言不改。
- **Task 2 按模块判断与叫醒**（Spec 验收 1–4、6）：
  - 先写测试：`tests/test_stall.py` 构造 `CrewRead`，覆盖：13 小时没提交叫醒一次、12 小时内不重复；没有 `last` 用 `startedAt`；`commits.error` 有值不按时间判；两个时间都没有不判；24 小时内 3 次报批叫醒、2 次或超窗不叫；五种跳过情况；0.3.x 形状或读不到时不产生模块键。`tests/test_patrol.py` 断言巡视把 crews 传进来后出现 `stall:<协调>|stalled:<模块>` 动作，文字含模块名与三个选项。
  - 验证：新测试先失败后通过；线级 R14 原有测试不变。
- **Task 3 主视图、文档与实跑**（Spec 验收 5、7、8）：
  - 先写测试：`overdue_rows` 对模块键写出「（模块 <名>）」，抛了【等待用户】就不列。
  - 再改：`overdue_rows`；README R14 一节加一句（需 module-crew 0.4.0、跳过哪些模块）；`spec/CAPABILITY-MAP.md` 外部依赖表加一行（0.4.0 字段与 `commits.last` 修订后的含义）。
  - 实跑：用 module-crew 0.4.0 副本对 crew-rehearsal 跑 `sessions --json`，经本插件解析后调 `_module_findings`，确认读出新字段且不产生叫醒（模块都已合入）。
  - 验证：全量测试通过。

## Checkpoint（gate）：模块最终验收

列出改动的文件、每条验收标准的证据和测试数，然后开 PR（base main）。

## 影响面

- 巡视的叫醒动作（多出按模块的叫醒）；
- 主视图的停滞行；
- README 一句、能力图外部依赖表一行。

不改协作规则段，已接入的线不用重新接入；module-crew 仍是 0.3.0 时没有任何变化。

## 风险

| 风险 | 对策 |
|---|---|
| 模块协调同时收到线级和模块级两次叫醒 | Spec 关键决策 3 已接受；键不同，各受 12 小时去重限制 |
| 0.4.0 字段形状和文档不一致 | 宽松读取，形状不对当作没有；实跑核对一次 |
| 时间带时区 | 统一用现有 `_instant` 解析（`fromisoformat`），测试里用带 +08:00 的值 |
