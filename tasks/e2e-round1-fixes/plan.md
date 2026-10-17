<!-- spec-guard: review approved -->
# Implementation Plan: e2e-round1-fixes

> 依据：`spec/e2e-round1-fixes.md`（已批准）。任务清单：`tasks/e2e-round1-fixes/todo.md`。

## Overview

六处修复各自独立，按「先打通主流程，再补安全和可见性」排序：

1. 先修 F1 和 F2：开发线收得下答复，追问有退回。
2. 再做 F3：转来的话不当作答复。
3. 然后是 F4 巡视报警、F5 身份名、F6 卸载。
4. 最后改约定块、README、版本号和需求记录。

每个任务先写失败的测试，再实现到全绿，单独提交。实测交给 spec-guard-monitor 在原测试环境重跑。

## Architecture Decisions

- **F1**：
  - 三个 `format_*` 函数各加一个可选参数 `source_relay_id`。为 `None` 时正文和现在一字不差，旧测试不用改。
  - `items.py` 生成答复的两处传入事项的 `relayId`；`hub._notices` 也一样。
  - `protocol._item` 本来就只取「#」后的数字，括号里的内容只用测试锁住，不改实现。
- **F2**：
  - 在 `hub._dispatch` 处理未知消息的分支里判断：`m.expects_reply` 为真，或 `m.reply_to` 不为空。
  - 再查 `m.reply_to` 是不是收件枢纽自己发过的退回：在 hub-loop 的 `outgoing` 记录里，按 `kind == "return"` 和已记下的发送编号查。是就不退回。
  - 退回正文的第三行：用 `m.reply_to` 去事项的 `sent` 记录里反查事项号，取那个事项的 `relayId`。【答复告知】的发送编号在 hub-loop 的发送记录里，也一并查。
  - 退回用原有的 `_queue(..., "return", ...)` 入队，`replyTo` 填 `m.id`。
  - 未知消息原本就会在附注里记「X 称」。另在主视图的异常计数里加一：hub-view 读 hub-loop 状态里新增的 `returned` 计数，只计当天。
- **F3**：
  - `hub.reply` 加参数 `relayed_from`。有值时直接返回，不经过任何解析分支，只记事件 `hub.relayed-input`（`data` 带原话），回复文字固定。
  - `__main__` 的 `inbox reply` 加 `--relayed-from`。
  - 收件枢纽约定块的「用户每说一句话」之前，加一节「先判断是不是用户亲手输入」。
- **F4**：
  - 新增 `hub.patrol_alarm(g, now) -> str | None`：
    - 读 onboarding 记录的 `patrolTask`、`patrolTaskAt`，和 patrol 状态的 `lastRunAt`；
    - 阈值 15 分钟，写成模块常量。
  - 两处调用，都放在第一行：`main_view` 的 `head`，以及 `__main__` 的 `flow` 分支（打印在 `render_flow` 输出之前）。
  - `onboard.record_task` 多记 `patrolTaskAt`。
- **F5**：`tickets.receive` 里 `find_session(short_name=…)` 找不到时，再试 `find_session(relay_name=…)`。
- **F6**：
  - `_commit` 写规则文件前判断文件是否存在，不存在就在 onboarding 记录的 `created` 里记下这个路径。
  - `_leave` 在 `confirm` 时，如果 `after.strip() == ""` 并且路径在 `created` 里，就调 `_drop_created_rules(rules)`（唯一调用 `unlink` 的地方），同时把这个路径从 `created` 去掉；否则照旧写回。
  - 预览输出（`Outcome`）多一个标记 `drops`，命令行预览据此写「会删掉这个文件（接入时新建，现已为空）」。
  - `test_no_deletion_calls` 改成：只允许 `onboard.py` 里函数 `_drop_created_rules` 内部出现 `unlink`，其他文件、其他函数仍然禁止。

## 影响面

- 修改：
  - `decision_inbox/protocol.py`、`items.py`、`hub.py`、`tickets.py`、`onboard.py`、`__main__.py`、`view.py`（异常计数，若计数在那里渲染）；
  - `commands/hub-setup.md`、`README.md`、`docs/requirements-record.md`、两份 `plugin.json`；
  - 对应测试：`tests/test_protocol.py`、`test_items.py`、`test_hub.py`、`test_tickets.py`、`test_onboard.py`、`test_package.py`、`test_packaging.py`、`test_cli.py`（若命令行测试在那里）；
  - `spec/e2e-round1-fixes.md`：实测记录；`tasks/e2e-round1-fixes/todo.md`。
- 用户可见界面：答复正文、退回正文、转来提示、巡视报警、卸载预览、约定块。都由测试逐字核对；实测时由 spec-guard-monitor 在真实会话里看到。

## Task List

### Phase 1：打通主流程

- [x] Task 1：答复、多线答复、告知写原消息号（Spec 验收 1；F1 回归场景）
- [x] Task 2：开发线追问自动退回（Spec 验收 3、4；F2 回归场景）

### Checkpoint 1（report）

- [x] 全部测试全绿

### Phase 2：安全与可见性

- [x] Task 3：`inbox reply --relayed-from`（Spec 验收 5）
- [x] Task 4：巡视停摆报警，主视图和 /flow 都有（Spec 验收 7）
- [x] Task 5：「在等谁」认身份名（Spec 验收 9）
- [x] Task 6：卸载删掉空的新建规则文件，静态扫描开窄例外（Spec 验收 10）

### Checkpoint 2（report）

- [x] 全部测试全绿；在 scratchpad 临时协作组上用命令行跑一遍 S0：开发线抛事项、用户答复、开发线追问、转来的话、巡视超时、卸载，记下输出

### Phase 3：约定与文档

- [x] Task 7：约定块（共用的编号对应、收件枢纽只认亲手输入）、hub-setup 最后一步、README 三处、需求记录第 12 节第 12 项、版本 0.0.4（Spec 验收 2、6、8、11）

### Checkpoint 3（report）

- [x] 全部测试全绿；推送分支并开 PR（不合并），通知 spec-guard-monitor 可以重跑

### Phase 3b：重跑发现的 F10（用户 2026-10-17 追加）

- [x] Task 9：结束行认发送方自己的邮箱号，对不上时提示；约定块加一句；README 记 F9（Spec 验收 13、14）

- [x] Task 10：卡片加「推荐回复」一行、选项不截断、约定写明主视图不套代码块（F12；Spec 验收 15）

### Phase 4：实测

- [x] Task 8：spec-guard-monitor 在 di-e2e 重跑 S0（Spec 验收 12）。重跑由它主持，本会话只收结果，写进规格的实测记录

### Checkpoint 4（gate）：模块最终验收

- [x] 全部测试全绿；15 条验收标准逐条有测试或实测记录；列出实际改动的文件；原样附上规格的改动差异
- [x] 本 Plan 获批即授权：
  - 返工 hub-loop、decision-queue、message-protocol、wait-tickets、onboarding 的代码；
  - 静态扫描开一个窄例外；
  - 版本号升到 0.0.4；
  - 每个任务完成后在当前分支做一次本地提交；
  - 在 scratchpad 里建临时协作组；
  - Checkpoint 3 推送本分支、开 PR，并给 spec-guard-monitor 发一条「可以重跑」的会话消息；
  - Task 9、Task 10 做完后再推送，并请 spec-guard-monitor 重跑；
  - 返工 hub-view 的卡片格式（F12）。
- [x] 不授权：合并 PR、改 di-e2e 测试环境、替 spec-guard-monitor 重跑
