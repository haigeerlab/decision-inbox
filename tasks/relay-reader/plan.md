<!-- spec-guard: review approved -->
# Implementation Plan: relay-reader

> 依据：`spec/relay-reader.md`（已批准）。任务清单：`tasks/relay-reader/todo.md`。
> 字段依据：agent-relay `v0.6.10` 标签下的 `plugins/agent-relay/bridge/src/server.ts`（`bridge_agents`、`bridge_outbox` 的输出）与 `bridge-store.ts`（`AgentSummary`、`OutboxEntry`、`waiting()`）。

## Overview

先用照源码构造的夹具把两个解析函数和版本判定做完（任务 1～3），再停在一个 gate：请你把本机 agent-relay 升级到 0.6.10，并允许我调用 `bridge_agents`、`bridge_outbox` 采集真实原文。采集、脱敏、给你过目后，用真实原文补测试并修正差异（任务 4），最后验收。

## Architecture Decisions

- 全部逻辑在 `decision_inbox/relay.py`，不依赖 `store.py`（能力图上本模块无依赖）。
- 字段对应（源码 → 本模块）：
  - `bridge_agents`：顶层 `{count, agents[]}`；每项 `name`、`host`（`{app, sessionId, verified}` 或 null）、`unread`、`lastActivity`、`retiredAt`、`presence`（`{state, since?, detail?}`，退役身份没有）、`wake`（绑定目标或 null）、`waiting`（`{count, from, ids, oldestAt}`，没有积压时不出现）。
  - `bridge_outbox`：顶层 `{agent, totalUnacknowledged, hasMore, entries[]}`；每项 `id`、`toAgent`、`createdAt`、`acknowledgedAt`、`deliveryState`、`expiresAt`、`replyTo`、`replies`；`preview`、`bodyLength`、`threadId`、`wake`、`recipient` 不进输出。
- 版本比较只比较 `主.次.修订` 三段整数；给出的版本号不是这种形状时当作没给，并加一条警告。
- 采集真实原文时，先在内存里脱敏，再写盘：身份名换成 `agent-1`、`agent-2`……（保持同一名字映射一致），`sessionId` 换成占位符，`preview` 删掉。脱敏后的夹具先给你看，再提交。

## 影响面

新增：`decision_inbox/relay.py`、`tests/test_relay.py`、`tests/fixtures/relay/` 下若干 JSON 夹具。修改：`tasks/relay-reader/todo.md`（勾选）、`.agent/state.json`（最终验收时切换当前模块）。不改其他已有文件，不涉及用户可见界面，不需要 UI 验证。

## Task List

### Phase 1：构造夹具

- [ ] Task 1：`parse_agents` 基础解析（Spec 验收 4、5、6、8、9）
- [ ] Task 2：版本判定（Spec 验收 1、2、3）
- [ ] Task 3：`parse_outbox`（Spec 验收 5 的发件部分、7）

### Checkpoint 1（report）

- [ ] 全部测试全绿

### Checkpoint 2（gate）：采集真实原文前

- [ ] 停下请你：① 按 agent-relay 0.6.10 的升级说明升级本机运行时（这一步只能你做）；② 允许我调用 `bridge_agents` 与 `bridge_outbox`（只读）采集原文。没有升级就不进入任务 4。

### Phase 2：真实原文核对

- [ ] Task 4：采集、脱敏、给你过目后存为夹具，补测试；与构造夹具有差异时修正解析并在本计划末尾记一笔

### Checkpoint 3（gate）：模块最终验收

- [ ] 全部测试全绿；9 条验收标准逐条对应测试；列出实际改动的文件
- [ ] 本 Plan 获批即授权：每个任务完成后在当前分支做一次本地提交；不授权推送、不授权开 PR

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| 真实原文与源码推出的形状不一致（例如 MCP 外层再包一层） | 中 | 任务 4 专门核对；入口只收工具返回的 JSON 正文，外层包装由会话剥掉，计划里写清 |
| 夹具泄露其他项目的身份名、会话 id 或正文 | 高 | 落盘前脱敏；提交前给你过目；测试扫描夹具不含 `preview` 键 |
| 你暂时不升级 agent-relay | 中 | 任务 1～3 不依赖升级；停在 Checkpoint 2，不跳过真实核对 |

## Open Questions

无。
