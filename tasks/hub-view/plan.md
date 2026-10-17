<!-- spec-guard: review approved -->
# Implementation Plan: hub-view

> 依据：`spec/hub-view.md`（已批准）。任务清单：`tasks/hub-view/todo.md`。

## Overview

先补齐上游模块缺的三项数据（返工），再按「零件 → 卡片 → 主视图 → 展开视图」的顺序实现。每个任务先写失败的测试，再实现到全绿，单独提交。代码在 `decision_inbox/view.py`。

## 上游数据缺口（需要返工已完成模块，请重点审）

对照已完成模块的代码，规格里要显示的三项数据现在拿不到：

| 缺口 | 现状 | 补法 |
|---|---|---|
| 1. 「等你确认」卡片要的 detail | agent-relay 的 `presence.detail` 有值（样例里是 `permission prompt`），但 relay-reader 的 `AgentFact` 没有解析这个字段 | relay-reader：`AgentFact` 加 `presence_detail: str \| None`，取 `presence.detail`，空串记为 None |
| 2. 「⚠ 未标审查」下的「正文提到：」 | review-registry 的 `ReviewLabel.mentions` 有值，但 decision-queue 收单时只存了 text、warn、highlight、ref，没存 mentions | decision-queue：收单时把 `mentions` 一起存进事项的 `review`；旧记录没有这个字段时按空处理 |
| 3. 详情、刚转达、失效的数据 | decision-queue 只有 `pending`（待答）和 `history`（事件）两个读取函数；规格要求本模块「不另读状态文件」 | decision-queue：加 `get(g, item)`（按编号取一个事项，没有返回 None）和 `by_status(g, *statuses)`（按状态列出，按编号排序） |

这三处都只加字段或加只读函数，不改已有行为。做完后把对应接口补进 `spec/relay-reader.md`、`spec/decision-queue.md`，在最终验收时一起给你复审。

## Architecture Decisions

- 入口按规格的 5 个函数。主视图内部分 6 段各自生成文字，再按固定顺序拼接：第一行推送、各线、总览、异常、卡片、最后一行计数。段与段之间空一行，没有内容的段（推送、异常、卡片）整段省略。
- 「各线」按名册顺序，跳过收件枢纽。短名一律从 group-store 名册取，找不到时用身份名。
- 「等你决定 N 项」= 待答事项数 + 状态为「等你确认」的会话数。「异常 N」= 异常区实际列出的行数，**不含信号 1**（与样例一致：样例有全线停住，异常写 1）。
- 「刚转达」：取状态为已转达、已取走、已确认的事项，用 `statusAt.forwarded` 判断是否在 10 分钟内；多个事项用「、」分隔，按转达时间排序；一个事项转给多个会话时，会话短名用「＋」连接，例如 `9 → 前端＋API`。
- 信号 1 的「卡在 X」：统计开着的等待单里每个被等方被等了几次，选次数最多、且自己没有开着的等待单的那个；最多的有两个以上并列、或者都在等别人时，写「卡在哪见 /flow」。N 取这些等待单里等得最久的分钟数。
- 异常行：说明一律用 line-health 给的原文。信号 2 例外：line-health 的原文带括号补充（「（API 在等 前端）」），按样例的写法由本模块用信号里的两个会话重新组句，不带括号。
- 「等你确认」卡片的「N 分钟前」取 `presence_since`；没有这个时间时标题不写时间段。多张时按名册顺序。
- 时间一律转绝对时间算，分钟向下取整；时间写法：不到 60 分钟写分钟，不到 24 小时写小时（向下取整），满 24 小时写天。

## 影响面

- 新增：`decision_inbox/view.py`、`tests/test_view.py`。
- 修改（返工）：`decision_inbox/relay.py`、`decision_inbox/items.py`，及其测试 `tests/test_relay.py`、`tests/test_items.py`；`spec/relay-reader.md`、`spec/decision-queue.md` 补接口（需复审）。
- 修改：`tasks/hub-view/todo.md`（勾选）、`.agent/state.json`（最终验收时切换当前模块）。
- 用户可见界面：本模块输出的是收件枢纽会话里显示的 Markdown 文字，没有网页。界面验证方式：把完整样例的输出写到临时文件，在对话里贴出渲染效果给你看；Claude 桌面版里的实际复制按钮要等 onboarding 接上收件枢纽后才能看，到时记为「UI 未验证」并说明原因。

## Task List

### Phase 1：上游数据与零件

- [ ] Task 1：返工——补 detail、mentions、两个读取函数（上表三项）
- [ ] Task 2：零件——时间写法、截断、复制块、第一行推送、「各线」、总览、最后一行计数（Spec 验收 1、3、7、8）

### Checkpoint 1（report）

- [ ] 全部测试全绿

### Phase 2：卡片与主视图

- [ ] Task 3：两种卡片与审查行（Spec 验收 4、5、6）
- [ ] Task 4：异常区与完整主视图（Spec 验收 2、9、11）
- [ ] Task 5：4 种展开视图（Spec 验收 10）

### Checkpoint 2（gate）：模块最终验收

- [ ] 全部测试全绿；11 条验收标准逐条对应测试；贴出完整样例的输出；列出实际改动的文件；给出 relay-reader、decision-queue 两份规格的修订内容供复审
- [ ] 本 Plan 获批即授权：Task 1 的返工；每个任务完成后在当前分支做一次本地提交。不授权推送、不授权开 PR；两份上游规格的修订要另行复审

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| 样例逐字比对容易因空行、全角符号出错 | 中 | 期望文本写成测试里的一整段常量，失败时用 `assertMultiLineEqual` 显示差异 |
| 返工改动影响已完成模块 | 低 | 只加字段和只读函数；先跑这两个模块的原有测试确认不变，再加新测试 |
| 展开视图的格式规格只写了内容，没写排版 | 低 | 按下面 todo 里写的每行格式实现；验收时给你看实际输出，不满意再改 |

## Open Questions

无。上面的返工和几条细节写法随本 Plan 一并审。
