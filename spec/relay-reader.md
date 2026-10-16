<!-- spec-guard: review approved 119c3ffc42f6 -->
# Spec: relay-reader

> 能力图模块 `relay-reader`。需求来源：`docs/requirements-record.md` 第 1.4、4.5、8.1、8.3、8.5、10.2 节，第 12 节第 15 项。
> agent-relay 接口依据：agent-relay 仓库 `v0.6.10` 标签下的 `docs/collaboration-interface.md` 第 2.1、5 节（接口 2.x），字段名以同一标签下 `plugins/agent-relay/bridge/src/server.ts`、`bridge-store.ts` 为准。

## 目标

把 agent-relay 给出的事实整理成本插件统一使用的只读数据，供后面的模块使用：
- 每个联调身份的在线状态、未读数、等待中的消息（几条、谁发的、最早一条几点）、最近活动和唤醒绑定；
- 某个身份发出的消息的投递事实：投递状态、何时确认、有没有回复、何时过期。

后面的 wait-tickets（对方离线标记）、line-health（信号 1、2、4、5、10）、stop-hook（我有没有未处理的消息）、query-commands（`/item` 时间线）都只通过本模块拿 agent-relay 的数据，不各自解析。

本模块只读：不发消息、不确认、不记已读、不唤醒、不改 agent-relay 的任何状态。

## 已定事项（用户 2026-10-16 确认）

1. **第 12 节第 15 项：要求 agent-relay ≥ 0.6.10（接口 2.x）。** 0.6.10 已于 2026-10-16 发布，`bridge_agents` 的 `waiting` 已覆盖 Claude 会话并带 `oldestAt`。版本更低时明确报「agent-relay 需升级到 0.6.10」，涉及 Claude 会话积压的字段给「未知」，不为旧版做兼容判断。
2. **取数方式：请 agent-relay 增加只读命令行入口。** 停止钩子和巡视脚本是 Python 进程，调不了 MCP 工具；直接读信箱的 SQLite 会绕开它承诺稳定的接口。所以向 agent-relay 提需求（见「对 agent-relay 的需求」），在它做好之前，由 Claude 会话（收件枢纽或定时巡视任务）调用 MCP 工具，把返回的 JSON 原文交给本模块解析。

## 范围

**范围内**

- 解析 `bridge_agents` 的返回 JSON，得到「身份快照」。
- 解析 `bridge_outbox` 的返回 JSON，得到「发出消息的投递记录」。
- 判断 agent-relay 版本够不够（规则见「版本判定」）。
- 在线状态归类：保留原值，另给一个归类，供显示和信号使用。
- 丢弃消息正文：输入里即使带正文或预览，输出也不保留。

**范围外**

- 调用 MCP 工具：由会话自己调用，本模块只接收原文。
- 调用 agent-relay 的只读命令行：这个命令还不存在，等它发布后作为本模块的返工任务追加，届时按它的契约再审一次。
- `bridge_inbox`、`bridge_thread`：收件枢纽收单要读正文，那是 decision-queue 的事，它直接用 MCP 工具；本模块不碰正文。
- 把快照存进状态文件、判断「卡住」、显示：分别属于下游模块。

## 关键决策与取舍（请重点审）

1. **输入是原文，不是已解析的对象。** 入口只收 MCP 工具返回的 JSON 文本，在本模块统一解析和校验。这样会话转交时不经手改写，也能用真实返回原文做测试夹具。
2. **版本判定只认证据，不猜。** `bridge_agents` 的返回里没有版本号，所以按下面的顺序判定：
   - 调用方显式给了 agent-relay 版本：以它为准。
   - 返回里任何一个 `waiting` 带 `oldestAt`：只有 0.6.10 及以上才会这样，判定为够新。
   - 以上都不成立：版本「未定」。这时 Codex 身份没有 `waiting` 记为 0（接口 1.3 起就保证）；Claude 身份的等待数记为「未知」，不记为 0。0.6.10 里只要有任何身份有积压就会带 `oldestAt`，所以「未定」只会出现在全组没有任何积压的时候。
   - 显式给出的版本低于 0.6.10：判定为过旧，给出诊断「agent-relay 需升级到 0.6.10」。
   - 不能用「`unread` 大于 0 却没有 `waiting`」推断过旧：0.6.10 的 `unread` 还计入广播和投递失败的消息，`waiting` 不计，这种组合在新版里也会出现（源码 `bridge-store.ts` 的 `UNREAD_FOR` 与 `waiting()`）。
3. **在线状态保留原值，另给归类。** 原值照抄，以便将来 agent-relay 新增取值时不丢信息。归类只有五种，未来新出现的值一律归为「未知」：

   | 原值 | 归类 |
   |---|---|
   | `running` | `active` 在运行 |
   | `waiting-input`、`waiting-approval` | `needs-user` 在等用户 |
   | `stopped` | `offline` 已停止 |
   | `unreachable` | `unreachable` 在运行但连不上 |
   | `unknown`、缺省、其他任何值 | `unknown` 未知 |

4. **单个条目缺关键字段只跳过并警告，整体结构坏了才报错。** 某个身份缺 `name`、某条消息缺 `id`：跳过这一条并给警告，其余照常。顶层不是 JSON、`bridge_agents` 原文没有 `agents` 数组或 `bridge_outbox` 原文没有 `entries` 数组：报错，不返回半份结果。
5. **时间保持原值。** agent-relay 给的是 UTC 的 ISO 8601（以 `Z` 结尾），本模块原样保留，不换算时区；需要比较先后时按绝对时间比，换成本机时区显示是显示层的事。

## 接口约定

### Python 接口

```python
from decision_inbox import relay

snap = relay.parse_agents(text, relay_version=None)   # text：bridge_agents 返回的 JSON 原文
snap.relay_status        # "ok" | "too-old" | "undetermined"
snap.warnings            # 跳过的条目、版本诊断等，中文
snap.agents["fe-codex"]  # AgentFact

out = relay.parse_outbox(text, sender="hub-claude")   # bridge_outbox 返回的 JSON 原文
out.messages[0]          # MessageFact
```

```python
@dataclass(frozen=True)
class AgentFact:
    name: str
    host_app: str | None          # "claude" | "codex" | None（没记录宿主）
    presence_raw: str | None      # 原值，例如 "waiting-approval"
    presence: str                 # active | needs-user | offline | unreachable | unknown
    presence_since: str | None
    unread: int | None
    waiting_count: int | None     # None = 未知（见关键决策 2）
    waiting_from: tuple[str, ...]
    waiting_ids: tuple[int, ...]  # 最多 20 个，最早的在前
    waiting_oldest_at: str | None
    last_activity_at: str | None
    wake_bound: bool | None
    retired: bool
    presence_detail: str | None = None   # presence.detail 原文，例如 "permission prompt"；缺失或空串为 None（hub-view 的「等你确认」卡片用）

@dataclass(frozen=True)
class MessageFact:
    id: int
    sender: str
    recipient: str
    sent_at: str | None
    delivery_state: str | None    # queued | sending | accepted | failed | unknown | expired，原值照抄；accepted 表示收件方已取走
    acknowledged_at: str | None
    expires_at: str | None
    reply_ids: tuple[int, ...]
    reply_to: int | None
```

- 输出里没有任何正文、预览或主题字段（`bridge_outbox` 的 `preview` 是正文前 200 字，一律丢弃）。
- `bridge_outbox` 不给已读时间；需要「何时取走」的追溯，以 `delivery_state` 为准，不另造字段。
- 不认识的字段一律忽略，不报错（接口 2.x 只增不改）。
- 字段名到 agent-relay 原字段的对应关系，以计划阶段采集的真实返回原文为准，写进测试夹具；与接口文档不一致时，以真实返回为准并在计划里注明。

### 对 agent-relay 的需求（由用户转给 agent-relay 的维护会话）

请 agent-relay 增加一个**只读**命令行入口，例如 `agent_relay_read.py agents --json` 与 `agent_relay_read.py outbox --agent <名字> --json`：

1. 输出字段与 `bridge_agents`、`bridge_outbox` 相同，并纳入接口 2.x 的稳定性承诺；
2. 顶层带 `relayVersion` 与 `interfaceVersion`；
3. 不需要 MCP 会话，不记已读、不确认、不唤醒，不写任何文件；
4. 不输出消息正文；
5. 退出码区分：成功、运行时未安装或版本过旧、信箱读不出；
6. `--json` 时 stdout 只有一个 JSON 对象，说明走 stderr。

## 项目结构

```text
decision_inbox/relay.py          本模块
tests/test_relay.py              单元测试
tests/fixtures/relay/*.json      bridge_agents、bridge_outbox 的返回原文（真实采集＋构造）
```

## 命令

```bash
python3 -m unittest discover -s tests -v
```

## 代码风格

沿用 group-store：只用标准库，代码与注释用英文，给用户看的诊断用中文；结果用 `@dataclass(frozen=True)`，解析失败抛 `RelayDataError`（继承 `ValueError`）。

## 测试策略

- 夹具分两类：
  - **真实采集**：在本机 agent-relay 升级到 0.6.10 后，由会话调用 `bridge_agents` 与 `bridge_outbox` 得到原文。采集前先去掉正文；不放与本项目无关的身份名。
  - **构造**：覆盖旧版、缺字段、未知状态值、超过 20 条积压等真实环境难以凑出的情况。
- 每条验收标准至少一个测试。

## 边界

- **始终**：只读；丢弃正文；不认识的字段与取值保留原值或归为「未知」，不猜。
- **先问**：把 `bridge_inbox` 或 `bridge_thread` 纳入本模块；直接读信箱 SQLite；为 0.6.10 以下版本做兼容。
- **绝不**：调用任何会改 agent-relay 状态的工具（发、确认、登记、唤醒）；把消息正文写进输出、日志或状态文件。

## 验收标准

1. 0.6.10 的 `bridge_agents` 原文（含一个有积压的 Claude 身份，带 `oldestAt`）：`relay_status` 为 `ok`；该身份的 `waiting_count`、`waiting_from`、`waiting_ids`、`waiting_oldest_at` 与原文一致。
2. 显式给出 `relay_version="0.6.1"`：`relay_status` 为 `too-old`，`warnings` 含「agent-relay 需升级到 0.6.10」，所有 Claude 身份的 `waiting_count` 为 `None`。另一份 0.6.10 原文里，某个 Claude 身份 `unread: 2`（广播）却没有 `waiting`、其他身份带 `oldestAt`：判为 `ok`，该身份 `waiting_count` 为 0，不误报过旧。
3. 没有任何积压、也没有显式版本：`relay_status` 为 `undetermined`；Codex 身份 `waiting_count` 为 0，Claude 身份为 `None`。同一份原文加上 `relay_version="0.6.10"` 后：Claude 身份为 0，`relay_status` 为 `ok`。
4. 在线状态：`running`、`waiting-input`、`waiting-approval`、`stopped`、`unreachable`、`unknown`、缺省、`something-new` 分别归类为 active、needs-user、needs-user、offline、unreachable、unknown、unknown、unknown；`presence_raw` 保留原值；`presence_detail` 取 `presence.detail`，缺失或空串为 None。
5. 原文里带 `body`、`preview` 等正文字段：输出对象及其 `repr` 都不含正文内容。
6. 某个身份缺 `name`：跳过它并给一条警告，其余身份照常；顶层不是合法 JSON 或缺 `agents` 数组：抛 `RelayDataError`。
7. `bridge_outbox` 原文：每条消息的 `delivery_state`、`acknowledged_at`、`expires_at`、`reply_to`、回复编号与原文一致；`sender` 取调用时给的身份名；`preview` 的内容不出现在输出里。
8. 已退役的身份（`includeRetired` 时出现）`retired` 为真，不计入任何积压。
9. 测试中扫描断言：`relay.py` 不 import 任何网络或子进程模块（`socket`、`subprocess`、`urllib`、`http`）。

## 假设

1. `bridge_agents` 与 `bridge_outbox` 的返回是 JSON 文本，形状以接口文档第 2.1 节和 agent-relay 自己的测试为准；计划阶段用真实原文核对，不一致时以真实原文为准并在计划里注明。
2. 采集真实原文要先把本机 agent-relay 升级到 0.6.10，这一步由你按它的升级说明亲自执行。升级前先用构造夹具开发，真实夹具作为计划里的一个检查点。

## 未决问题

无。原第 1 项（对 agent-relay 的需求怎么交付）已由用户 2026-10-16 定：由用户转给 agent-relay 的维护会话。

## 文档建议

无。本模块对下游的接口已写在「接口约定」；对 agent-relay 的需求写在本 Spec 里，由用户转交。
