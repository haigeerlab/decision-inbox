<!-- spec-guard: review approved -->
# Implementation Plan: hub-loop

> 依据：`spec/hub-loop.md`（已批准）。任务清单：`tasks/hub-loop/todo.md`。

## Overview

先给 relay-reader 补 `parse_inbox`，再在 `decision_inbox/hub.py` 里依次做收件分发与去重、要发消息的留存与记账、用户输入的识别、约定块，最后接命令行并实测一轮。每个任务先写失败的测试，再实现到全绿，单独提交。

## Architecture Decisions

- **领域 `hub` 的结构**：`received`（处理过的 agent-relay 消息编号 → 时间、类型、是否退回）、`outgoing`（`out:<n>` → 收件人、replyTo、类型、关联事项、生成时间、发送编号或失败标记）、`nextOut`、`unknown`（认不出类型的消息编号 → 发件人与全文，供「N 原文」）。只有 `hub.py` 写它。
- **一次 `receive` 一个事务吗？** 不是。各模块的 `receive` 各自开事务；`hub` 每处理完一条，再开一个事务记 `received` 和要发的消息。中途出错时，已处理的消息已经记账，没处理的下次重交还会处理；同一条不会处理两次，因为先查 `received`。
- **正文文件**：写到 `<协作组目录>/outgoing/<n>.txt`，写入先落临时文件再改名；`sent` 发成后保留（协作组里的文件永久保留、不删）。
- **退回说明**：【等待用户】【撤回】用 decision-queue 的 `return_text`；其他类型按同样写法由 `hub.py` 生成（逐条列问题的中文说明，请补全后重发）。
- **`reply` 的识别**：一组按顺序匹配的整句正则；都不匹配才交给 `interpret_reply`。显示类分支直接调用 hub-view。
- **命令行**：沿用 `__main__.py` 的 argparse 写法，新增 `_inbox` 和 `_view`；`view` 的事实获取复用 `_assess` 的做法，读不到 agent-relay 时降级显示。

## 影响面

- 新增：`decision_inbox/hub.py`、`tests/test_hub.py`、`tests/fixtures/relay/inbox.json`、`tests/fixtures/relay/inbox-truncated.json`。
- 修改：
  - `decision_inbox/relay.py`、`tests/test_relay.py`：返工，加 `parse_inbox`；
  - `decision_inbox/__main__.py`：加 `inbox`、`view` 子命令和用法说明；
  - `spec/hub-loop.md`：Task 7 实测后补「实测记录」；
  - `tasks/hub-loop/todo.md`：勾选；
  - `.agent/state.json`：最终验收时切换当前模块。
- 用户可见界面：收件枢纽里显示的主视图和提示文字。由 Task 7 实测时在本会话里看到并记录。

## Task List

### Phase 1：收件

- [ ] Task 1：relay-reader 返工——`parse_inbox`（Spec 验收 3 的解析部分）
- [ ] Task 2：`hub.receive` 分发、去重、没读全与 `bridge` 通知（Spec 验收 1、2、3、4、5）

### Checkpoint 1（report）

- [ ] 全部测试全绿

### Phase 2：发送与用户输入

- [ ] Task 3：要发的消息留存与 `hub.sent`（Spec 验收 8、9 的状态部分）
- [ ] Task 4：`hub.reply` 的识别与答复（Spec 验收 6、7、9 的「重发」）
- [ ] Task 5：约定块 `hub.convention`（Spec 验收 11）
- [ ] Task 6：命令行 `inbox receive|reply|sent|convention` 与 `view`（Spec 验收 9 的退出码、10、12）

### Checkpoint 2（report）

- [ ] 全部测试全绿；在 scratchpad 的临时协作组上用样例文件跑一遍命令行，记下输出

### Phase 3：实测

- [ ] Task 7：实测一轮收件 → 答复 → 发送 → 记账 → 主视图（Spec 验收 13）。先问用户；用真实的 `bridge_inbox` 返回核对 `parse_inbox`，结果写进规格的实测记录

### Checkpoint 3（gate）：模块最终验收

- [ ] 全部测试全绿；13 条验收标准逐条有测试或实测记录；列出实际改动的文件；原样附上规格的改动差异（实测记录），批准本次验收即同时批准修订后的规格
- [ ] 本 Plan 获批即授权：
  - Task 1 的返工；
  - 每个任务完成后在当前分支做一次本地提交；
  - 在 scratchpad 里建临时协作组。
- [ ] 不授权：Task 7 的实测（到时另外问你）、推送、开 PR

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| `bridge_inbox` 的真实返回和源码读出的字段不一致 | 中 | 解析只依赖少数字段，缺字段时记警告并跳过那条；Task 7 用真实返回核对，不一致就回来改 |
| 处理到一半出错，消息被处理一半 | 中 | 每条消息处理完立即记 `received`；测试覆盖「中途出错后重交」 |
| 用户原话在写文件、读文件之间被改动 | 中 | 命令行按 UTF-8 原样读；测试用含换行、全角标点、引号的原话核对转发正文一字不差 |
| 实测给测试身份发消息影响真实会话 | 低 | 只用专门的测试身份和临时协作组；发之前先给你看内容 |

## Open Questions

无。
