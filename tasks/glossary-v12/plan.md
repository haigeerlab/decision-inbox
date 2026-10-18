<!-- spec-guard: review pending -->

# Implementation Plan: glossary-v12

> 依据：`spec/glossary-v12.md`（用户 2026-10-19 批准）。任务清单：`tasks/glossary-v12/todo.md`。分支 `claude/glossary-v12`（从 main 开出，main 已含 0.0.24）。

## Overview

一个任务，先写失败的测试再改：审查列标记、旧称扫描、README、术语表副本一起改，因为扫描加词后 README 和代码必须同时改掉才能转绿。最后做一次最终验收。不升版本号。

## Architecture Decisions

- **审查列**：只改 `mapview._REVIEW_MARKS` 的五个值，`review_cell` 的拼接逻辑和「（有参考意见）」后缀不动。
- **旧称扫描**：`tests/test_glossary.py` 的 `OLD` 加「待审核」→「待批准」、「待审」→「待批准」；模块文档字符串写 v1.2。
- **术语表副本**：`docs/glossary.md` 用原件 `livesaas-integration/GLOSSARY.md` 的正文覆盖，开头保留本仓库的来源行并改为 v1.2。

## Task List

- **Task 1 审查列标记、旧称扫描、README 与术语表副本**（Spec 验收 1–4）：
  - 先改测试（确认失败）：
    - `tests/test_mapview.py` 的审查列与整表断言改为新写法（✔、待批准、改过待重审、标记无效、无标记）；
    - `tests/test_glossary.py` 的 `OLD` 加两个词，扫描应命中 `mapview.py` 和 README 第 106 行；
    - `tests/test_glossary.py` 第 159 行核对术语表副本版本的断言改为「术语表（v1.2」。
  - 再改 `mapview.py`、README 第 106 行、`docs/glossary.md`；`__main__.py` 第 656 行注释里的「v1.1」改为「v1.2」。
  - 验证：上面两组测试转绿；`diff` 核对术语表副本与原件正文一致；全量测试通过。

## Checkpoint（gate）：模块最终验收

列出改动的文件、每条验收标准的证据和测试数，然后开 PR（base main）。

## 影响面

- `/map` 审查列的显示文字；
- README 一行；
- 术语表帮助页（`/decision-inbox:glossary` 读的就是 `docs/glossary.md`）。

不改协作规则段，已接入的线不用重新接入。

## 风险

| 风险 | 对策 |
|---|---|
| 「✔」在某些终端或表格里对不齐 | spec-guard 的 `/map` 已经这样用；验收时实跑 `/map` 看一次 |
| 「待审」加进扫描后误伤别的词 | 已核对现行文字只有两处命中；如有例外，写进 ALLOWED 并说明原因 |
