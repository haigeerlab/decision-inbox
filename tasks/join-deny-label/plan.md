<!-- spec-guard: review pending -->

# Implementation Plan: join-deny-label

> 依据：`spec/join-deny-label.md`（用户 2026-10-19 批准，不做外部审查）。任务清单：`tasks/join-deny-label/todo.md`。分支 `claude/join-deny-label`（从 main 64f79d8 开出）。

## Overview

一个任务：先写会失败的测试（打印的标签与写入的数组逐条一致），再把 `__main__.py` 的两处标签换成按种类的对照表。最后做一次最终验收。不升版本号，发版另开 PR。

## Architecture Decisions

- `__main__.py` 加一张 `_RULE_KINDS = {"allow": "放行", "ask": "先问", "deny": "禁止"}`，两处打印都用 `_RULE_KINDS.get(kind, kind)`。
- 测试放在 `tests/test_onboard.py`（沿用 `ScopedInstallPermissionsTest.test_preview_prints_removals` 的命令行调用法）：预览一次、确认一次，解析每行「要加／已加 标签：规则」，与 `settings.local.json` 里各数组比对。

## Task List

- **Task 1 标签与测试**（Spec 验收 1–3）：先写测试，确认在当前代码上失败（禁止规则显示「先问」）；再改 `__main__.py`。验证：先失败后通过；全量测试、旧称扫描通过。

## 检查点

- Checkpoint（gate）：模块最终验收——列出改动的文件、每条验收标准的证据和测试数，然后开 PR（base main）。

## 影响面

只影响接入预览与写入回执的显示文字；写入不变，已接入的线不用重跑。

## 风险

| 风险 | 对策 |
|---|---|
| 以后再加规则种类又被归错 | 不认识的种类原样打出种类名；测试逐条核对 |
