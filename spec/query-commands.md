<!-- spec-guard: review approved 2983841c8aac -->
# Spec: query-commands

> 能力图模块 `query-commands`。需求来源：`docs/requirements-record.md` 第 7.1 节（`/lines`、`/flow`、`/item` 与 `/flow` 的诊断要求）、第 3.3.1 节查询行、第 13.1 节第 6 行。
> 接口依据：agent-relay 源码 `bridge/src/server.ts` 的 `bridge_wake_status`、`bridge-store.ts` 的 `MessageStatus`、`wake-queue.ts` 的 `WakeJob`（本机缓存 0.6.1 的源码；实现时用 0.6.10 实采的样例核对）。

## 目标

给用户三个只读查询，看多少次都不打扰任何一条线：

- `/lines`：各线一览，每条线一行。分清「已结项」和「阻塞：等谁」。
- `/flow`：流畅度体检。顺着等待链找到源头，归入需求第 7.1 节的分类，只给一个结论：谁来做什么。在收件枢纽里说「怎么停了」「卡在哪」也走这个查询。
- `/item <编号>`：单项追溯。一个事项从谁抛、谁转、用户何时答、对方何时恢复的完整时间线；编号是等待单时，给等待单的时间线。

本模块只组合已有的事实、排版成文字：状态与信号用 line-health，事项用 decision-queue，等待单用 wait-tickets，投递与唤醒用 relay-reader。不写状态文件，不发消息，不叫醒。

## 已定事项（用户 2026-10-16 确认）

1. **`/item` 的投递、确认、唤醒记录只用 `bridge_wake_status`**：按消息编号逐条查（收单那条、每条答复）。返回里的正文预览 `preview` 丢弃，不接 `bridge_thread`，消息正文不进本插件。能力图 relay-reader 那一行相应改为「只追加 `bridge_wake_status`」。
2. **`/flow` 不写「负责人最后一次跟进」**：长期外部阻塞只写已阻塞多久、等谁、等什么，跟进一栏写「第一版不记录」。
3. **`/flow` 只判漏抛，不判送错**：会话在 agent-relay 里是「等待输入」（`presence_raw` 为 `waiting-input`），但待答表里没有它的事项、也没有它开着的等待单，判为漏抛。送错要读别人的收件箱，第一版不做。

## 关键决策与取舍（请重点审）

1. **数据怎么进来**：MCP 工具只能由收件枢纽会话调用，Python 拿不到。所以三个查询都做成命令行：
   - 收件枢纽先调 MCP 工具，把原文存成临时文件，再把文件路径传给命令行；
   - 命令行读协作组的状态、调 spec-guard-reader 读各线仓库，算出结果后打印 Markdown。
   - 斜杠命令文件（告诉收件枢纽先调哪些工具、再跑哪条命令）和插件清单，归 onboarding 统一做。本模块只交付命令行和渲染函数。
2. **进度快照**：line-health 需要上次巡视的快照。本模块从 group-store 领域 `patrol` 的 `snapshot` 键只读取它，没有就传 None。快照由 patrol 写，本模块从不写。
3. **`/item` 分两步**：先 `query item-ids <编号>` 打印要查的 agent-relay 消息编号；收件枢纽对每个编号调一次 `bridge_wake_status(messageId)`，再把这些结果文件传给 `query item`。
   - agent-relay 只许消息的发件人或收件人查状态。【等待用户】是发给收件枢纽的，答复是收件枢纽发的，都查得到。
   - 某个编号查不到或报错时，那一行写「agent-relay 查不到 #编号」，不中断。
4. **源头怎么选**（`/flow`，需求第 7.1 节）：
   - 用开着的等待单画出「谁在等谁」。只有能对上名册的等待方和被等方才进图；等用户的单不进图。
   - 图里有环：结论是「互等成环」，停在哪写环上的会话，如「前端 ⇄ API」。
   - 没有环：在「被别人直接或间接等着、自己没在等别的会话」的会话里，选挡住会话最多的那个；并列时选被等得最早的那个。
   - 图里没有等待：从各线状态里按「等你确认 → 等你决定 → 身份失效 → 掉线 → 悄悄停下」的顺序，取第一个有这种情况的会话。都没有就是「流畅」。
5. **源头归类**：按下表取第一个符合的。前 9 类是需求第 7.1 节的表；最后一类是新加的兜底，表里没有对应情况，请重点审。

   | 源头的情况 | 怎么判断 | 你要做 / 谁来做 |
   |---|---|---|
   | 等用户去原会话亲自确认 | 状态词 needs-user | 打开「X」会话，确认它弹出的请求（detail）/ 用户 |
   | 等用户决定 | 它有完全停住的待答事项 | 回 `<复制块>`（hub-view 的复制块写法）/ 用户 |
   | 身份失效 | agent-relay 记录 `retired` | 叫醒后用原名重登 / 插件 + agent-relay |
   | 离线 / 被挂起 | 状态词 offline | 巡视会自动叫醒，叫不醒请打开「X」/ 插件，兜底用户 |
   | 交付了没人接 | 它是信号 2 的等待方 | 叫醒 X 去取 Y 的交付 / 插件 |
   | 悄悄停下 | 状态词 stalled | 叫醒 X，要它继续或上抛 / 插件 |
   | 正在忙长任务 | 状态词 working | 不打扰，已忙 N 分钟 / — |
   | 等别的线交付 | 它有开着的等待单、等的对象不在名册里 | 交负责人跟进 / 负责人 |
   | 互等成环 | 第 4 条找到环 | 你来定谁先做 / 用户 |
   | 被等着但没在干活（新加） | 以上都不是：已结项或无活动，却有人在等它 | 问 X 是否已交付，没交付就让它接着做 / 用户 |

6. **`/flow` 输出**：先给结论，再给 5 项检查明细。结论的写法按需求第 7.1 节的样例：
   ```text
   停在哪：前端（14:14 起）
   为什么：等你在原会话亲自确认（permission prompt）
   你要做：打开「前端」会话，确认它弹出的请求（谁来做：用户）
   被它挡住：总协调（#2842）、API（#2910）
   其他：后台 已结项（空闲）· UI 干活中

   检查明细
   - 等待链：API → 前端；总协调 → 前端；无循环
   - 积压：API 有 3 条未读，最早已等 25 分钟，叫醒没成功 2 次
   - 停住的线：无
   - 漏抛：无
   - 长期外部阻塞：无
   ```
   - 「被它挡住」后的括号是挡住它的那张等待单的编号（group-store 的编号，不是 agent-relay 的消息编号）。
   - 「（14:14 起）」取最早一张等它的等待单的发出时间；没有等待单时取状态词的起始时间；都没有就不写括号。
   - 流畅时只写一行「流畅：没有卡点」，后面照样列检查明细。
7. **5 项检查各看什么**：
   - 等待链：每条等待单一段「等待方 → 被等方」，最后写有无循环。
   - 积压：agent-relay 里有未读、并且最早一条已等 10 分钟以上的会话（line-health 的 `BACKLOG_MINUTES`）。「叫醒没成功」= 这个会话的唤醒记录里状态是 held、refused、unknown、expired 的条数。
   - 停住的线：line-health 的信号 3。
   - 漏抛：已定事项 3。
   - 长期外部阻塞：开着 60 分钟以上的等待单（wait-tickets 的 `STUCK_MINUTES`），写「已阻塞 N 小时 · 负责人跟进：第一版不记录」。
8. **`/lines` 一行的写法**：`前端 · 干活中 · 当前模块 pay（6/11）· 最后产出 14:20（40 分钟前）· 未读 0 · 在等：API`。
   - 状态：line-health 的状态文字。
   - 当前模块：spec-guard 的当前模块和已勾数。读不出时如实写原因：「无能力图」「spec-guard 未安装」等，用 spec-guard-reader 的 `reason`。
   - 最后产出：已勾数上次变化的时间（快照）和最后勾选时间（git 历史完整时）中较晚的那个。都没有写「最后产出：无记录」。
   - 未读：agent-relay 的积压数；判断不了写「未读：未知」。
   - 在等：它开着的等待单的被等方，用「、」连接；在等用户答复的写「你（#12）」；都没有写「在等：—」。
   - 按名册顺序，跳过收件枢纽。
9. **`/item` 时间线**：每行 `HH:MM 事件`，按时间排序。事项的事件来自 decision-queue 的 `history`：
   - 抛出（谁、agent-relay 消息编号、收单时的审查标签）、被取代、撤回（原因）、用户答复（原话）、转发给谁（发送编号）、对方取走、对方确认、对方恢复（结束）。
   - 再并入 `bridge_wake_status` 的事实：每条消息的投递状态、确认时间、回复编号、唤醒状态与说明。
   - 第一行写事项概要：`#12 · 前端 · 支付页先接哪种支付方式 · 当前：已转达`。
   - 编号是等待单时：开单（谁等谁、等什么）、关单（理由、依据）。
   - 编号两边都没有：写「#N 不是事项也不是等待单」。
   - `/item` 是展开视图，可以出现 agent-relay 消息编号，不出现消息正文。

## 范围

**范围内**

- relay-reader 返工：
  - `parse_message_status(text)` 解析 `bridge_wake_status(messageId)` 的结果；
  - `parse_wake_jobs(text)` 解析不带参数的 `bridge_wake_status`，得到每个会话各种唤醒状态的条数。
  - 两个都丢弃 `preview`。
- `decision_inbox/query.py`：`render_lines`、`render_flow`、`item_message_ids`、`render_item`。
- 命令行：`python3 -m decision_inbox query lines|flow|item-ids|item ...`。
- 已定事项和上面的关键决策。

**范围外**

- 叫醒、追问、替用户做任何事：叫醒归 patrol；`/wake`、`/ask` 是第二版。
- `/map`：归 map-view。
- 送错检测、负责人跟进记录：第一版不做（已定事项 2、3）。
- 斜杠命令文件、插件清单、Codex 侧的查询技能（第二版）：归 onboarding 或之后。
- 主动推送「全线停住」：hub-view 已做第一行，patrol 负责触发。

## 接口约定

```python
from decision_inbox import query, relay

status = relay.parse_message_status(text)   # MessageStatusFact（见下）；结构不对抛 relay.RelayDataError
wakes = relay.parse_wake_jobs(text)         # {agent 身份名: {唤醒状态: 条数}}

query.render_lines(g, now="...", assessment=a, relay=agents, maps=maps)            # /lines 的 Markdown
query.render_flow(g, now="...", assessment=a, relay=agents, wakes=wakes)            # /flow 的 Markdown
query.item_message_ids(g, number=12)       # 要查的 agent-relay 消息编号，按先后排序；不是事项时为 ()
query.render_item(g, number=12, statuses={2842: status, ...})                       # /item 的 Markdown
```

```python
@dataclass(frozen=True)
class MessageStatusFact:
    id: int
    sender: str
    recipient: str
    sent_at: str | None
    delivery_state: str | None    # queued | sending | accepted | failed | unknown | expired
    acknowledged_at: str | None
    reply_ids: tuple[int, ...]
    wake_state: str | None        # pending | sending | accepted | read | held | refused | unknown | cancelled | expired | acknowledged
    wake_detail: str | None
    outcome: str | None           # pending | acknowledged | replied | failed | expired
```

命令行（`--agents`、`--wakes`、`--status` 都是收件枢纽存下的 MCP 工具原文文件）：

```bash
python3 -m decision_inbox query lines <协作组> --agents <文件> [--relay-version <版本>]
python3 -m decision_inbox query flow <协作组> --agents <文件> --wakes <文件> [--relay-version <版本>]
python3 -m decision_inbox query item-ids <协作组> <编号>
python3 -m decision_inbox query item <协作组> <编号> [--status <文件> ...]
```

- 退出码：0 成功；2 参数错误或协作组不存在；3 agent-relay 原文读不出（打印原因，不输出半截结果）。
- 时间以运行时的本机时间为准；渲染函数的 `now` 显式传入，便于测试。

## 依赖

- 本插件模块：group-store（名册、状态）、relay-reader（在线状态、积压、唤醒、消息状态）、decision-queue（待答、历史、`get`）、wait-tickets（等待单）、line-health（状态词、信号、常量）、spec-guard-reader（各线仓库）、hub-view（复制块、时间写法）。
- 外部组件：agent-relay ≥ 0.6.10 的 `bridge_agents`、`bridge_wake_status`；spec-guard ≥ 0.62.0 的 `map_view.py`。不缺接口。

## 项目结构

```text
decision_inbox/query.py          本模块
decision_inbox/relay.py          返工：parse_message_status、parse_wake_jobs
decision_inbox/__main__.py       加 query 子命令
tests/test_query.py              单元测试
tests/fixtures/relay/            加 wake_status 的样例（合成一份、实采脱敏一份）
```

## 命令

```bash
python3 -m unittest discover -s tests -v
```

## 代码风格

沿用前面的模块：只用标准库，代码和注释用英文，给用户看的文字用中文。

## 测试策略

- 用 group-store 临时组构造名册、事项、等待单；agent-relay 与 spec-guard 的数据直接构造 `AgentsSnapshot`、`ReadResult`；时间全部显式传入。
- 源头选择和 10 类归类，各用一个最小场景断言结论的三行（停在哪、为什么、你要做）。
- 命令行用临时文件跑一遍 `lines`、`flow`、`item-ids`、`item`，断言退出码和关键行。
- 实采：实现时调用一次 `bridge_wake_status`（不带参数和带一个消息编号各一次），脱敏后存为夹具。

## 边界

- **始终**：只读；结论只给一个；编号两边都查不到时如实说；消息正文和 `preview` 不进输出。
- **先问**：给 `/flow` 加新的源头分类；在查询里加任何会动别人的操作；接 `bridge_thread`。
- **绝不**：叫醒、发消息、写状态文件；自己判断状态词或信号（用 line-health 的）。

## 验收标准

1. `/lines`：每条开发线一行，按名册顺序，含状态、当前模块与已勾数、最后产出、未读、在等。spec-guard 读不出时写它给的原因；未读判断不了写「未知」；在等用户答复写「你（#N）」。
2. `/flow` 等待链有环：结论是「互等成环」，停在哪写环上的会话，你要做写「你来定谁先做」。
3. `/flow` 无环：选出挡住会话最多、自己没在等别的会话的源头；并列时选被等得最早的；「被它挡住」列出直接和间接挡住的会话和单号。
4. 10 类源头各一个场景：「为什么」「你要做」「谁来做」与关键决策 5 的表一致。
5. 没有等待单、也没有异常状态：第一行是「流畅：没有卡点」。
6. 检查明细 5 行都在。积压按 10 分钟门槛、叫醒没成功按 4 种状态计数；漏抛按已定事项 3；长期外部阻塞按 60 分钟，并写「负责人跟进：第一版不记录」。
7. `/item` 事项：时间线按时间排序，含抛出、答复、转发、投递、确认、唤醒、恢复。缺某条消息的状态时写「agent-relay 查不到 #编号」。输出不含 `preview` 和消息正文。
8. `/item` 等待单：含开单和关单（理由、依据）。编号两边都没有：写「#N 不是事项也不是等待单」。
9. `item_message_ids`：收单那条和每条答复的编号，去重、按先后排序。
10. relay-reader：`parse_message_status`、`parse_wake_jobs` 解析合成样例与实采样例；结构不对抛 `RelayDataError`；解析结果里没有 `preview`。
11. 命令行：4 个子命令在临时文件上跑通，退出码 0；协作组不存在为 2；agent-relay 文件不是 JSON 为 3。
12. 查询前后，协作组目录里的文件逐字节不变。

## 假设

1. 收件枢纽会话能调 `bridge_agents`、`bridge_wake_status`，并能把结果写到临时文件。
2. 0.6.10 的 `bridge_wake_status` 字段与本机缓存的 0.6.1 源码一致；不一致时以实采为准，并回来改本规格。
3. patrol 会把进度快照存在领域 `patrol` 的 `snapshot` 键。patrol 定规格时如果要换地方，本模块跟着改。

## 未决问题

无。第 12 节没有归本模块的待定项；用到的门槛都已在第 3 项定过。

## 文档建议

无。三个查询的用法会写进 README（onboarding 模块已记）。
