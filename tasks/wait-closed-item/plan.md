<!-- spec-guard: review approved -->

# Implementation Plan: wait-closed-item

> 依据：`spec/wait-closed-item.md`（用户 2026-10-19 批准，D1 A：「所等的 #N 已结项」只标可能已失效，不自动关）。任务清单：`tasks/wait-closed-item/todo.md`。分支 `claude/i11-stale-wait`（从 main a0790f0 开出）。

需要的外部条件：无。

## Overview

两个任务，各自先写在 a0790f0 上失败的测试再改：先统一「在等用户」的认定（自动关闭跟着生效），再给「可能已失效」加「所等的 #N 已结项」这个来源。最后最终验收，然后发 0.0.30。

## Architecture Decisions

- `tickets.waits_on_user(g, target) -> bool`：先按原样在名册里找线（找到就不是等用户）；再去掉末尾全角或半角括号说明，等于 `USER_TARGETS` 之一、或等于名册里收件箱会话的线名／邮箱名，就是等用户。`USER_TARGETS` 保留（其他插件或旧数据可能读它），比对处全部改调这个函数：`tickets.receive`、`tickets.close_answered`、`view._push_line`、`mapview`、`query` 三处。
- `tickets.stale_reasons(g) -> {等待记录号: ("later", 消息号) | ("closed", 待决事项号)}`：在现有「之后又发过消息」（仍跳过模块协调）之外，加「等什么里写的 #N 是这个发送方自己的待决事项且已结项（closed、superseded、withdrawn）」，不跳过模块协调；两者都有时取 closed。`stale_tickets` 保留原签名（只含 later）给旧调用方；`health.assess`、主视图页脚「其中 N 条可能已失效」、`query stats` 的计数都改用 `stale_reasons`，于是线状态、全线互等、主视图「全线停住」都不再算它，计数也对得上。
- `TicketView` 加 `stale_item`；「看等待」按来源写两种说法（Spec 要做的 2）。

## Task List

- **Task 1 统一「在等用户」**（Spec 要做的 1；验收 1、2、5）：先写 `tests/test_tickets.py` 用例（四种写法认作等用户、「前端（fe）」仍找线；带括号写法收件不提示不在名册；答复发成功后理由 3 自动关、没发成不关）。再改 `tickets.py` 和各比对处。
- **Task 2 可能已失效：所等的 #N 已结项**（Spec 要做的 2、3；验收 3、4）：先写 `tests/test_tickets.py`、`tests/test_view.py`、`tests/test_health.py` 用例（模块协调点名的 #N 结束／取代／撤回 → 标；#N 还待答 → 不标；用 W8738／#47 的真实文本造主视图不出「全线停住…卡在决策收件箱」；「看等待」写法）。再改 `tickets.py`、`health.py`、`view.py`。最后改 README 两行（要做的 4）。

## Checkpoint（gate）：模块最终验收

列出改动文件与测试数，批准后开 PR；合并后接着发 0.0.30（版本号两处、README 升级说明、测试里的版本断言，另开 PR）。

## 风险

| 风险 | 对策 |
|---|---|
| 去掉括号后把某条线误认作用户 | 先按原样找名册里的线，找到就不是等用户；只在完全等于那几个名字时才算 |
| `stale_tickets` 有别的调用方依赖它只含 later | 保留原函数原签名，只让 health 改用新函数 |
