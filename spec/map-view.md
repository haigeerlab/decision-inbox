<!-- spec-guard: review approved e67c52a7990e -->
# Spec: map-view

> 能力图模块 `map-view`。需求来源：`docs/requirements-record.md` 第 7.1 节 `/map` 与「按 spec-guard 实际接口调整」5 条、状态词表、折叠规则，第 13.1 节第 1 行。
> 接口依据：spec-guard-reader 的 `LineMap`、`ModuleFact`；本机 spec-guard 0.63.1 的 `map_view.py` 文字输出（作为排版参照）。

## 目标

给用户三个只读查询，看一条线或全部线的能力图进度：

- `/map <线>`：这条线的模块表，按折叠规则只展开要看的部分。
- `/map <线> 全部`：展开所有模块。
- `/map all`：每条线只显示一行总数，早上第一眼看全局。

模块状态、进度、依赖、挂起、「挡住 N 个」、评审标记、未推送，全部来自 spec-guard（经 spec-guard-reader），本模块不改它给的任何状态。本模块只叠加自己的数据：
- 「架构审查」列（review-registry）；
- 「等你决定」的事项（decision-queue）；
- 外部等待（wait-tickets）。

## 已定事项（用户 2026-10-16 确认）

1. **「架构审查」按模块填，靠【审查结论】新加的可选字段「模块」**：
   - message-protocol 返工：【审查结论】加可选字段「模块：<模块编号>」。
   - review-registry 返工：记下每个审查编号对应的模块，并提供按模块读取的函数。
   - onboarding 的约定块要求负责人写这个字段（记给 onboarding）。
   - 没写模块的审查，在该线表头汇总为「未标模块的审查 N 个」。
2. **备注里的「由别的线负责」「剩余要点」第一版不写**：现在没有数据来源。等 spec-guard 在能力图里提供了，再向它提需求接入。
3. **外部等待写在当前模块的备注里**：这条线有开着的等待单、等的不是用户时，写进 spec-guard 给的当前模块那一行的备注。没有当前模块时写在表头。

## 关键决策与取舍（请重点审）

1. **自己排版，不用 spec-guard 的文字表**：spec-guard 的 `map_view.py` 自己也能输出表格，但只有一列「审查」，也不能加列。所以本模块读它的 JSON（`--json`），按下面的格式排版。表头和折叠写法尽量和 spec-guard 的文字表一致，用户在两边看到的是同一张表。
2. **列**：`| 位 | 编号 | 作用 | 状态 | Spec/Plan 评审 | 架构审查 | 备注 |`。两种审查分两列，列名固定，不共用「审查」一词（需求第 7.1 节调整第 1 条）。
3. **状态列（图标 + 原因，原因来自 spec-guard 的字段）**：

   | spec-guard 状态 | 写法 |
   |---|---|
   | done | `✅ 已完成` |
   | in_progress | `🔨 写 Spec`、`🔨 写 Plan`，或 `🔨 进行中 6/11`（step 为 build 时） |
   | suspended | `⏸ 挂起：<suspendedReason 或「未记原因」> · 挡住 N 个` |
   | blocked | `⛔ 阻塞：等 <blockedOn 用「、」连接>` |
   | ready | `🟢 可以开始` |
   | not_ready | `○ 未就绪：缺 <missingDeps 用「、」连接>` |

   「挡住 N 个」= spec-guard 给的 `blocks` 的个数，按 spec-guard 的契约已含间接被挡的。
4. **Spec/Plan 评审列**：`Spec <标记> Plan <标记>`。标记取 spec-guard 的评审状态：approved 写 ✔、pending 写「待审」、revised 写「已改待复审」、invalid 写「标记无效」、none 写「—」。
5. **架构审查列**：这个模块每个审查编号最近一轮的结论，按节点写，多个用「 · 」连接，例如 `Spec 通过 · Plan 有须修改项（第 2 轮）`。
   - 结论写法：通过、通过，附建议N条、有须修改项（第 N 轮）。
   - 没有结论写「—」。
   - 这条线没有登记审查者时，表头写「架构审查：本线无审查者」，列里一律「—」。
6. **表头 3 到 4 行**：
   ```text
   前端 · 14 个模块 · ✅ 10 🔨 1 ⏸ 0 ⛔ 0 🟢 2 ○ 1 · 更新于 18:37
   关键卡点：pay 挂起 → 挡住 3 个模块 · 等你决定：#12、#15
   未合入主线：91 个提交（相对 origin/main）；未推送：判断不了
   架构审查：未标模块的审查 1 个
   ```
   - 第 1 行：线的短名、模块总数、各状态个数（取 spec-guard 的 `totals`）、`generatedAt` 的本机时间。
   - 第 2 行「关键卡点」：每个 bottleneck 写「<编号> 挂起 → 挡住 N 个模块」，用「；」连接，没有写「无」。「等你决定」：这条线发起的待答事项，加上「适用会话」包含这条线的多线事项，没有就不写这一段。
   - 第 3 行：未合入、未推送照 spec-guard 的 `head` 写，null 写「判断不了」（需求第 7.1 节调整第 4 条）。
   - 第 4 行：没有当前模块时的外部等待、未标模块的审查、本线无审查者。三样都没有就不写这一行。
7. **折叠**（需求第 7.1 节折叠规则）：
   - 默认展开：进行中、挂起、阻塞、可以开始，以及最近完成的 1 个模块。「最近完成」取 `lastTickAt` 最晚的已完成模块，都没有时取位次最大的。
   - 其余已完成的合并成一行 `| 1–9 | 其余 9 个已完成 | | ✅ | | | |`，未就绪的合并成一行 `| 14 | 1 个未就绪 | | ○ | | | |`。「位」写成合并模块的最小位次–最大位次，只有一个时写一个数。
   - `全部`：每个模块一行，不合并。
   - 作用列超过 40 个字截断加「…」（spec-guard 的文字表也截断）。
8. **`/map all`**：每条开发线一行，写第 1 行的总数；能力图读不出的线写「<短名> · <spec-guard-reader 给的原因>」，例如「后台 · 无能力图」。按名册顺序。
9. **选线**：`<线>` 按名册的短名或身份名匹配开发线。对不上时写「没有叫「X」的线，现有：前端、API、后台」。
10. **读不出能力图**：整张表换成一行「<短名> · <原因>」。如果这条线有待答事项或外部等待，照样在下面列出（需求第 7.1 节：「没用 spec-guard 的线只显示邮箱里的数据，并注明无能力图」）。
11. **命令行**：spec-guard-reader 能直接读各线仓库，本模块不需要 MCP 工具的数据，所以命令行一步就够：
    ```bash
    python3 -m decision_inbox map <协作组> <线|all> [全部]
    ```
    退出码：0 成功（包括「对不上线」和「读不出能力图」，这些照实打印）；2 参数错误或协作组不存在。

## 范围

**范围内**

- message-protocol 返工：【审查结论】的可选字段「模块」，解析进 `Conclusion.module`。
- review-registry 返工：
  - 记下审查编号对应的模块：最近一次写了模块的那一轮为准；
  - 新增 `reviews.module_reviews(g, session)`，返回按模块分组的审查，以及没标模块的审查编号。
- `decision_inbox/mapview.py`：`render_line`、`render_all`。
- 命令行 `map` 子命令。

**范围外**

- 模块状态、进度、依赖、挂起、「挡住 N 个」的计算：归 spec-guard。
- 由别的线负责、剩余要点：第一版不写（已定事项 2）。
- 约定块要求负责人写「模块」字段：归 onboarding。
- 「阻塞：等谁」整条线的状态：在 `/lines` 显示，不覆盖模块状态（需求第 7.1 节调整第 2 条）。

## 接口约定

```python
from decision_inbox import mapview, reviews

mapview.render_line(g, now="...", line="前端", read=read_result, full=False)   # /map 前端；read 是 spec-guard-reader 的 ReadResult
mapview.render_all(g, now="...", reads={"fe-codex": read_result, ...})          # /map all

cells, unmarked = reviews.module_reviews(g, session="fe-codex")
cells["pay"]     # (ModuleReview(ref="R-3", node="spec", verdict="changes-needed", advice_count=None, rounds=2, closed=False), ...)
unmarked         # ("R-7",)：没标模块的审查编号
```

- `render_line` 的 `line` 按已定的选线规则匹配；`read` 由调用方用 `specguard.read_line(<该线 repo>)` 取得，测试里直接构造。
- message-protocol：`msg.conclusion.module` 为字段原文去掉首尾空格，没写为 None。不校验它是否是真实的模块编号（协议层不知道能力图）。

## 依赖

- 本插件模块：spec-guard-reader（`LineMap`、`ReadResult`）、review-registry（返工后的 `module_reviews`）、decision-queue（`pending`）、wait-tickets（`open_tickets`）、message-protocol（返工）、group-store（名册）、hub-view（时间写法）。
- 能力图里本模块的依赖写的是 line-health。实际不用它：线的状态在 `/lines`，`/map` 只看模块。依赖列改为 `spec-guard-reader, review-registry, decision-queue, wait-tickets`，随本规格一起审。
- 外部组件：spec-guard ≥ 0.62.0 的 `map_view.py --json`。不缺接口。

## 项目结构

```text
decision_inbox/mapview.py      本模块
decision_inbox/protocol.py     返工：【审查结论】的「模块」字段
decision_inbox/reviews.py      返工：记模块、module_reviews
decision_inbox/__main__.py     加 map 子命令
tests/test_mapview.py          单元测试
```

## 命令

```bash
python3 -m unittest discover -s tests -v
```

## 代码风格

沿用前面的模块：只用标准库，代码和注释用英文，给用户看的文字用中文。

## 测试策略

- spec-guard 的数据用 line-health 测试里已有的构造方式拼 JSON，再用 `specguard.parse_map` 解析；另用真实的 `map-0.63.json` 夹具跑一遍。
- 用 group-store 临时组构造名册、审查登记与结论、事项、等待单；时间全部显式传入。
- 默认视图做一份完整的期望文本，逐字比较；其余细则逐条断言。

## 边界

- **始终**：模块状态只取 spec-guard；两种审查分两列、列名固定；只读。
- **先问**：改变列、折叠规则或状态写法；在 `/map` 里加 spec-guard 没有的模块级数据（本规格已定的三样除外）。
- **绝不**：自己解析能力图或 todo；改 spec-guard 给的状态；把外部等待写成模块状态。

## 验收标准

1. 默认视图与一份完整期望文本逐字一致：表头（含关键卡点、等你决定、未合入未推送）、展开的行、两行合并、两种审查列、当前模块的外部等待备注。
2. 6 种状态的写法与关键决策 3 一致，in_progress 的三种 step 都覆盖。
3. Spec/Plan 评审列 5 种标记写法正确。
4. 架构审查列：同一模块两个节点用「 · 」连接；有须修改项写轮数；通过附建议写条数；没结论「—」；本线无审查者时表头有说明、列里全是「—」；未标模块的审查在表头计数。
5. 折叠：最近完成取 `lastTickAt` 最晚的；都没有时取位次最大的；合并行的位次范围正确；`全部` 时没有合并行。
6. 外部等待：有当前模块时写进它的备注，没有时写进表头；等用户的单不算。
7. 等你决定：本线发起的、多线事项含本线的都列；没有就不出现这一段。
8. `/map all`：每条开发线一行；读不出的线写原因；按名册顺序。
9. 选线：短名、身份名都能选；对不上时列出现有的线。
10. 读不出能力图：一行原因，加上这条线的待答事项和外部等待。
11. message-protocol：【审查结论】写了「模块」时解析出来，没写时为 None，原有测试不改动、全部通过。review-registry：模块取最近一次写了模块的那一轮；`module_reviews` 分组正确。
12. 命令行：`map <组> <线>`、`map <组> <线> 全部`、`map <组> all` 退出码 0；协作组不存在为 2；运行前后协作组文件逐字节不变。

## 假设

1. spec-guard 的 `blocks` 已按依赖链计入间接被挡的模块（spec-guard `spec/map-view.md` 的契约）。如果实测不是，回来改这一条，不在本模块里自己算。
2. 负责人会照约定块写「模块」字段；漏写时这条审查只出现在表头的「未标模块」计数里，不会算错到别的模块。

## 未决问题

无。

## 文档建议

无。`/map` 的用法写进 README（onboarding 模块已记）；约定块要求负责人写「模块」字段，记给 onboarding。
