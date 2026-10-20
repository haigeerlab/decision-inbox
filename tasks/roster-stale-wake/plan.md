<!-- spec-guard: review approved -->

# Implementation Plan: roster-stale-wake

> 依据：`spec/roster-stale-wake.md`。任务清单：`tasks/roster-stale-wake/todo.md`。分支 `claude/relaxed-greider-5943d6`（从 main 6511882）。

需要的外部条件：无。

## Overview

先写核对函数，再接到巡视、停滞询问和主视图上，最后升版本、写 README。Task 1～3 每条修复都先写一条在 6511882 上失败的测试。做完后做最终验收，再开 PR（base main，由用户合并）。不打标签，不在本机安装或升级。

## Architecture Decisions

- `relay.AgentFact` 新增字段 `session_id: str | None = None`（放在末尾、带默认值，现有构造处不用改）。`desktop.Session` 新增 `claude_id: str | None = None`，同样放在末尾。
- `desktop.Holder`（frozen dataclass）：`state`（`ok`／`stale`／`unknown`），`session`（已知的实际持有者 `local_…` 编号，或 None）。`desktop.holders(g, relay, sessions)` 只对 `host == "claude-desktop"`、记了 `desktopSession`、没离开的成员给结果；relay 或 sessions 为 None 时返回空 dict，调用方按「判不出」处理。
- `desktop.link(entry, holders)`：没有结果、`ok`、`unknown` 时返回名册的 `desktopSession`；`stale` 时返回 `holder.session`，可能为 None。所有改动都只经这一个入口，旧行为留在「没结果」这条路上。
- `patrol.plan` 在 `_Context` 上挂 `holders`。`_wake` 改用 `link`；返回 None 时不发唤醒，名册过期通知照发。新函数 `_stale_notices(ctx)` 为每个过期成员发通知，键为 `stale:<邮箱名>|<持有者或 ?>`。`_wake_hub` 改用 `link`。
- `stall.asks(..., holders=None)` 和 `stall.overdue_rows(..., holders=None)` 都多收一个可选参数，现有调用不传时行为不变。`hub.main_view` 在 `sessions` 和 `relay` 都在时算一次 holders，传给 `overdue_rows`，并在开头加名册过期行（放在巡视警报之后）。

## Task List

- **Task 1 读出持有者并核对名册**（Spec 要做的 1、2，验收 6）：
  - `tests/test_relay.py`：`host.sessionId` 和 `wake.sessionId` 都能读出来，`host` 优先。
  - `tests/test_desktop.py`：`sessionId` 读进 `claude_id`；`holders` 的四种结果（一致、不一致且持有者在运行、只有旧会话在运行、两边都不在），以及没带 sessions 时返回空。`link`／`stale_text` 的输出。
  - `tests/test_onboard.py`：重新 join 传入新编号后，名册换成新编号，核对结果为 `ok`。这条测的是现有行为，改前就该通过，交付时注明。
- **Task 2 巡视唤醒实际持有者**（要做的 3，验收 1～3）：`tests/test_patrol.py` 新类 `RosterStaleTest`，重放 di-p0：名册是 `local_OLD`，持有者 `NEW-ID` 空闲、有 3 条消息等了 6 分钟，sessions 里有 `NEW-ID → local_NEW`。断言：
  - `wake:rh2-coord` 的目标是 `local_NEW`；所有动作的目标和文字都不含 `local_OLD`；有一条 `notify:stale:…`，文字含「名册过期：并行协调2 的邮箱名已由新会话持有，请在新会话重跑 join」。
  - 下一轮 5 分钟后还没读：「叫不醒」通知里的链接是 `local_NEW`。
  - 只有旧会话在运行时：不发唤醒，通知里不含 `local_OLD`。
  - 收件箱名册过期时，`_wake_hub` 也唤醒新会话。
  - 名册和持有者一致时没有名册过期通知；现有的巡视测试全部不改、照样通过。
  - 另加一条命令行测试：`patrol plan --sessions` 把 sessions 传了进去。
- **Task 3 停滞询问与主视图**（要做的 3 的停滞部分和 4，验收 4、5）：
  - `tests/test_stall.py`：过期且持有者已知时，`asks` 发 `wake` 给 `local_NEW`；持有者未知时改为 `owner-alert` 发给邮箱名；`overdue_rows` 的链接是 `local_NEW`，持有者未知时写「去新会话处理（名册过期，编号未知）」。
  - `tests/test_hub.py`：`main_view` 带 relay 和 sessions、名册过期时，开头有名册过期行和 `local_NEW` 链接。
  - `patrol.plan` 把 holders 传给 `stall.asks`。
  - 全量 `PYTHONPATH=tests:. python3 -m unittest discover -s tests` 通过。
- **Task 4 版本 0.0.35 与 README 升级步骤**（做／不做 里的版本和文档）：
  - `.claude-plugin/plugin.json`、`.codex-plugin/plugin.json` 改为 0.0.35，`tests/test_packaging.py` 的版本断言跟着改。
  - README「升级」一节加 0.0.35：这一版包括 rules-dir-guard（#53）、hub-stop-scope（#54）和本修复。写清哪些会话要重开（先核对停止钩子是否在会话开始时加载，按核对结果写）；协作规则段没改，不用重跑 join 或 hub-setup；用 `bridge_register` 接管过邮箱名的会话，要在新会话里重跑 join（di-p0 这次是 rh2-coord 和 di-p0-owner）。
  - README 的排查表加一行：主视图或通知报「名册过期」时该怎么做。
  - `test_packaging` 里 README 必须出现的短语加上「0.0.35」那一段。

## Checkpoint（gate）：模块最终验收

- 列出实际改动的文件（新增、修改、行数，取自版本库）和测试数。
- 在临时组里重放 di-p0 的场景：给你看 `patrol plan` 的 actions，以及 `view` 开头的名册过期行。
- 批准后开 PR（base main，由用户合并）；合并后把版本号和升级步骤抄送接入协调会话 local_4f410de8。
- 不改界面，没有 UI 自验（主视图是命令输出，用重放结果对照）。

## 风险

| 风险 | 对策 |
|---|---|
| 改 `_wake` 影响现有唤醒路径 | 没有 holders 结果时走原逻辑；现有巡视测试不改，全部通过才算 |
| 测试读到本机真实的 `~/.decision-inbox` | 沿用 `TempHomeTestCase` |
| 「哪些会话要重开」写错 | Task 4 先读 hooks 配置和 install 的 shim 刷新逻辑，按代码写，不凭印象 |
