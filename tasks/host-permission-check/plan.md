<!-- spec-guard: review pending -->

# Implementation Plan: host-permission-check

> 依据：`spec/host-permission-check.md`（用户 2026-10-19 批准）。任务清单：`tasks/host-permission-check/todo.md`。分支 `claude/host-permission-check`（从 main 开出，main 已含 go-to-session）。

需要的外部条件：无（不装依赖、不联网；只用仓库已有的 `python3` 与测试）。

## Overview

三个任务，各自先写失败的测试再改：读宿主事实与 Plan 需要（纯函数）、doctor 的「宿主权限」一项、接入预览与文档。最后做一次最终验收。不升版本号。

## Architecture Decisions

- **`decision_inbox/hostperm.py`**（新，只读）：
  - `codex_facts(repo, config_path)` → 可写／可联网／受信任，以及每项的来源；按行读全局配置（复用 doctor 的手工读法，抽成小函数），项目 `.codex/config.toml` 只在受信任时算数；读不到或看不懂返回「未知」和原因。
  - `claude_facts(repo)` → 有没有放行安装规则、有没有旧的先问规则。
  - `plan_needs(repo, module)` → `"none" | "needs" | "unknown"`：认一行字段与小节标题两种写法。
  - `compare(entry, facts, needs)` → 状态（ok／bad／unknown）、事实文字、A／B 两个选项文字。
- **doctor**：每条开发线（`role == "dev"`、有 repo、没退出）加一项 `Check("宿主权限：<线名>", …)`；当前模块用 `specguard.read_line(repo)` 的 `active_module`，读不到按「unknown」。
- **接入预览**：`onboard.join` 对开发线调一次 `compare`，状态为 bad 时 warnings 加一行。
- 测试用临时目录造配置文件，环境变量 `DECISION_INBOX_CODEX_CONFIG` 指向临时全局配置（doctor 已有这个口子）。

## Task List

- **Task 1 读宿主事实与 Plan 需要**（Spec 验收 1–6 的判断部分）：先写 `tests/test_hostperm.py`：Codex 全局关联网＋无项目配置、受信任项目配置开联网、未受信任同样配置、全局开联网、`danger-full-access`、`read-only`；Claude 有／无放行、有旧先问；Plan 一行写法、小节写法、「无」、没写、没有文件；读不到或看不懂。再写 `hostperm.py`。验证：先失败后通过；所有配置文件读前读后逐字相同。
- **Task 2 doctor 的「宿主权限」一项**（Spec 验收 1–6 的展示部分）：先写 `tests/test_doctor.py` 的用例：✘ 含 A、B 两个选项与「没实测」说明，✔ 写事实，「没法对照」不计异常，「?」写原因；只对开发线。再改 `doctor.py`。验证：先失败后通过；doctor 原有测试不变。
- **Task 3 接入预览与文档**（Spec 验收 7、8）：先写测试：Codex 开发线接入时对不上有一行 ⚠（含 A、B）；对得上没有。再改 `onboard.py`、README。实跑：本分支代码对本机 di-p0 跑一次 doctor，看「宿主权限」各项（只读）。验证：旧称扫描、全量测试通过。

## Checkpoint（gate）：模块最终验收

列出改动的文件、每条验收标准的证据和测试数，然后开 PR（base main）。

## 影响面

- doctor 多出每条开发线一项；接入预览多一行提醒。
- 不改协作规则段，已接入的线不用重新接入；不写任何配置。

## 风险

| 风险 | 对策 |
|---|---|
| 手工读 TOML 认错（多行值、内联表） | 只认本插件要的几个键的简单写法；认不出就记「未知」，不猜 |
| Codex 桌面应用的配置加载与 CLI 不同 | 改法 A 注明没实测；不据此判断「能联网」以外的事 |
| 读 Plan 文件越出本插件边界 | 只找这一项；spec-guard 在 JSON 给出后改读那里 |
