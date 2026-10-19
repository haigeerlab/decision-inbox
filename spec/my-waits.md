<!-- spec-guard: review approved 09e56c67c18c -->

# Spec: my-waits

> 能力图模块 `my-waits`（2026-10-20 用户确认插入，排在 patrol-watch-runtime 之后）。来源：需求记录 3.3.5「开发线 · 查询 ·『我在等什么』『谁在等我』·【二】」与 11.2「开发线：『我在等什么』『谁在等我』」。用户 2026-10-20 选定第二版先做这一项，并确认下面的假设。

## 目标

任何接入协作组的会话，运行一条命令就知道自己该等还是该催：自己在等谁的什么、等了多久、对方在不在线，以及谁在等自己。

## 现状

- 等待记录（W 编号）存在 `tickets` 状态里：`waiter`（等待方的 agent-relay 名）、`target`（「在等谁」原文）、`targetRelay`（认得出时对方的 agent-relay 名）、`what`、`sentAt`、`status`。`tickets.open_tickets` 已经算好等了多久、`waited`（≥30 分钟）、`maybe-stuck`、`offline`（需要 agent-relay 快照）几种标记，`stale_numbers` 给出「可能已失效」。
- 待决事项（# 编号）存在 `items` 状态里：`sender`、`status`（`pending` → 用户答复后 `forwarded` → `picked` → `acknowledged`；结束是 `closed`／`superseded`／`withdrawn`）、`sent`（`items.delivered` 判断答复是否已送到发件会话）、`waitKind`（`go-to-session` 是「去会话操作」）。
- 只有主视图、`/lines`、`/flow` 能看到这些，都是给用户看全组的；会话自己没有只看自己的查询。
- `whoami` 按当前目录给出 `group`、`relayName`、`role`。

## 要你确认的假设（用户 2026-10-20 已确认）

1. **谁能用**：任何接入的会话（开发线、审查者、跨线协调、模块协调），查的是自己（`whoami` 的 `relayName`）。决策收件箱自己运行时，两节都为空，并提示「决策收件箱看主视图」。
2. **「我在等什么」分两类**：
   - 我开的、还开着的等待记录：`W编号 在等 <对象> 的「<等什么>」，已等 N 分钟` 加标记；
   - 我抛出、还没结束的待决事项（状态不是 `closed`／`superseded`／`withdrawn`），按状态写：
     - `pending`：「等用户决定」；是去会话操作的写「等用户来本会话操作」；
     - 已答复但 `delivered` 为假：「用户已答复，答复还没送到」；
     - 已答复且已送到：「答复已送到，执行后发【已恢复】结项」。
3. **「谁在等我」**：只算别人开的、还开着、对象是我的等待记录（`targetRelay` 是我，或 `target` 是我的会话名、agent-relay 名）：`W编号 <等待方> 在等你的「<等什么>」，已等 N 分钟` 加标记。审查队列不算（属于第二版「负责人：审查队列」）。
4. **标记**：沿用 `open_tickets` 与 `stale_numbers` 的判断——「已等 N 分钟」（≥30）、「可能卡住」、「对方离线」（只在给了 agent-relay 快照时判断）、「可能已失效」。不新增判断规则。
5. **只读**：不给任何会话发消息，不写状态，不催办（需求 11.3 不做自动催办）。

## 要做的

1. `query`：新增 `render_waits(g, relay_name, now, relay=None)`，按假设 1～4 出文字；两节都空时写「没有在等的，也没有人在等你」。
2. 命令行：`query waits <组> --me <agent-relay 名> [--agents <bridge_agents 输出>]`。
3. 斜杠命令 `commands/waits.md`（`/decision-inbox:waits`）：`whoami` 取组和自己的名字 → `bridge_agents` 写入 `io/agents.json` → 运行 `query waits` → 原样显示。照 `/lines` 的写法。
4. README「查询命令」加 `/waits` 一行。

## 做 / 不做

- 做：上面 1～4；版本号升到 0.0.33。
- 不做：审查队列、催办或代发消息、改等待记录与待决事项的数据结构、改协作规则段（规则段里不要求会话去跑这条命令）、打标签。

## 验收标准

1. 一个开发线开了两条等待记录（一条等另一条线、一条已失效）、抛了三项待决事项（pending、已答复未送到、已答复已送到）：`/waits` 的「我在等什么」按假设 2 列出五行，状态与标记正确；已结束的事项、已关的等待记录不出现。
2. 另一条线开了等它的等待记录：「谁在等我」列出这一条，带等待方和等了多久；对象写会话名或 agent-relay 名的都认得。
3. 给了 agent-relay 快照且对方离线时带「对方离线」；不给快照时不判断离线。
4. 两节都空时写「没有在等的，也没有人在等你」；决策收件箱运行时提示看主视图。
5. 命令不发消息、不改任何状态文件（测试比对运行前后的状态目录）。
6. 新测试先失败后通过；全量 `PYTHONPATH=tests:. python3 -m unittest discover -s tests` 通过。

## 风险

- 「在等谁」是自由文本，写成别的叫法（例如中文昵称）时认不出是在等我：只按会话名和 agent-relay 名认，认不出的不进「谁在等我」，和主视图一致。
- 会话多开几个目录对上多个组时 `whoami` 退出 5，命令照 `/lines` 把 stderr 原样告诉用户。

## 文档建议

README「查询命令」加 `/waits` 一行；术语表已有「等待记录」「待决事项」，不加。其他无。
