<!-- spec-guard: review approved -->

# Implementation Plan: go-to-session

> 依据：`spec/go-to-session.md`（用户 2026-10-19 批准）。任务清单：`tasks/go-to-session/todo.md`。分支 `claude/go-to-session`（从 main 开出，main 已含 scope-authority-defaults）。

## Overview

四个任务，各自先写失败的测试再改：契约 v2.2 解析、事项入库与回复结项、主视图一栏与兜底、规则段与文档。最后做一次最终验收。不升版本号（R21 的模块做完再一起发版）。

## Architecture Decisions

- **契约**：`CONTRACT_VERSION` 改 `"2.2"`；从 session-protocol 仓库 f5bc04e 复制 `fixtures/` 全部到 `tests/fixtures/session-protocol/v2.2/`，删掉 `v2.1/`；`SHA256SUMS` 测试保证逐字。`protocol.FIELDS["wait-user"]` 加「类型」与配套字段（插在「要点」之后），`Message` 加 `wait_kind: str | None`、`go_to_session: dict | None`；`to_contract` 只在样例期望里有这两个键时输出，和现有 v2.1 字段的做法一致。样例数和问题代码以契约为准，对不上就停下来报契约负责人。
- **事项**：`items._record` 加 `waitKind`、`goToSession`。`items.pending` 照旧包含它（编号、历史、查询都不变），渲染层按 `waitKind` 分流。
- **回复**：`hub.reply` 在 `items.answer` 之前把答到去会话操作事项的部分挑出来，不转发，回复里加说明；其余照常。
- **结项**：`items.on_resumed` 对 `waitKind == "go-to-session"` 的事项允许从 pending 直接关。
- **主视图**：`hub.main_view` 的 head 在巡视告警之后插入「要你去会话里操作」一栏（新函数 `view.go_to_session_rows(g, now, relay)`）；`view.render` 的普通卡片跳过这类事项。兜底行由同一个函数按 relay 快照里 Claude 线的 `waiting-approval` 生成。
- **规则段**：`onboard._COMMON` 加一节「停在宿主确认上」，含格式示例；`join` 的 warnings 加说明行。

## Task List

- **Task 1 契约 v2.2 解析**（Spec 验收 1）：先复制样例、改版本号，跑 `test_contract` 看哪些失败；再改 `protocol.parse` 与 `to_contract` 到全绿。
- **Task 2 事项入库、回复与结项**（Spec 验收 5、6）：先写测试：入库字段；回「N A」不出消息、回复含说明；混答普通事项照常转发；发起方【已恢复】关掉、别人发的不算。再改 `items`、`hub.reply`。
- **Task 3 主视图一栏与兜底**（Spec 验收 2、3、4、7）：先写测试：Claude 链接两种写法、Codex 写法、关联事项一行、无选项、普通卡片不出现、30 分钟前后、兜底行出现与不重复。再改 `view`、`hub.main_view`。改完用临时组实跑一次主视图，贴出这一栏的样子。
- **Task 4 规则段、接入预览与文档**（Spec 验收 8、9）：先写测试：三种角色规则段含新一节与示例、接入预览有说明行、README 断言。再改 `onboard`、README（主视图、消息协议、接入、升级）。跑旧称扫描和全量测试。

## Checkpoint（gate）：模块最终验收

列出改动的文件、每条验收标准的证据和测试数，然后开 PR（base main）。

## 影响面

- 解析器（所有【等待用户】）、主视图顶部、回复处理、【已恢复】结项；
- 协作规则段（已接入的线重跑接入才生效，和 scope-authority-defaults 一起在发版时说明）；
- 契约钉 2.2：module-crew 仍是 2.x 就兼容。

## 风险

| 风险 | 对策 |
|---|---|
| 升契约后旧样例的期望变了 | 契约负责人说已有样例零改动；Task 1 先跑测试看清，对不上就停下来报契约负责人 |
| 回复拦截误伤普通事项 | 测试覆盖同一句混答；只拦 `waitKind` 为去会话操作的编号 |
| 主视图顶部太挤 | 每项最多 5 行；兜底行一行 |
