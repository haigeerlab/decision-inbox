<!-- spec-guard: review approved -->

# Implementation Plan: scope-authority-defaults

> 依据：`spec/scope-authority-defaults.md`（用户 2026-10-19 批准，DI-2 选 A）。任务清单：`tasks/scope-authority-defaults/todo.md`。分支 `claude/scope-authority-defaults`（从 main 开出，main 已含 0.0.27）。

## Overview

三个任务，各自先写失败的测试再改：授权默认打开（DI-1）、Claude 权限与旧规则清理（DI-2）、规则段措辞与文档（DI-3）。最后做一次最终验收。不升版本号（4 个模块做完再一起发版）。

## Architecture Decisions

- **默认值**：`onboard.join` 的参数默认改为 `checkpoint_authority=True`；`__main__` 的 join 子命令加 `--no-checkpoint-authority`（`store_false` 到同一个目标），`--checkpoint-authority` 保留为无操作。默认打开时，`Outcome.warnings` 加一行说明与关法。
- **授权一节**：只改 `_AUTHORITY` 的文字（授权、不授权两段），挂载方式不动。
- **权限**：`ROUTINE_ALLOW` 加 4 条，`ALWAYS_ASK` 去 2 条；新增常量 `RETIRED_ASK = ("Bash(npm install *)", "Bash(pip install *)")`。`Outcome` 加一个 `permissions_removed` 列表：预览列出设置文件 ask 里存在的这些原文，确认时只删它们；新函数和 `_merge_rules` 一样原子写入，不重排其他规则。
- **规则段**：只改 `_COMMON` 里「停滞询问与常规授权」一节的第二条，以及其他提到「联网安装依赖」算不可逆的地方（先用 grep 列全）。

## Task List

- **Task 1 授权默认打开**（Spec 验收 1、2）：
  - 先写测试（`tests/test_onboard.py`）：默认 join → 规则段有授权一节且含「Plan 列出的依赖」「官方源」「Plan 没列的新依赖」，名册 `checkpointAuthority` 为 true，预览 warnings 有说明与 `--no-checkpoint-authority`；`checkpoint_authority=False` → 没有这一节、名册无此键；CLI 两个开关各跑一次。原来用默认值（关）的测试按新默认值改写。
  - 验证：新测试先失败后通过。
- **Task 2 Claude 权限与旧规则清理**（Spec 验收 3、4）：
  - 先写测试：新接入的设置文件 allow 含 4 条新规则、ask 只有推送、`reset --hard`、`rm -rf`；设置文件已有旧的两条 ask 和一条用户自己的 ask 时，预览列出要删的两条，不确认不改文件，确认后只删这两条、用户那条和顺序保留。
  - 验证：新测试先失败后通过。
- **Task 3 规则段措辞与文档**（Spec 验收 5、6、7）：
  - 先写测试：规则段不再出现「联网安装依赖」列为不可逆，含「Plan 没列的依赖」「只问一次」「不送审」；`tests/test_packaging.py` 里 join 命令与 skill 的断言改为默认打开、提到 `--no-checkpoint-authority`。
  - 再改 `_COMMON`、`commands/join.md`、`skills/decision-inbox-join/SKILL.md`、README（接入一节、「检查点答复即授权」一条、升级一节写明要重跑接入）。
  - 验证：旧称扫描、全量测试通过。

## Checkpoint（gate）：模块最终验收

列出改动的文件、每条验收标准的证据和测试数，然后开 PR（base main）。

## 影响面

- 新接入的线默认带授权一节和新的 Claude 权限规则；
- 已接入的线重跑接入后才生效，重跑时会提议删旧的两条 ask 规则；
- 文档三处。

## 风险

| 风险 | 对策 |
|---|---|
| 默认打开授权让授权面变大 | 授权一节写清边界；预览开头提示，可一键关掉 |
| auto 模式下加新包不一定问 | 规则段明写先问、只问一次；Spec 关键决策 2 已接受 |
| 误删用户自己写的规则 | 只认两条原文；测试覆盖用户自己的 ask 规则保留不动 |
