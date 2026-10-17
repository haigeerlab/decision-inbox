<!-- spec-guard: review approved -->
# Implementation Plan: relay-presence-and-doubt

> 依据：`spec/relay-presence-and-doubt.md`（已批准）。任务清单：`tasks/relay-presence-and-doubt/todo.md`。

## Overview

先让 relay-reader 读出 agent-relay 0.8 的三个新字段，再依次改各线状态与信号、送达存疑的显示、收件枢纽的 `alsoAnswers` 与约定块的 `withdraws`，最后是停止钩子说明、文档和版本。每个任务先写失败的测试，再实现到全绿，单独提交并推送。

## Architecture Decisions

- **字段（已对照 agent-relay 0.8.2 源码核对）**：
  - `bridge_agents` 的 `presence.activity`（`busy`／`idle`，只在 Claude 会话 `running` 时有）→ `AgentFact.activity`；
  - `bridge_agents` 的 `waiting.doubtfulIds`（编号列表，最多 20 个，可能没有）→ `AgentFact.doubtful_ids`；
  - `bridge_outbox` 条目与 `bridge_wake_status` 的 `wake.doubt`（`{reason, since}`）→ `MessageFact.wake_doubt`、`MessageStatusFact.wake_doubt`（布尔）。
- **干活中**：`health._is_working` 先看 `activity`：`busy` 为真，`idle` 为假；没有 `activity` 时照旧看最近活动时间。
- **信号 5 拆分**：`busy-backlog` 只在 `busy` 或没有 `activity` 时报；新增代码 `idle-backlog`（仍算信号 5）：「X 空闲，有 N 条消息没读」，建议「巡视会叫醒它；叫不醒就打开它」。
- **送达存疑**：新增信号 11 `delivery-doubt`，文字「X（Codex）有 N 条消息送达存疑（来源：agent-relay）」，建议「完全退出 ChatGPT 再打开 X 的任务」。巡视沿用 `ctx.notify`，键里带存疑编号，同一批只通知一次。`/item` 时间线里 `wake_doubt` 为真时写「已接受但没读到（送达存疑）」。
- **信号 1**：`assess` 没拿到 agent-relay 状态（`relay` 为 None）时不产生信号 1。
- **各线一行**：`_state` 选「阻塞：等谁」时跳过 `tickets.stale_tickets` 里的单；对方名在名册里有就写短名。
- **alsoAnswers**：`hub.reply` 生成发给提出方的【用户答复】时，从待答表找同一提出方、状态为被取代或已撤回、还没回复过（收件枢纽的 `outgoing` 里没有指向它的 `replyTo`、也没被放进过 `alsoAnswers`）的事项，把它们的邮箱号放进这条 send 的 `alsoAnswers`；放进去的编号记在 `outgoing` 里，避免下次重复。收件枢纽约定块第 3 步写明「有 `alsoAnswers` 就照填」。
- **withdraws**：开发线等角色的约定块「事项有效性标记」一条后加一句：取代或撤回自己的事项时，`bridge_send` 带 `withdraws: [旧那条的邮箱号]`。
- **停止钩子**：「已答未恢复」的拦截说明末尾加「如果你已经发过【已恢复】、收件枢纽还没收进，回一句『已发 #邮箱号』即可收工，不用重发」。
- **文档与版本**：需求记录第 13 节补「agent-relay 只读发件查询」的用例；README 两行；两份 `plugin.json` 升到 0.0.9。

## 影响面

- 修改：`decision_inbox/relay.py`、`health.py`、`view.py`、`query.py`、`patrol.py`、`hub.py`、`onboard.py`、`stophook.py`；`README.md`、`docs/requirements-record.md`、两份 `plugin.json`；对应测试。
- 用户可见界面：各线一行、异常区的两种新提示、巡视通知、`/item` 措辞、约定块与停止钩子文字。都由测试逐字核对。
- 最大风险：`alsoAnswers` 里有一个编号关不掉，agent-relay 会拒发整条答复。缓解：只放待答表里确认属于同一提出方、状态为被取代或撤回、从没回复过的编号；测试覆盖「别的会话的不放」「回复过的不放」「已放过的不重复放」。

## Task List

- [ ] Task 1：relay-reader 读出 activity、doubtfulIds、wake.doubt（Spec 验收 1、2 的数据部分）
- [ ] Task 2：干活中、信号 5 拆分、没带状态不报全线停住、各线一行说实话（Spec 验收 1、4、5）

### Checkpoint 1（report）

- [ ] 全部测试全绿

- [ ] Task 3：送达存疑的异常行、巡视通知、`/item` 措辞（Spec 验收 2）
- [ ] Task 4：收件枢纽 `alsoAnswers` 与约定块 `withdraws`（Spec 验收 3）
- [ ] Task 5：停止钩子说明、需求记录、README、版本 0.0.9（Spec 验收 6、7）

### Checkpoint 2（report）

- [ ] 全部测试全绿（含契约一致性测试）；scratchpad 临时协作组用手写的 `bridge_agents`、`bridge_outbox` 输出跑主视图与 `/item`，记下输出；推送本分支

- [ ] Task 6：实测 owesReplies 回落（Spec 验收 8）。先问用户

### Checkpoint 3（gate）：模块最终验收

- [ ] 全部测试全绿；8 条验收标准逐条有证据；列出实际改动的文件；规格有改动时原样附上差异
- [ ] 本 Plan 获批即授权：返工 relay-reader、line-health、hub-view、query-commands、patrol、hub-loop、onboarding、stop-hook 的代码；改 README 与需求记录；版本升到 0.0.9；每个任务完成后本地提交并推送本分支；在 scratchpad 里建临时协作组
- [ ] 不授权：Task 6 的实测（到时另外问你）；开或合并 PR；改契约仓库
