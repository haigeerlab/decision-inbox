<!-- spec-guard: review approved b065c728c792 -->
# Spec: hub-loop

> 能力图模块 `hub-loop`。需求来源：`docs/requirements-record.md` 第 3.3.1 节（用户经收件枢纽的操作）、第 3.3.2 节（收件枢纽）、第 4 节（事项与消息约定，尤其 4.6 边界、4.7 通信通道）、第 6.4 节（用户回复）。
> 接口依据：agent-relay 0.7.0 运行时源码（`~/.agent-relay/runtime/src/server.ts`、`src/bridge-store.ts`、`src/paging.ts`），2026-10-16 读取。

## 目标

把前面各模块接成收件枢纽会话能照着跑的主循环。收件枢纽会话只做两件事：调用 agent-relay 的 MCP 工具，把命令行的输出原样执行或显示。判断和记账全在命令行里：

- **收件**：`inbox receive` 读一批邮箱原文，按消息类型分给待答表、等待单、审查登记、【已恢复】处理，给出要退回的说明、要告诉用户的话、要确认已读的消息编号；
- **用户说话**：`inbox reply` 接住用户在收件枢纽里打的每一句话，认出是答复、关单、看详情还是看明细，给出要发的答复或要显示的文字；认不出就返回一个问题；
- **发完记账**：`inbox sent` 记下每条发出消息的 agent-relay 编号，顺带按理由 3 关掉已转达的等待单；
- **看主视图**：`view` 更新投递进度后显示主视图，也能显示四种展开视图；
- **约定块**：收件枢纽会话自己的工作约定，由 onboarding 写入。

## 已定事项（用户 2026-10-16 确认）

1. **消息整批交文件**：收件枢纽把 `bridge_inbox` 的返回原样写进文件，`inbox receive --inbox <文件>` 一次处理一批，按 agent-relay 消息编号去重，同一条交两次不会重复编号。relay-reader 返工，新增 `parse_inbox`。
2. **退回说明和答复直接发**：命令列出要发的消息，收件枢纽不再问用户，直接用 `bridge_send` 发出，再用 `inbox sent` 记编号。理由：答复是用户已经说过的话；退回说明是格式检查的结果，不含任何决定。
3. **用户说的话只有一个入口**：用户在收件枢纽里说的每句话都原样交给 `inbox reply`，由它判断是什么意思。收件枢纽自己不解读，也就不会改写用户的话。
4. **改规则在约定块里转发**：用户说「以后 X 都这样」，第一版不做专门的命令。约定块要求收件枢纽把用户原话一字不改地转给用户点名的会话，发出前先向用户确认收件人。

## 关键决策与取舍（请重点审）

1. **分发规则**（`inbox receive`，每条消息按 message-protocol 认出的类型分发）：

   | 类型 | 交给 | 不合格时 |
   |---|---|---|
   | 【等待用户】 | decision-queue 收单；wait-tickets 处理开头的「结束」行 | 退回 decision-queue 生成的说明 |
   | 【撤回】 | decision-queue | 同上 |
   | 【等待其他会话】 | wait-tickets 开单 | 退回，说明由本模块按同样写法生成 |
   | 【已恢复】 | wait-tickets 按「结束」行关单；decision-queue 的 `on_resumed` 结束已转达的事项 | 同上 |
   | 【审查结论】 | review-registry 记一轮 | 退回 review-registry 给出的问题（例如「不是登记的审查者」） |
   | 【用户答复】 | 不处理（只有收件枢纽能发这类消息） | 告诉用户「X 发来一条【用户答复】，收件枢纽不处理」，不退回 |
   | 认不出类型 | 不处理 | 告诉用户「X 称：<第一行>」，并提示用「<编号> 原文」看全文；不退回 |
   | 发件人是 `bridge`（agent-relay 自动通知） | 不处理 | 告诉用户一句，不回复（agent-relay 的规定） |

   - 各模块给的提示（例如「结束行里的 #5 不是你的等待单」）都列给用户看，不发给发件人。
   - 时间一律用消息的 `createdAt`：事项「几分钟前」和等待单「已等多久」都从对方发出时算起（需求 4.5）。
2. **去重与确认已读**：
   - 处理过的消息编号记在领域 `hub` 里，再次交来时直接跳过，不重复编号、不重复退回。
   - 每条处理过的消息（包括跳过的、退回的、认不出的）都列进输出的 `ack`，收件枢纽据此调用 `bridge_ack`。
   - 正文没读全的消息（`bodyTruncated`）不处理、不记、不列进 `ack`。输出会说明怎样用 `messageId` 和 `bodyOffset` 读全，读全后再交。
   - `hasMore` 为真时，输出提示「确认已读后再读一页」。
3. **要发的消息存在状态里，不存在临时文件里**：
   - `inbox receive` 和 `inbox reply` 生成的每条要发的消息都记进领域 `hub`，编号写作 `out:<n>`。正文写进协作组目录下的 `outgoing/<n>.txt`，收件枢纽用 `bridge_send` 的 `bodyFile` 原样发出，正文不经过它转写。
   - `inbox sent --done out:3=3950 --failed out:4` 记结果：发成的记下 agent-relay 编号，正文文件保留（协作组里的文件永久保留、不删，需求第 12 节第 11 项）；是答复的，同时调用 decision-queue 的 `record_sent`，再调用 wait-tickets 的 `close_answered`。
   - 发失败或还没记结果的消息一直留着。主视图最前面显示「⚠ 有 N 条消息没发出去，说「重发」再试」；用户说「重发」时，`inbox reply` 再把它们列一遍。
4. **`inbox reply` 的识别顺序**（只看整句，不猜）：

   | 用户说 | 做什么 |
   |---|---|
   | `<编号> 详情` | 显示事项详情（hub-view `render_detail`） |
   | `<编号> 原文` | 显示第 1 条里认不出类型的那条消息的全文（只限本模块记下的） |
   | `看等待` | `render_waits` |
   | `看已关闭`，可带日期 `看已关闭 2026-10-15` | `render_closed`，不带日期就是今天 |
   | `看失效` | `render_invalidated` |
   | `关掉 #编号`，可带多个编号和原因 | wait-tickets `close_by_user`。编号是事项而不是等待单时，返回问题：「#N 是事项，不是等待单；要放弃事项请让提出方发【撤回】」 |
   | `重发` | 把没发出去的消息再列一遍 |
   | 其他 | 交给 decision-queue 的 `interpret_reply`：认得出就调用 `answer`，生成【用户答复】；认不出就原样返回它的问题，什么都不发 |

   - 答复发给事项提出方时，`replyTo` 填原事项的 agent-relay 编号。多线事项发给各适用会话的几条不填 `replyTo`。
   - 答复、关单之后，输出最后附上新的主视图，收件枢纽一并显示。
5. **`view` 先更新投递进度再显示**：
   - 给了 `--outbox`（收件枢纽自己的 `bridge_outbox` 原文，读时带 `includeAcknowledged: true`，否则对方已确认的消息不会列出）时，先调用 decision-queue 的 `update_delivery`，把投递状态推到「已取走」「已确认」。
   - 读不到 agent-relay 的文件时照样显示，第一行写「⚠ 读不到 agent-relay，各线状态不全」。
6. **约定块**：`inbox convention <协作组>` 打印收件枢纽会话的约定块，用 `<!-- BEGIN decision-inbox hub -->` 和 `<!-- END decision-inbox hub -->` 包住。写进哪个文件、怎样替换，由 onboarding 负责。约定块写这几件事：
   - 被叫醒或收到 agent-relay 提醒时：`bridge_inbox` → 写文件 → `inbox receive` → 按输出发消息、`inbox sent`、`bridge_ack` → `view`，把主视图显示给用户；
   - 用户每说一句话：`bridge_agents` → 写文件；用户原话用写文件工具原样写进文件 → `inbox reply` → 按输出发消息、`inbox sent` → 显示输出；
   - 只发命令输出里的消息，加上第 4 条「改规则」那种转发（发前确认收件人），此外不给任何会话发消息；
   - 需求 4.6 的边界：转述注明「X 称」；宿主权限确认只能用户去原会话点；不替用户决定、不改写选项、不补后果、不改任何项目的文件；
   - 某一步出错时，把出错的命令和输出告诉用户，不自己补救、不改状态文件。

## 范围

做：

- `decision_inbox/hub.py`：`receive`、`reply`、`sent`、`outgoing`、`convention`；领域 `hub` 的唯一写入口。
- `__main__.py` 新增子命令 `inbox receive|reply|sent|convention`、`view`。
- relay-reader 返工：`parse_inbox`，以及按 agent-relay 0.7.0 源码字段做的样例 `tests/fixtures/relay/inbox.json`。

不做：

- 调用 agent-relay、发消息、发桌面通知（由收件枢纽会话做）。
- 写约定块进文件、登记名册（onboarding）。
- 斜杠命令和插件清单（plugin-packaging）。
- 防伪造【用户答复】（需求第 12 节第 12 项）：第一版只做到「收件枢纽不处理别人发来的【用户答复】」，开发线那边怎么防不在本模块。
- `/wake`、`/ask`（第二版）。

## 接口约定

```python
inbox = relay.parse_inbox(text)          # bridge_inbox 原文 → Inbox(agent, messages, has_more, warnings)
# InboxMessage(id, sender, body, created_at, reply_to, expects_reply, truncated, next_offset)

r = hub.receive(g, inbox, now)           # → Receipt(sends, notes, ack, unread)
r = hub.reply(g, text, now, relay=None, maps=None)  # → Reply(sends, show)
hub.sent(g, done={"out:3": 3950}, failed=["out:4"], at=now)
hub.outgoing(g)                          # 还没发出去的消息
hub.convention(group, cli="python3 -m decision_inbox")
```

`sends` 每条：`{"id": "out:3", "to": "<身份名>", "bodyFile": "<绝对路径>", "replyTo": 2950 或 null, "kind": "answer"|"return"}`。

命令行（都打印 JSON，收件枢纽照做；`show`、`notes` 原样显示给用户）：

```text
python3 -m decision_inbox inbox receive <协作组> --inbox <文件>
python3 -m decision_inbox inbox reply <协作组> --text-file <文件> [--agents <文件>] [--relay-version <版本>]
python3 -m decision_inbox inbox sent <协作组> [--done out:N=编号 ...] [--failed out:N ...]
python3 -m decision_inbox inbox convention <协作组>
python3 -m decision_inbox view <协作组> [--agents <文件>] [--outbox <文件>] [--relay-version <版本>]
python3 -m decision_inbox view <协作组> detail <编号> | waits | closed [日期] | invalidated
```

退出码：0 正常；2 参数不对、协作组不存在、`--done`/`--failed` 里有不存在的编号；3 `--inbox` 读不出或格式不对（不处理任何消息）。

## 依赖

- 本插件：message-protocol（`parse`、问题说明）、review-registry（`record_conclusion`）、decision-queue（`receive`、`on_resumed`、`interpret_reply`、`answer`、`record_sent`、`update_delivery`）、wait-tickets（`receive`、`close_answered`、`close_by_user`）、hub-view（`render` 与四种展开视图）、line-health（`assess`）、relay-reader（返工）、spec-guard-reader、group-store。
- 外部组件：agent-relay 的 `bridge_inbox`、`bridge_send`（含 `bodyFile`、`replyTo`）、`bridge_ack`、`bridge_outbox`、`bridge_agents`，都是 0.7.0 已有的接口，不缺。

## 项目结构

- `decision_inbox/hub.py`（新）
- `decision_inbox/relay.py`（加 `parse_inbox`）
- `decision_inbox/__main__.py`（加子命令）
- `tests/test_hub.py`、`tests/test_relay.py`（追加）、`tests/fixtures/relay/inbox.json`

## 命令

`python3 -m unittest discover -s tests -v`

## 代码风格

沿用现有模块：标准库、dataclass、事务里读写状态、事件名 `hub.*`。代码和注释用英文。

## 测试策略

- 单元测试：每种消息类型的分发、去重、没读全、`bridge` 通知、`reply` 的每个识别分支、`sent` 的成功和失败、没发出去的消息留存与重发、约定块的标记。
- 命令行测试：用临时协作组和样例文件跑每个子命令，检查退出码和 JSON。
- 实测（最终验收前，先问用户）：在 scratchpad 的临时协作组上，由当前会话扮演收件枢纽，给测试身份发一条【等待用户】，跑一遍收件 → 答复 → 发送 → 记账 → 主视图，并用真实的 `bridge_inbox` 返回核对 `parse_inbox`。

## 边界

- 始终：用户原话一字不改；只发命令列出的消息；退回说明只写格式问题。
- 先问：改规则的转发（发前确认收件人）。
- 绝不：替用户答复；处理别人发来的【用户答复】；读不全正文就处理；把要发的正文交给收件枢纽转写。

## 验收标准

1. 一批里有【等待用户】（合格、不合格各一）、【等待其他会话】、【已恢复】、【审查结论】、认不出的、`bridge` 通知各一条：分别入表、退回、开单、关单并结束事项、记一轮、告诉用户；`ack` 列出全部 7 条。
2. 同一批再交一次：没有新编号、没有要发的消息，`ack` 照列。
3. 正文没读全的消息不处理、不进 `ack`，输出说明怎样读全；`hasMore` 时提示再读一页。
4. 【等待用户】开头写了「结束：#旧编号」：事项入表，同时旧等待单按理由 2 关掉。
5. 【等待其他会话】缺「等什么」：退回说明列出这条问题，不开单。
6. `reply`：「12 B」生成答复，`replyTo` 为原事项编号；多线事项另给各适用会话一条；对不上的回复返回问题、不发任何消息、事项仍在待答。
7. `reply`：「12 详情」「看等待」「看已关闭」「看已关闭 2026-10-15」「看失效」「关掉 #5 已经不需要」「关掉 #12」（#12 是事项）各自得到对应的显示或问题。
8. `sent`：答复发成后事项记下发送编号；等用户答复 #12 的等待单按理由 3 关掉；正文文件保留。
9. `sent` 记为失败的、没记结果的消息留着；`view` 第一行提示没发出去；「重发」再列出它们；不存在的编号退出码 2。
10. `view --outbox`：投递状态推进到「已取走」「已确认」；`--agents` 读不出时仍显示，第一行写读不到。
11. `convention`：带 BEGIN/END 标记，含协作组名、两个流程的命令、需求 4.6 的边界和改规则的确认要求。
12. 领域 `hub` 只由 `hub.py` 写；原有子命令和测试不受影响。
13. 实测：按测试策略的实测跑通一轮，记录写进本规格的「实测记录」。

## 实测记录

2026-10-17 00:04–00:06（用户同意后做），agent-relay 0.7.0。本会话登记两个测试身份 `di-hub-probe`（收件枢纽）、`di-dev-probe`（开发线），都不绑定唤醒；scratchpad 里建临时协作组 `probe-hub`。

| 步骤 | 结果 |
|---|---|
| `di-dev-probe` 用 `bodyFile` 发【等待用户】给 `di-hub-probe` | 消息 3982 |
| `bridge_inbox` 原样写入 `io/inbox.json`，`inbox receive` | 退出码 0；入表为 #1，存下的原文与发出的正文一字不差；`ack` 为 [3982]；提示「选项 C 没写『选了会怎样』」只报一次 |
| `bridge_ack` 3982 | 已确认，剩余未读 0 |
| 用户原话「1 A」写入 `io/said.txt`，`inbox reply` | 生成 `out:1`，收件人 `di-dev-probe`，`replyTo` 3982 |
| `bridge_send` 用 `bodyFile` 和 `replyTo` 发出 | 消息 3983；`di-dev-probe` 收到的正文与文件逐字一致（70 字），`replyTo` 为 3982 |
| `inbox sent --done out:1=3983` | 退出码 0；事项记下发送编号 3983 |
| `di-dev-probe` 确认已读后，读 `bridge_outbox` 写入 `io/outbox.json`，`view --outbox` | 事项状态推进到 `acknowledged`；`store show` 一致性正常 |

实测发现：`bridge_outbox` 默认只列对方还没确认的消息，对方一确认就不再列出，事项永远到不了「已确认」。约定块改为读发件箱时带 `includeAcknowledged: true`，带上后 3983 连同 `acknowledgedAt` 列出。真实的 `bridge_inbox` 返回存为样例 `tests/fixtures/relay/real-inbox.json`，`parse_inbox` 解析无警告。

两个测试身份仍登记着，退役命令交给用户执行。

## 假设

1. `bridge_inbox` 返回 `{agent, messages: [...], hasMore, ...}`，每条消息有 `id`、`fromAgent`、`toAgent`、`body`、`createdAt`、`replyTo`、`expectsReply`，正文没读全时带 `bodyTruncated` 和 `nextOffset`（读自 0.7.0 源码；2026-10-17 实测核对一致，另有 `count`、`totalUnread`，本模块不用）。
2. `bridge_send` 的 `bodyFile` 只接受本人拥有的普通文件、最大 256 KiB；协作组目录在用户主目录下，满足条件。
3. 事项、等待单共用一套编号，所以「关掉 #N」能分清 N 是事项还是等待单。

## 未决问题

无。

## 文档建议

无：本模块的用法会写进约定块；README 在 plugin-packaging 统一写。
