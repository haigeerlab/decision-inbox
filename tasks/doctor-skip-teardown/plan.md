<!-- spec-guard: review pending -->

# Implementation Plan: doctor-skip-teardown

> 依据：`spec/doctor-skip-teardown.md`（用户 2026-10-19 批准）。任务清单：`tasks/doctor-skip-teardown/todo.md`。分支 `claude/doctor-skip-teardown`（从 main 开出，main 已含 0.0.26）。

## Overview

一个任务，先写失败的测试再改 `doctor._patrol`，最后实跑一次 doctor 并做最终验收。不升版本号。

## Architecture Decisions

- 在 `doctor.py` 加一个小函数 `_torn_down(g)`：读名册里 `role` 为 hub 的条目和 `onboarding.json` 的 `left`，hub 条目非空且全部在 `left` 里时，返回最晚的退出时间，否则返回 None。
- `_patrol` 开头先调它：有值就返回 `Check("巡视", "ok", "本插件", "<组> 的决策收件箱已卸载（<时间>），状态目录保留，不再检查巡视")`，其余逻辑不动。时间按 doctor 现有的写法显示。

## Task List

- **Task 1 doctor 跳过已卸载的组**（Spec 验收 1–5）：
  - 先写测试（`tests/test_doctor.py` 的 `PatrolTest`）：收件箱已退出、巡视登记还在、巡视很久没跑 → ✔ 含「已卸载」和退出时间，`render` 的合计不计异常；有两个 hub 条目只退一个 → 照常报 ✘；名册里没有 hub → 照现在的做法。
  - 再改 `doctor.py`。
  - 实跑：`~/.decision-inbox/bin/decision-inbox` 指向的是已装版本，所以用本分支的代码（`python3 -m decision_inbox doctor --group di-e2e --group pp-probe` 或等价写法）对本机的 di-e2e、pp-probe 跑一次，确认两组巡视一项为 ✔ 已卸载。
  - 验证：新测试先失败后通过；原有 `PatrolTest` 不变；全量测试通过。

## Checkpoint（gate）：模块最终验收

列出改动的文件、每条验收标准的证据和测试数，然后开 PR（base main）。

## 影响面

只有 doctor 的巡视一项。不改协作规则段，已接入的线不用重新接入。

## 风险

| 风险 | 对策 |
|---|---|
| 换收件箱时旧 hub 记了 left、新 hub 还在 → 误判为已卸载 | 要求所有 hub 条目都在 left 里才算；测试覆盖两个 hub 只退一个 |
