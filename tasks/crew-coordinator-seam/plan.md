<!-- spec-guard: review approved -->
# Implementation Plan: crew-coordinator-seam

> 依据：`spec/crew-coordinator-seam.md`（用户 2026-10-18 批准）。任务清单：`tasks/crew-coordinator-seam/todo.md`。分支 `claude/livesaas-seam`。

## Overview

一共四个任务，按风险从小到大排：先改停止钩子（只是让它少拦），再加标记，再加写入 CLAUDE.local.md，最后改文档、升版本。每个任务都先写会失败的测试，再改代码。

## Architecture Decisions

- **名册字段**：`crewCoordinator: true`、`localRules: true`，都是可选字段。`store._validate_session` 校验三点：只能是布尔值；`crewCoordinator` 只能用在 dev 角色上；`localRules` 只能用在 `claude-desktop` 宿主上。没有这两个字段的旧名册照常能读。
- **停止钩子** `stophook._silent_stop`：
  - 当前模块 `m.status == "suspended"` 时返回 None，对所有开发线都生效；
  - 名册条目带 `crewCoordinator` 时，在调用 `_silent_stop` 之前直接返回 None；
  - 「有人在等」和「已答复未恢复」这两项检查在 `decide` 里照旧，不受影响。
- **约定块**：`onboard.block(role, group, hub, checkpoint_authority=False, crew_coordinator=False)`。为真时，在 `_ROLE_RULES["dev"]` 后面拼上 `_CREW_COORDINATOR` 这一节（内容见 Spec「要做的」第 2 条）。doctor 生成期望约定块时，从名册条目读这两个开关传进去。
- **规则文件路径**：新增 `onboard.rules_path(entry, project)`，`localRules` 为真时用 `CLAUDE.local.md`，否则用 `RULES_FILES[host]`。`join`、`_leave`（带 `--project` 时也走这里）共用它。
- **忽略规则**：
  - 用 `git -C <项目> rev-parse --git-common-dir` 找到 git 公共目录；
  - 用 `git -C <项目> check-ignore -q CLAUDE.local.md` 判断这个文件是否已被忽略，返回 0 表示已忽略；
  - 没被忽略时，在预览的 steps 里写明要做的事；确认时往 `<common>/info/exclude` 追加一行 `CLAUDE.local.md`（已经有这一行就不追加），并在 onboarding 状态的 `excludeAdded[<relay>]` 里记下文件路径；
  - `_leave` 时，只有当 `excludeAdded` 里记过这个会话时，才删掉那一行；
  - 不是 git 仓库时跳过，不做任何处理。
- **AGENTS.md 警告**：`localRules` 为真，项目目录有 `AGENTS.md`、没有 `CLAUDE.md` 时，往 `out.warnings` 里加一条。
- 版本 0.0.16。两份 `plugin.json` 和打包测试都要改。

## Task List

- [x] Task 1：停止钩子跳过已挂起的模块，并给协调会话开例外（Spec 验收 4；联合测试 T9 ①②②′④）
- [x] Task 2：`--crew-coordinator` 标记和约定块里的新一节（Spec 验收 3）
- [x] Task 3：`--local-rules`：写进 CLAUDE.local.md，处理忽略规则，加 AGENTS.md 警告（Spec 验收 1、2）
- [x] Task 4：文档和版本 0.0.16（Spec 验收 5）

### Checkpoint（gate）：模块最终验收

- [x] 全部测试通过；验收标准每一条都有证据；列出实际改动的文件
- [x] 授权范围：Task 1–4 的代码、测试、文档；每个任务完成后提交并推送 `claude/livesaas-seam`
- [x] 不授权：改用户配置、开 PR 或合并 PR、碰 LIVE-SAAS
- [ ] 实测（Spec 验收 6）放到联合演练阶段，开始前另问用户

## Risks

| 风险 | 预防 |
|---|---|
| 改停止钩子后漏拦 | 测试覆盖「普通开发线没勾完照常拦」和「协调会话有人在等照常拦」 |
| `info/exclude` 写坏或删错 | 只追加、只删本插件记过的那一行；用临时 git 仓库实测追加、重复追加、删除三种情况 |
| 旧名册里没有新字段 | 字段缺省按 False 处理；用旧名册样例回归 |
