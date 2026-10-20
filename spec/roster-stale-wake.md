<!-- spec-guard: review approved c1b173653ee4 -->

# Spec: roster-stale-wake

> 能力图模块 `roster-stale-wake`（2026-10-20 用户确认插入，排在 hub-stop-scope 之后）。来源：决定 73（「按推荐，停大测试，修两处后短验证」），接入协调转来的 O-roster-stale-wake。

## 目标

巡视的唤醒、桌面通知和主视图里的会话链接，不再只信名册的 `desktopSession`：先用 agent-relay 的实际绑定核对这个邮箱名现在由哪个会话持有。名册过期时，唤醒实际持有者，不再指向旧会话，并告诉用户「名册过期，请在新会话重跑 join」。

## 现状（2026-10-20 只读核对）

- di-p0 的名册里，rh2-coord 的 `desktopSession` 还是旧的 `local_307bc55e…`，di-p0-owner 还是旧的 `local_dd0bf7d3…`。新会话（`local_cb182a33…`、`local_f96586b6…`）已经用 `bridge_register` 接管了这两个邮箱名，但没有重跑 join。
- 后果：巡视按名册唤醒旧会话，03:27 的桌面通知让用户去打开旧的「并行协调2」；用户 11:28 答的 #69～#71 转给了 rh2-coord，邮件进了邮箱，新会话却一直空闲没读，巡视的「空闲积压」唤醒发给了旧会话。
- 重新 join 本来就会更新名册：`onboard._commit` 遇到同名邮箱会 `replace_session`，`desktopSession` 换成新传入的值。
- `bridge_agents` 每个邮箱名带 `host.sessionId` 和 `wake.sessionId`（宿主内部的会话 id，比如 `0f36d94f…`）；`relay.parse_agents` 现在没读这两个字段。
- `bridge_sessions` 的 `claude` 列表每行有 `sessionId`（宿主内部 id）和 `hostSessionId`（桌面版 `local_…` 编号）；`desktop.parse_sessions` 读了 `hostSessionId`，没读 `sessionId`。这份列表只包含**正在运行**的 Claude 会话。
- 读 `desktopSession` 拿来唤醒或做链接的地方：`patrol._wake`（唤醒目标，以及「叫不醒，请手动打开」通知里的链接；`_wakes`、`_offline_mail`、`_handoffs` 都走它）、`patrol._wake_hub`、`stall.asks`（停滞询问的唤醒目标）、`stall.overdue_rows`（主视图「请去处理」的链接）。

## 假设（用户 2026-10-20 已确认）

1. **判断规则**。对名册里 `host` 为 `claude-desktop`、记了 `desktopSession` 的成员，取 `bridge_agents` 里这个邮箱名的持有者 id（优先 `host.sessionId`，没有时取 `wake.sessionId`），再到 `bridge_sessions` 的对照表里查它的 `local_…` 编号：
   - 查到了：和名册一致算**正常**；不一致算**过期**，实际持有者就是查到的编号。
   - 查不到（持有者没在运行），但名册里的那个旧会话在运行，而且它的 `sessionId` 不是持有者 id：算**过期**，实际持有者未知。
   - 其余情况（没带 agents 或 sessions、邮箱名没有持有者 id、两边都没在运行）算**判不出**，沿用现在的做法，按名册处理。
2. **过期、实际持有者已知**：唤醒、停滞询问、「叫不醒，请手动打开」通知和主视图「请去处理」里的链接，都改用实际持有者的编号；另外每个过期的邮箱名报一次「名册过期：<线名> 的邮箱名已由新会话持有，请在新会话重跑 join」：通知发一次，主视图每次都显示。
3. **过期、实际持有者未知**：不发指向旧会话的唤醒，「叫不醒」通知也不带旧链接。停滞询问改用 agent-relay 邮件（`owner-alert`）发给这个邮箱名，谁持有就由谁收；同样报名册过期。
4. **只读校正，不改名册**。巡视和主视图不写名册，名册只在 join 时写。不读桌面版 App 的内部会话文件来补「两边都没在运行」的盲区。

## 要做的

### 1. 读出持有者 id 和对照表

- `relay.AgentFact` 加 `session_id`：`host.sessionId`，没有时取 `wake.sessionId`，都没有时为 None。
- `desktop.Session` 加 `claude_id`：`bridge_sessions` 那一行的 `sessionId`。

### 2. 核对名册（新函数，放在 `desktop.py`）

`desktop.holders(g, relay, sessions) -> dict[relayName, Holder]`，按假设 1 给出每个成员的状态（`ok`／`stale`／`unknown`），以及实际持有者的 `local_…` 编号（已知时）。另外提供两个小工具给调用方：
- `link(entry, holders)`：唤醒或做链接时该用的编号。正常或判不出时用名册的值；过期且持有者已知时用持有者；过期且持有者未知时返回 None。
- `stale_text(entry)`：「名册过期：<线名> 的邮箱名已由新会话持有，请在新会话重跑 join」。

### 3. 巡视用核对结果

`patrol.plan` 开头算一次 holders：
- `_wake`、`_wake_hub` 的唤醒目标和「叫不醒」链接改用 `link(...)`。返回 None 时不发唤醒，只发名册过期通知。
- 每个过期的邮箱名通知一次（键 `stale:<邮箱名>|<持有者或 ?>`），持有者变了会再通知一次。
- `stall.asks` 多收一个 holders 参数：`link(...)` 有值时发 `wake` 给它，None 时改为 `owner-alert` 发给邮箱名。

### 4. 主视图

- `hub.main_view` 在开头几行里，为每个过期的邮箱名加一行 `⚠ 名册过期：…`，持有者已知时附上它的链接。
- `stall.overdue_rows` 的「打开 …」链接改用 `link(...)`；为 None 时写「去新会话处理（名册过期，编号未知）」。

### 5. 回归测试

每条修复先有一条失败的测试（见验收）。另补一条：重新 join 时，名册的 `desktopSession` 换成新编号（现有行为，防回退）。

## 做 / 不做

- 做：上面 1～5；版本号升到 0.0.35（这一版同时带上 #53、#54），README 写升级步骤。
- 不做：巡视自动改名册；读桌面版 App 的内部会话文件；改「去原会话确认」卡片（`view._confirm_card`）里的链接和 `desktop._owner` 按链接认会话（这两处拿不到 sessions，名册过期行就在主视图开头，会指出新会话）；在本机安装或升级；打标签。

## 验收标准

1. **重放 di-p0 的场景**：名册里 rh2-coord 的 `desktopSession` 是 `local_OLD`；`bridge_agents` 里 rh2-coord 的 `host.sessionId` 是 `NEW-ID`，空闲、有 3 条消息等了 5 分钟以上；`bridge_sessions` 里 `NEW-ID → local_NEW`。`patrol plan` 的唤醒目标是 `local_NEW`，计划里没有任何动作的目标或文字含 `local_OLD`，并有一条名册过期通知。
2. 同上，但 `bridge_sessions` 里只有旧会话 `OLD-ID → local_OLD` 在运行：不发唤醒；通知是名册过期，不含 `local_OLD`。
3. 名册和持有者一致、两边都没在运行、没带 sessions：行为和改前一样（现有巡视测试全部通过）。
4. 停滞询问：过期且持有者已知时，`wake` 发给 `local_NEW`；持有者未知时，改为 `owner-alert` 发给邮箱名。
5. `decision-inbox view` 带 `--agents`、`--sessions`，名册过期时，开头有「名册过期：并行协调2 的邮箱名已由新会话持有，请在新会话重跑 join」和 `local_NEW` 的链接；「请去处理」的链接也是 `local_NEW`。
6. 重新 join 传入新编号后，名册的 `desktopSession` 是新编号，之后的核对结果为正常。
7. 每条修复先有一条失败的测试；全量 `PYTHONPATH=tests:. python3 -m unittest discover -s tests` 通过。

## 风险

- **盲区**：新旧会话都没在运行时判不出，仍按名册唤醒旧会话。被唤醒的旧会话不持有邮箱名，读不到消息；用户点开后看到的是旧会话。只有新会话重跑 join 才能根治，所以名册过期提示里写明「请在新会话重跑 join」。
- `bridge_agents` 的 `host.sessionId` 和 `bridge_sessions` 的 `sessionId` 是 agent-relay 0.9.0 现有的字段（本机 2026-10-20 实测）。将来字段没了会退回「判不出」，不会误报过期。

## 文档建议

README 加 0.0.35 的升级步骤：哪些会话要重开、要不要重跑 join 或 hub-setup，以及「用 bridge_register 接管邮箱名后要在新会话重跑 join」。
