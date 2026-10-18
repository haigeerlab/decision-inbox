<!-- spec-guard: review approved -->
# Implementation Plan: transition-compat

> 依据：`spec/transition-compat.md`（用户 2026-10-18 批准）。任务清单：`tasks/transition-compat/todo.md`。分支 `claude/transition-compat`。

## Overview

六个任务，按风险从小到大排：契约升级 → 名册与 enroll → 输出旧写法 → 输入认旧编号 → 约定块 → 文档版本。每个任务先写失败的测试再改。

## Architecture Decisions

- **契约 v1.7**：从 `~/Documents/haigeerlab/session-protocol` 的 1e14a49 复制 `fixtures/`，放到 `tests/fixtures/session-protocol/v1.7/`，删掉 v1.5 目录。`test_contract.py` 里把 `VERSION` 改成 `"v1.7"`；`NOT_PARSED` 增加 `owner-handoff`；`user-reply/relay-*` 按文件名前缀跳过（新集合 `SKIPPED_FILES_PREFIX`）。跳过数断言改为 26，并加上「解析 63、生成 6」两个计数断言。
- **名册**：新增字段 `legacyFormat: bool`。`store._validate_session` 校验：只能是布尔值，只用于 dev 角色。
  - `onboard.enroll(group, relay_name, short_name, host, lines, desktop_session, confirm, now)` 只写名册（`_check_entry` 再加一笔，并记事件 `onboarding.enrolled`），不碰任何规则文件。命令行用 `onboard enroll`。
  - 正式接入时，`join` 本来就会替换整个条目，`legacyFormat` 跟着消失，不用改。
- **leave**：`_leave` 遇到「没有接入记录的文件，也没给 `--project`」时，如果这个条目带 `legacyFormat`，就不报错，只记 `left`。输出里 `out.file = None`，steps 写明「这个会话没有约定块，只从收件范围里移除」。
- **已退出**：新增 `store`（或 onboard）辅助函数 `left_relays(g)`，读 onboarding 状态里的 `left`。用在三处：
  - `hub._notices` 跳过已退出的会话，也跳过 `legacyFormat` 的会话；
  - `items._receive_wait_user` 校验多线「适用会话」时，已退出的会话按 `scope-session-unknown` 处理；
  - `items.answer` 多线发送时，跳过已退出的会话。
- **旧写法输出**：`protocol` 新增 `format_legacy_user_reply(item, relay_id, …)` 和 `format_legacy_multiline_replies(item, sender_relay, relay_id, …)`，首行和旧收件枢纽的实际写法一致，其余字段沿用正式写法的拼法（直接复用正式函数的输出，只替换首行）。`items.answer` 按收件人条目的 `legacyFormat` 选用哪种写法。
- **旧编号输入**：`items` 新增 `_resolve_own(doc, no, sender, legacy)`：先照旧按收件枢纽编号找；找不到、并且发件人是旧格式会话时，再按这个发件人自己还没答复的事项的 `relayId == no` 找。【取代】和【撤回】都走它。正式会话不改，继续按 v1.7 只认收件枢纽编号。退回说明和提示里写事项编号的地方，如果对方是旧格式会话，统一用 `_label(it)` 写成「#M（hub 编号 N）」。
- **约定块**：
  - `_OWNER` 里「你仍要按原来的路线转交」改成【负责人转交】的格式说明；
  - `_DEV`、`_COORDINATOR` 各加一条：收到【负责人转交】时要核对的三项。
  - doctor 会对所有已接入的会话报「约定块不是当前版本」，这是预期行为，README 升级一节写明。
- 版本 0.0.17。

## Task List

- [x] Task 1：契约升到 v1.7（Spec 验收 6）
- [x] Task 2：`legacyFormat` 字段、`onboard enroll`、leave 只登记的条目（Spec 验收 1、5 的 leave 部分）
- [x] Task 3：给旧格式会话输出旧写法；答复告知跳过旧格式和已退出的会话；多线事项跳过、退回已退出的会话（Spec 验收 2、3、5）
- [x] Task 4：认旧格式会话写的旧编号；退回说明写双编号（Spec 验收 4）
- [x] Task 5：约定块写明【负责人转交】（Spec 验收 7）
- [x] Task 6：文档和版本 0.0.17（Spec 验收 8）

### Checkpoint（gate）：模块最终验收

- [x] 全部测试通过；每条验收标准都有证据；列出实际改动的文件
- [x] 授权：Task 1–6 的代码、测试和文档；每个任务做完都提交，并推送 `claude/transition-compat`
- [x] 不授权：改用户配置、开 PR 或合并 PR、碰 LIVE-SAAS、改契约仓库
- [ ] 实测（Spec 验收 9）放到联合演练，开始前另问用户

## Risks

| 风险 | 预防 |
|---|---|
| 认旧编号时认错了别人的事项 | 只在发件人自己还没答复的事项里，按 `relayId` 找；正式会话不走这条路。测试覆盖「别人的邮箱号」和「已答复的事项」两种 |
| 复制过来的契约样例计数和契约负责人说的不一致 | 测试断言 63、6、26；对不上就停下来问契约负责人，不自己改断言 |
| 约定块改了以后，di-p0 测试组全部要重新接入 | 预期内，README 升级一节写明；联合演练前统一重跑 |
