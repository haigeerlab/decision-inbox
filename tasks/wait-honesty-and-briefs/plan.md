<!-- spec-guard: review approved -->
# Implementation Plan: wait-honesty-and-briefs

> 依据：`spec/wait-honesty-and-briefs.md`（已批准）。任务清单：`tasks/wait-honesty-and-briefs/todo.md`。

## Overview

先修主视图说假话的两处（A2、A3），再改事项规则（A7），然后是约定与停止钩子（B1），最后是约定块的文字类改动（B2、B5、邮箱派活）和版本。每个任务先写失败的测试，再实现到全绿，单独提交。

## Architecture Decisions

- **A2**：
  - hub-loop 的 `received` 记录从现在起加 `sender`。新增 `hub.later_from(g, sender, after_id) -> int | None`：先看 `received` 里带 `sender` 的记录，再补读事件日志里的 `hub.received`（`actor`、`data.relayId`），返回发送方在 `after_id` 之后最早一条消息的邮箱号。
  - `tickets.open_tickets` 的 `TicketView` 加 `maybe_stale`（那条消息的邮箱号或 None）。为了不让 tickets 依赖 hub，判断用的函数作为参数传入；只有调用方（health、view、hub）传入。
  - health 的信号 1 只数 `maybe_stale is None` 的单；view 的推送行同样过滤；「看等待」行尾加说明；计数行加「（其中 M 单可能已失效）」。
- **A3**：`health.assess`、`hub.main_view`、`view.render` 增加参数 `relay_status`（`"ok"`／`"absent"`／`"unreadable"`，默认按 `relay is None` 推断为 `"absent"`）。`__main__` 没给 `--agents` 时传 `"absent"`，给了但解析失败时传 `"unreadable"` 并带错误首行。`query` 的 `/item` 没给 `--status` 时写「本次没带」。
- **A7**：`items._receive_wait_user` 在没有任何取代或并行标记时，找同一发送方、同类（`multi` 相同）、状态 `pending` 的事项，排除写了【并行】的，按取代处理；`data` 加 `auto: true`；`ReceiveResult.hints` 加 `auto-superseded`。
- **B1**：`stophook.decide` 在原有判断之后、放行之前，读 spec-guard（复用 line-health 读进度的函数）。当前模块有未勾任务，且本会话没有开着的等待单、待答事项、已答未恢复事项时，拦一次。读不到时放行。
- **B2**：`protocol.parse` 给【等待用户】的「要点」做轻量检查，生成 `Issue("brief-thin", …)` 放进 hints（不进 problems）。约定块的示例要点改为 3 行。
- **B5、邮箱派活**：只改约定块常量。
- **版本**：两份 `plugin.json` 升到 0.0.6。

## 影响面

- 修改：`decision_inbox/hub.py`、`tickets.py`、`health.py`、`view.py`、`query.py`、`items.py`、`protocol.py`、`stophook.py`、`onboard.py`、`__main__.py`；`README.md`、两份 `plugin.json`；对应测试。
- 用户可见界面：主视图顶部和各线状态的措辞、「看等待」、计数行、回执提示、约定块文字、停止钩子说明。都由测试逐字核对。

## Task List

- [ ] Task 1：A2 等待单可能已失效（Spec 验收 1）
- [ ] Task 2：A3 区分没带、读不到、查不到（Spec 验收 2）
- [ ] Task 3：A7 新事项默认取代（Spec 验收 3）

### Checkpoint 1（report）

- [ ] 全部测试全绿

- [ ] Task 4：B1 约定硬规则与停止钩子检查（Spec 验收 4）
- [ ] Task 5：B2 要点写法与提示、B5、邮箱派活、README、版本 0.0.6（Spec 验收 5–8）

### Checkpoint 2（report）

- [ ] 全部测试全绿；scratchpad 临时协作组命令行跑一遍 A2、A3、A7、B2，记下输出；推送本分支

- [ ] Task 6：di-e2e 实测（Spec 验收 9）。先问用户

### Checkpoint 3（gate）：模块最终验收

- [ ] 全部测试全绿；9 条验收标准逐条有测试或实测记录；列出实际改动的文件；原样附上规格的改动差异
- [ ] 本 Plan 获批即授权：返工 wait-tickets、line-health、hub-view、query-commands、decision-queue、message-protocol、stop-hook、onboarding、hub-loop 的代码；版本升到 0.0.6；每个任务完成后本地提交并推送本分支；在 scratchpad 里建临时协作组
- [ ] 不授权：Task 6 的实测（到时另外问你）、开或合并 PR
