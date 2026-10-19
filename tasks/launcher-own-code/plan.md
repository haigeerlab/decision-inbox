<!-- spec-guard: review approved -->

# Implementation Plan: launcher-own-code

> 依据：`spec/launcher-own-code.md`。任务清单：`tasks/launcher-own-code/todo.md`。分支 `claude/gifted-montalcini-e7661a`（从 main 85debcf 快进）。

需要的外部条件：无。

## Overview

一个任务：先写在 85debcf 上失败的测试，再改启动脚本。最后最终验收、开 PR（base main，由用户合并），不发版、不打标签。

## Architecture Decisions

- 启动脚本最后一行改为 `exec python3 -c 'import sys; sys.path[0] = sys.argv.pop(1); import runpy; runpy.run_module("decision_inbox", run_name="__main__", alter_sys=True)' "$ROOT" "$@"`：用公开的 `runpy.run_module`，`alter_sys=True` 让 `sys.argv[0]` 与 `-m` 一样指向 `__main__.py`。
- 测试放在 `tests/test_packaging.py`，用 `subprocess` 以临时目录为 `cwd` 运行 `REPO/bin/decision-inbox glossary`。

## Task List

- **Task 1 启动脚本只跑自己的代码**（Spec 要做的 1、2；验收 1、2、3）：先写测试（临时目录放假 `decision_inbox/__init__.py`、`__main__.py` 打印标记，再放假 `runpy.py`），确认在 85debcf 上失败；再改 `bin/decision-inbox`；跑全量测试；用 3.10 手工复核 `whoami` 仍按调用者目录。

## Checkpoint（gate）：模块最终验收

列出改动文件与测试数，批准后开 PR。

## 风险

| 风险 | 对策 |
|---|---|
| 引导代码在换路径前导入了非内建模块 | 只先导入 `sys`；测试放假 `runpy.py` |
| `sys.argv` 与 `-m` 不一致影响参数解析 | `alter_sys=True`；全量测试里调用 `bin/decision-inbox` 的用例照跑 |
