<!-- spec-guard: review approved -->

# Implementation Plan: stage-c2-fixes

> 依据：`spec/stage-c2-fixes.md`。任务清单：`tasks/stage-c2-fixes/todo.md`。分支 `claude/v0036-fixes`（从 main 06739cc）。

需要的外部条件：无。

## Overview

按 Spec 的优先级做四个修复，每个都先写一条在 06739cc 上会失败的测试，然后升版本、写文档，最后做最终验收、开 PR（base main，由用户合并）。不打标签，不在本机安装或升级。

## Architecture Decisions

- **I-16**
  - `items._segments` 拿到每一行（单行时就是整段）后，先调新函数 `_split_inline(line, known)`：在「空白＋待答编号＋空白＋单个大写字母＋（分号／逗号／空白／行尾）」处切开，并且这个字母必须在 `known[编号]["options"]` 里。
  - 切出来的片段再走现有的 `grouped` 规则，把「；D1 A」这类带前缀的片段归给前一项。
  - 兜底放在 `interpret_reply`：某一段的 rest 里还能匹配上别的待答事项的「编号＋空白＋选项字母＋分隔」，就返回问题。
- **I-17**
  - `onboard.patrol_dir(group)` 返回 `store.root_dir() / group / "patrol"`。
  - `onboard hub` 的步骤里写这个目录；`state["patrolSession"]` 存在时，先插入 teardown 用的那两步（停止、归档），把这两步抽成 `_retire_patrol_steps(session)`，teardown 和 hub 共用。
  - `onboard.allow(group, project, confirm)` 也写 `patrol_dir/.claude/settings.local.json`，返回值里两份都列出；CLI 打印跟着改。
  - 停止钩子不用改：巡视目录不属于任何成员，`locate` 认不出它，自然放行。用测试锁住这一点。
- **I-18**
  - `stophook.session_start(payload)`：读 `transcript_path` 第一条带 `timestamp` 的记录；读不到返回 None。
  - `decide(..., started=None)` 把它传给 `_answered`。事项 `receivedAt` 早于 `started` 的，改用 Spec 假设 6 的写法；`_hook` 负责传入。
- **I-19**
  - `hub._notices(g, it, now, crews=None, maps=None)` 先认出唯一的那一条开发线，认不出就返回空：
    - 先看 `review.ref`：查 `reviews` 状态里这个编号的 `submitter`，并且它要是审查者那条线上的开发线；
    - 再看 `module` 或 `approvalModule`（不是「无」）：在审查者那条线的开发线里找，模块协调的 `crews[名].modules` 或 `maps[名].map.modules` 里有这个模块 id 的，恰好一条时才算。
  - `_queue_answers` 和 `hub.reply` 把已有的 crews、maps 传下去。
- **版本**：两个 plugin.json 升到 0.0.36，`test_packaging` 跟着改。

## Task List

- **Task 1 I-16 答复按项切开**（Spec 要做的 1；验收 1～3）
  - `tests/test_items.py` 新类 `InlineSplitTest`：用当时 `said.txt` 的原文重放，#69～#72 都是待答状态，#69、#70、#71 带 D1；`69 A 70 B`；`21 B，C15 退回`；`69 A 提交 3f2a1b9`；有 #3 待答时 `69 原话：验收 1、3 都要补`、`69 A 第 3 步先做`；兜底问题。
  - `tests/test_hub.py` 加一条：用 `hub.reply` 跑重放原文，排队的 #69【用户答复】正文里没有「70 A」。
- **Task 2 I-17 巡视换到自己的目录**（要做的 2；验收 4、5）
  - `tests/test_onboard.py`：
    - hub 的步骤里写的是巡视目录；
    - 名册记着旧巡视会话时，先列出停止和归档；
    - `allow --confirm` 后两个目录都写了放行规则，预览不改文件；
    - teardown 的步骤不变。
  - `tests/test_stophook.py`：Spec 现状里那次实测的重放（有等收件箱的等待记录），cwd 在收件箱目录时出 block（锁住旧行为，说明为什么要换目录），cwd 在巡视目录时不出 block。
  - 文档：`commands/hub-setup.md` 改写法。
- **Task 3 I-18 旧事项写明来历**（要做的 3；验收 6）
  - `tests/test_stophook.py` 的 `AnsweredNotResumedTest` 加用例：
    - 会话记录开始时间晚于事项抛出时间：提示含「之前的会话」、抛出和答复时间、【已恢复】和【撤回】；
    - 开始时间更早：提示照旧；
    - 没有记录：提示照旧；
    - 命令行入口传了开始时间。
- **Task 4 I-19 收窄【答复告知】**（要做的 4；验收 7）
  - `tests/test_hub.py` 的 `AnswerNoticeTest`：
    - 现有「同线所有开发线都收到」的用例改成新行为；
    - 带审查编号只发提交方；
    - 只带模块时按模块协调或能力图认出唯一一条；
    - 认不出不发；
    - 测试身份收不到；
    - 多线事项照旧不发。
  - 全量测试通过。
- **Task 5 版本 0.0.36 与 README**（要做的 5）
  - 两个 plugin.json、`test_packaging`；
  - README 的 0.0.36 升级步骤（收件箱重跑 hub-setup，换掉旧巡视会话，`onboard allow` 重跑一次；开发线不用重跑）；
  - 排查表加「巡视会话开在收件箱目录里」。

## Checkpoint（gate）：模块最终验收

- 列出实际改动的文件（新增、修改与行数，取自版本库）和测试数。
- 重放三件事：
  - I-16：用当时的 said.txt 原文跑 `inbox reply`，看每项发出去的原话；
  - I-17：在 di-p0 状态副本上，巡视目录与收件箱目录各跑一次停止钩子；
  - I-18：用 #64 的时间线跑停止钩子提示。
- 批准后开 PR。
- 没有界面改动，不做 UI 自验。

## 风险

| 风险 | 对策 |
|---|---|
| I-16 改切分影响现有答复解析 | 现有 test_items、test_hub、test_cards 的解析用例不改，全部通过 |
| I-19 改了现有「同线全发」的测试 | 这是 Spec 要改的行为，交付时列出改了哪几条断言 |
| I-17 测试写到真实的 `~/.decision-inbox` | 测试一律用 `TempHomeTestCase` |
| 会话记录格式没有 `timestamp` | 退回原提示，测试覆盖 |
