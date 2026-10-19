<!-- spec-guard: review pending -->

# Implementation Plan: proxied-session-note

> 依据：`spec/proxied-session-note.md`（用户 2026-10-19 批准）。任务清单：`tasks/proxied-session-note/todo.md`。分支 `claude/proxied-session-note`（从 main 开出，main 已含 host-permission-check）。

需要的外部条件：无（不装依赖、不联网；只用仓库已有的 `python3` 与测试）。

## Overview

一个任务，先写失败的测试再改：接入预览一行（只 Claude 会话）、规则段一条（三种角色）、README 两处。最后做一次最终验收。不升版本号。

## Architecture Decisions

- **接入预览**：`onboard.join` 在 go-to-session 那行说明之后，`host == "claude-desktop"` 时再加一行提醒；文字固定，测试逐字核对关键词。
- **规则段**：只改 `onboard._COMMON` 里「停在宿主确认上」一节，末尾加一条；三种角色共用这一节，不分别改。
- **README**：「使用注意事项」第 158 行补一句；升级一节在 R21 那段里补一句。

## Task List

- **Task 1 接入预览、规则段与 README**（Spec 验收 1–4）：
  - 先写测试：Claude 开发线、审查者、跨线协调接入时预览有这一行（含「亲手开的会话」「代开」「不弹确认」），Codex 开发线没有；三种角色规则段含「被别的会话开出来的」「不要直接执行」「去会话操作」「本会话由别的会话代开，先问规则可能不弹确认」；README 断言。
  - 再改 `onboard.py`、README；`tests/test_onboard.py` 里按提醒条数断言的地方，用现有的 `others()` 把这一行也排除掉。
  - 验证：新断言先失败后通过；旧称扫描、全量测试通过。

## Checkpoint（gate）：模块最终验收

列出改动的文件、每条验收标准的证据和测试数，然后开 PR（base main）。

## 影响面

- 接入预览多一行（Claude 会话）；协作规则段多一条，已接入的线重跑接入才生效。
- 不改权限规则，不写任何配置。

## 风险

| 风险 | 对策 |
|---|---|
| 会话判断不准自己是不是被代开 | 规则写明判断依据（开工说明的来源）；这是靠自觉的软约束，Spec 已写明，强制拦截等实测再定 |
