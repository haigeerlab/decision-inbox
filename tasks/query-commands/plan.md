<!-- spec-guard: review approved -->
# Implementation Plan: query-commands

> 依据：`spec/query-commands.md`（已批准）。任务清单：`tasks/query-commands/todo.md`。

## Overview

先做 relay-reader 的返工，并用真实采集的样例核对字段；再依次做 `/lines`、`/flow`（先找源头和归类，再做检查明细）、`/item`，最后接命令行。每个任务先写失败的测试，再实现到全绿，单独提交。代码在 `decision_inbox/query.py`。

## Architecture Decisions

- 「谁在等谁」的图只建一次（内部函数 `_wait_graph`），`/lines` 的「在等」、`/flow` 的源头和等待链都用它。数据来自 `tickets.open_tickets`：等待方和被等方都要能对上名册；等用户的单不进图，但 `/lines` 会写「你（#N）」。
- 找环用深度优先搜索。只报第一个找到的环，环上的会话按名册顺序写。
- 源头归类写成一张有序的规则表：每条规则一个判断函数加一段文字模板，按顺序取第一个符合的。新增分类只需在表里加一行。
- 「被它挡住」按等待图反向走，直接和间接等它的会话都算；括号里的单号，取这个会话等向源头方向的那张等待单。
- 复制块和时间写法直接用 hub-view 的 `copy_line`、`ago`，不另写一份。
- 命令行只做三件事：读文件、调用解析和渲染函数、打印。出错时打印中文原因，按规格的退出码返回。
- 「查询前后协作组文件逐字节不变」用测试验证：查询前后各对协作组目录里的所有文件算一次哈希，比较两次结果。

## 影响面

- 新增：`decision_inbox/query.py`、`tests/test_query.py`、`tests/fixtures/relay/` 下的 wake_status 样例（合成一份、实采脱敏一份）。
- 修改（返工）：`decision_inbox/relay.py`、`tests/test_relay.py`；`spec/relay-reader.md` 补接口（需复审）。
- 修改：`decision_inbox/__main__.py`（加 `query` 子命令），`tests/test_package.py`（只在要补命令行测试时改）。
- 修改：`tasks/query-commands/todo.md`（勾选）、`.agent/state.json`（最终验收时切换当前模块）。
- 用户可见界面：输出的是收件枢纽里显示的 Markdown 文字。和 hub-view 一样，桌面版里的实际显示要等 onboarding 接上后才能看。验收时会贴出三个查询的样例输出，桌面版显示记为「UI 未验证」。

## Task List

### Phase 1：数据与一览

- [ ] Task 1：relay-reader 返工——`parse_message_status`、`parse_wake_jobs`，加合成样例；实采一次 `bridge_wake_status`，脱敏后存为夹具（Spec 验收 10）
- [ ] Task 2：等待图与 `/lines`（Spec 验收 1）

### Checkpoint 1（report）

- [ ] 全部测试全绿；实采样例与源码的字段一致，不一致的地方记进 todo，并在最终验收时报告

### Phase 2：体检与追溯

- [ ] Task 3：`/flow` 的源头选择与 10 类归类、结论段（Spec 验收 2、3、4、5）
- [ ] Task 4：`/flow` 的 5 项检查明细（Spec 验收 6）
- [ ] Task 5：`/item`——`item_message_ids` 与时间线（Spec 验收 7、8、9）
- [ ] Task 6：命令行 `query` 的 4 个子命令与只读校验（Spec 验收 11、12）

### Checkpoint 2（gate）：模块最终验收

- [ ] 全部测试全绿；12 条验收标准逐条对应测试；贴出三个查询的样例输出；列出实际改动的文件；给出 relay-reader 规格的修订内容供复审
- [ ] 本 Plan 获批即授权：
  - Task 1 的返工；
  - 只读调用 `bridge_wake_status` 两次（不带参数一次、带一个消息编号一次），采集样例，脱敏后提交为夹具；
  - 每个任务完成后在当前分支做一次本地提交。
  - 不授权：推送、开 PR。relay-reader 规格的修订要另行复审。

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| 0.6.10 的 `bridge_wake_status` 字段和 0.6.1 源码不一致 | 中 | Task 1 先实采再定解析；不一致时以实采为准，改规格前先问你 |
| 实采样例含消息正文预览或真实会话名 | 中 | 提交前删掉 `preview` 等字段并替换会话名；测试扫描夹具里没有 `preview` |
| 收件枢纽没有自己的身份时，按编号查状态会被拒（只许发件人或收件人查） | 低 | 采集时用本会话已有的身份查一条它自己发过的消息；查不到如实记录，不绕过 |
| 源头归类规则互相遮蔽 | 中 | 每类一个最小场景，另有「同时满足两类」的用例锁定规则顺序 |

## Open Questions

无。
