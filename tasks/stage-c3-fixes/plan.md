<!-- spec-guard: review approved -->

# Implementation Plan: stage-c3-fixes

> 依据：`spec/stage-c3-fixes.md`。任务清单：`tasks/stage-c3-fixes/todo.md`。分支 `claude/v0037`（基线 b58f3e1，建在 `claude/di11-patrol-trigger` 上，用户 2026-10-22 批准）。

需要的外部条件：无。

## 架构决定

- **I-20 不带编号的回复**：
  - 在 `items.interpret_reply` 里，不带编号、靠「只剩一项待答」认出来的那一段，按带编号时的同一套规则处理：先用 `_LETTER_RE` 识别选项字母，认不出又不是「原话：」开头的，就返回 `NO_ITEM_QUESTION`。
  - 没有选项的事项照旧收下整句。
- **I-20 重答替换**：
  - `items.interpret_reply` 遇到 `ANSWERED` 状态的事项时，先问 `hub` 层这个事项最近一次答复是否已经发出。为免 items 依赖 hub，由 `items` 自己判断：`it["sent"]` 为空就算没发出（`hub.sent` 成功时会调用 `items.record_sent` 写入 `sent`）。
  - 没发出的，允许这一段作为新答复。`items.answer` 在事项已转达、但 `sent` 为空时，用新答复覆盖最后一条，并记事件 `items.answer-replaced`。
  - `hub._queue_answers` 排队前删掉这一项还没发出的旧发件记录，记事件 `hub.dropped`。
- **I-20「撤下 N」**：
  - `hub.reply` 识别 `^撤下\s*#?(\d+)$`，调用新函数 `items.retract(g, no, at)`：`sent` 为空时，状态回到 `pending`，清掉 `answers` 和 `statusAt.forwarded`，记 `items.retracted`；已发出的返回 False。
  - hub 同时删掉这一项还没发出的发件记录。
  - `_COMMAND_LIKE_RE`、`COMMANDS` 和规则段第 5 步的指令清单都加上「撤下」。
  - `unsent_rows` 和 `sent_summary` 里答复类的那一行改成三种说法并列。
- **I-21**：`stall._work_start(m, f, raised=None)` 多一个候选，类型记为 `"raise"`，文案是「你 <时间> 抛出问题后 N 小时没有新提交」（实际上抛出后有未结项事项时这个候选最晚，也就不会判停住）。
  - `_module_findings` 从 `items` 里取同一模块协调、`module` 等于该模块、状态不在 `FINAL` 里的事项，取最晚的 `receivedAt` 传入。
  - 普通开发线在 `_findings` 里：`state.since` 早于这条线最近一次未结项事项的抛出时间时，不判停住。
- **I-22**：
  - `stophook.hub_turn_check(payload, pending=None)`：`output is None` 且 `pending` 非空时，用 `(?<![0-9A-Za-z])#(\d+)(?!\d)` 找回复里的编号，有落在 `pending` 里的就拦一次。
  - `__main__._hook` 在 `is_hub` 时读这个组的待答编号（`items.pending`，去掉去会话操作类）传进去。
  - 调查分支带来的 `HubTurnWithoutViewTest` 两条测试已经用 `pending=` 关键字，不用改。
- **小事 1**：`onboard watch <组> --remove [--confirm]` 调 `watch.uninstall`，打印要删的 plist 路径或「没有装巡视提醒」。
- **小事 2**：`onboard.join` 在 `confirm` 之前比较 `store.find_session(g, relay_name)` 的 `shortName`，变了就往 `out.warnings` 开头插一行。

## 任务清单

- **Task 1 I-20 不带编号的回复**（Spec 假设 1；验收 1）
  - `UnsentAnswerTest.test_unnumbered_chat_is_not_an_answer`（已在调查分支，改前失败）。
  - 另在 `tests/test_items.py` 加：只剩一项有选项的事项时「B」「原话：…」照收，闲话追问；没有选项的事项照旧收下整句。
  - 现有的 `TolerantReplyTest` 等解析用例不改。
- **Task 2 I-20 重答替换与「撤下 N」**（假设 2、3；验收 2、3）
  - `UnsentAnswerTest` 另外三条（已在调查分支，改前失败）。
  - 补一条：答复还没发（没跑 `inbox sent`，不是失败）时重答也能替换。
  - 补一条：规则段第 5 步有「撤下 N」。
  - 补一条：`COMMANDS` 提示里有「撤下」。
- **Task 3 I-21 停滞起点**（假设 4；验收 4）
  - `RaisedItemStallTest`（已在调查分支，1 条改前失败）。
  - 补普通开发线的对应用例：线停住，但它刚抛的事项还没结，不问。
- **Task 4 I-22 没贴卡片也拦**（假设 5；验收 5）
  - `HubTurnWithoutViewTest` 两条（已在调查分支）。
  - 补一条：回复提到的事项不是待答状态时放行。
  - 补一条命令行用例：`hook stop` 在收件箱目录，组里 #1 待答，会话记录这一轮没跑 view、回复写「#1」时，出 block。
- **Task 5 两件小事与 README 排查行**（假设 6、7；验收 6、7）
  - `tests/test_onboard.py`：`watch --remove` 的预览不改文件，`--confirm` 后 plist 没了，没装时提示「没有装」；join 改线名时提示，不改时不提示。
  - README 排查表加「误收的答复」一行。
  - 全量测试通过。

## Checkpoint（gate）：模块最终验收

- 列出实际改动的文件（新增、修改与行数，取自版本库）和测试数。
- 在临时组重放三件事：
  - I-20：只剩 #78 时「dev codex 应该在线了」被追问；模拟发送失败后「撤下 78」和「78 B」都能用。
  - I-21：kappa 抛了 #84 后不再被问停滞。
  - I-22：用 #79 那一轮的会话记录跑停止检查，被拦。
- 批准后接着写 protocol-contract-v2-6 的 Plan；两个模块做完一起开 PR，版本号在那个模块里升。
- 不改界面，不做 UI 自验（主视图是命令输出，用重放对照）。

## 风险

| 风险 | 对策 |
|---|---|
| 不带编号的回复收紧后，现有测试里依赖「只剩一项就收」的用例变红 | 先跑全量，看依赖的用例是否带选项字母；按 Spec 改的列在交付里 |
| `sent` 字段在旧数据里可能不全（0.0.30 以前） | 只有 `sent` 为空且状态是已转达时才允许替换或撤下；旧数据里真发出过的，发件记录里有邮箱号，hub 层再核一遍 |
| I-22 误拦 | 只在本轮没出主视图、回复写了「#数字」、数字恰好是待答事项时才拦，有测试覆盖放行的情况 |

## 未决问题

- 无。
