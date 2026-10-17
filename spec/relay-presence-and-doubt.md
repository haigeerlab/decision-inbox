<!-- spec-guard: review pending -->
# Spec: relay-presence-and-doubt

> 能力图模块 `relay-presence-and-doubt`（2026-10-17 用 add-module 插入，排在 protocol-contract-v1 之后）。来源：`docs/requirements-record.md` 13.5「依赖插件升级核对」（agent-relay 0.8.0–0.8.2 的新事实），以及 wait-honesty-and-briefs、doctor-and-observer 实测记录里的观察。用户 2026-10-17 同意另开本模块。

## 目标

主视图和巡视用上 agent-relay 0.8 给的新事实，并修掉实测里看到的几处说错话：

- 现在会话「在不在干活」只看最近活动时间，Claude 会话空闲时，有积压消息也写「已忙 N 分钟」；agent-relay 0.8.1 起 `presence.activity` 直接给出 `busy`／`idle`。
- Codex 收件方的唤醒被接受却一直没读（信箱连接断开），agent-relay 0.8.2 起标为「送达存疑」，本插件仍当作已送达。
- 收件枢纽欠的回复只增不减：被取代、被撤回的【等待用户】永远没有答复（实测某收件枢纽 `owesReplies` 5 条）；agent-relay 0.8.0 起 `bridge_send` 能用 `alsoAnswers` 一次关掉多条、发件方能用 `withdraws` 撤回自己的请求。
- 实测观察：没带 agent-relay 状态时仍报「全线停住」；各线一行按可能已失效的等待单写「阻塞：等di-e2e-dev-a」（写的还是身份名）；负责人已经发出【已恢复】、收件枢纽还没收进时，停止钩子照样拦。

## 关键决策与取舍（请重点审）

1. **空闲与忙碌**（返工 relay-reader、line-health）。
   - relay-reader 读出 `presence.activity`（没有这个字段的旧版本为 None）。
   - line-health：`running` 且 `activity=busy` 算「干活中」；`activity=idle` 不算，按原有规则往下判断（停住、空闲等）。没有 `activity` 时照旧看最近活动时间。
   - 信号 5「已忙 N 分钟还有积压」只在 `busy` 或没有 `activity` 时报；`idle` 又有积压时改报「X 空闲，有 N 条消息没读」，建议「巡视会叫醒它；叫不醒就打开它」。
2. **送达存疑**（返工 relay-reader、line-health、hub-view、wait-tickets）。
   - relay-reader 读出 `waiting.doubtfulIds`（`bridge_agents`）和 `wake.doubt`（`bridge_outbox`、`bridge_wake_status`）。
   - 有存疑的会话，主视图异常区加一行「X（Codex）有 N 条消息送达存疑：完全退出 ChatGPT 再打开 X 的任务（来源：agent-relay）」；巡视首次发现时通知用户一次（同一批存疑只通知一次）。
   - `/item` 的时间线把存疑的那条写成「已接受但没读到（送达存疑）」，不写「已送达」。
3. **欠回复的清理**（返工 hub-loop、onboarding 约定块）。两头都做：
   - **发件方撤回**：约定块「事项有效性标记」一条加一句：写【取代 #旧】或【撤回】时，`bridge_send` 带 `withdraws: [旧那条的邮箱号]`；默认取代时也一样。
   - **收件枢纽兜底**：收件枢纽给某个会话发【用户答复】时，把这个会话被取代、被撤回、还没回复过的【等待用户】的邮箱号放进 `alsoAnswers`，一次关掉。`sends` 的每一项多一个 `alsoAnswers` 列表，收件枢纽约定块写明照填。
   - agent-relay 早于 0.8.0 时这两个参数会被悄悄丢掉，不出错，只是关不掉；不做版本分支。
4. **没带状态时不报「全线停住」**（返工 line-health）。本次没带 agent-relay 状态或读不到时，信号 1 不触发：判断不了谁在干活，就不下「全线停住」的结论；顶部已有「本次没带／读不到」一行。
5. **各线一行说实话**（返工 line-health）。算各线「阻塞：等谁」时跳过可能已失效的等待单；对方写短名（名册里有就用短名，没有才用身份名）。都跳过后按原有顺序往下判断（例如「阻塞：等你决定 #15」）。
6. **停止钩子不误拦已发的【已恢复】**（返工 stop-hook 的提示文字）。钩子读不到会话自己发出的邮件（agent-relay 没有只读的命令行入口，需求已提过），所以不改判断，只改拦截说明：在原说明后加「如果你已经发过【已恢复】、收件枢纽还没收进，回一句『已发 #邮箱号』即可收工，不用重发」。同时在需求记录里把「agent-relay 只读命令行入口（outbox）」的需求补上这个用例，转给 agent-relay 负责人。
7. **版本 0.0.9**。

## 范围

做：`decision_inbox/relay.py`、`health.py`、`view.py`、`query.py`、`tickets.py`、`patrol.py`、`hub.py`、`onboard.py`、`stophook.py`、`README.md`、两份 `plugin.json`，以及对应测试；`docs/requirements-record.md` 补一条转给 agent-relay 的需求。

不做：

- 读 agent-relay 的数据库或内部文件：只读它的工具输出（经会话转交）。
- 按 agent-relay 版本分支处理新参数。
- 改契约 session-protocol：`alsoAnswers`、`withdraws` 是 agent-relay 的发送参数，不是消息正文，契约 v1.0 不变；约定块的新写法若要写进契约，并进 v1.1 另批。

## 接口约定

```python
relay.AgentFact.activity: str | None          # "busy" | "idle" | None
relay.AgentFact.doubtful_ids: tuple[int, ...]
relay.MessageFact.wake_doubt: bool             # outbox / wake_status
hub Reply.sends[i]["alsoAnswers"]: list[int]   # 收件枢纽照填进 bridge_send
```

## 测试策略

- 单元测试：
  - relay-reader：有、无 `activity`、`doubtfulIds`、`wake.doubt` 的输入。
  - line-health：busy 算干活中、idle 不算；idle 有积压的新提示；没带状态时没有信号 1；各线一行跳过可能已失效的单、写短名。
  - 送达存疑：异常区一行、巡视只通知一次、`/item` 措辞。
  - hub-loop：答复带 `alsoAnswers`（被取代、被撤回、没回复过的同会话事项），不带别的会话的、不带已回复过的。
  - 约定块：`withdraws` 那一句；收件枢纽约定块照填 `alsoAnswers`。
  - 停止钩子：新的说明文字。
- 命令行实跑：scratchpad 临时协作组，用手写的 `bridge_agents`、`bridge_outbox` 输出跑一遍主视图与 `/item`。
- 实测（先问用户）：di-e2e 里让一条线抛两项（第二项默认取代第一项），用户答复后看收件枢纽的 `owesReplies` 是否回到 0。

## 边界

- 始终：只读 agent-relay 的工具输出；读不到就说读不到。
- 先问：实测。
- 绝不：替发件方撤回请求（`withdraws` 只能由发件方自己发）；为依赖插件的缺陷加绕过逻辑。

## 验收标准

1. busy 算干活中、idle 不算；idle 又有积压时写「空闲，有 N 条消息没读」，不写「已忙」。
2. 送达存疑在主视图、巡视通知、`/item` 都有，且标来源 agent-relay。
3. 【用户答复】的 `sends` 带上同会话被取代、被撤回、没回复过的事项的邮箱号；约定块写明 `withdraws` 与 `alsoAnswers` 的用法。
4. 没带或读不到 agent-relay 状态时不报「全线停住」。
5. 各线一行不按可能已失效的单写阻塞，对方写短名。
6. 停止钩子的拦截说明里有「已发过【已恢复】时怎么办」；需求记录补了转给 agent-relay 的用例。
7. 两份清单 0.0.9；原有测试全部通过；契约一致性测试照样通过。
8. 实测：`owesReplies` 回落（或记明未实测）。

## 假设

1. agent-relay 0.8.1 起 `presence.activity` 只在 Claude 会话 `running` 时出现；Codex 会话没有这个字段（本机 2026-10-17 `bridge_agents` 实读如此）。
2. `waiting.doubtfulIds` 和 `wake.doubt` 的字段名以 agent-relay 0.8.2 CHANGELOG 为准；实现前用本机 `bridge_agents` 再核对一次，名字不对就停下来问。
3. `alsoAnswers` 里的编号必须是发给收件枢纽自己的请求；有一个关不掉整条不发（agent-relay 的规则），所以只放收件枢纽确认过、确实没回复过的编号。

## 未决问题

1. 第 3 条两头都做（推荐），还是只做收件枢纽兜底（约定块不改，开发线不用学新参数）。
2. 第 6 条只改说明文字（推荐），还是等 agent-relay 提供只读的发件查询后再改判断。

## 文档建议

README「使用注意事项」表里「消息一直显示已送达却没人读」一行改为指向主视图的「送达存疑」；排查表加「收件枢纽欠回复越来越多」一行。
