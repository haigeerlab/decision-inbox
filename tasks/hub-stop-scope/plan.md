<!-- spec-guard: review approved -->

# Implementation Plan: hub-stop-scope

> 依据：`spec/hub-stop-scope.md`。任务清单：`tasks/hub-stop-scope/todo.md`。分支 `claude/zen-almeida-67c3f0`（从 main e88e7d9）。

需要的外部条件：无。

## Overview

两个任务，每个先写在 e88e7d9 上失败的测试：停止钩子只对收件箱做卡片检查 → doctor 只试读收件箱自己的会话记录。之后最终验收、开 PR（base main，由用户合并），不改版本号、不打标签、不升级本机。

## Architecture Decisions

- `__main__._hook` 在调 `hub_turn_check` 之前先认会话：带 `--group` 和 `--session` 时用 `store.find_session` 取角色；否则用 `install.locate(cwd)`。只有恰好对上一个条目、而且它的 `role` 是 `hub` 时才调 `hub_turn_check`。没有 `cwd`、对上多个条目且其中有收件箱、读名册出错时，往 stderr 写 `decision-inbox 停止钩子：收件箱停止检查放行：<原因>`，然后继续走原来的流程。认会话的结果顺带用于后面的 `decide`，不再调第二次 `locate`。
- 认会话的逻辑放在 `__main__.py` 里的一个小函数 `_hub_scope(args, payload) -> (is_hub, note)`，`stophook.hub_turn_check` 本身不改，现有 `HubTurnCheckTest` 不动。
- `doctor` 新增 `_project_folder(path) -> str`：把目录路径里非字母数字的字符换成 `-`。`_hub_transcript(groups)` 对每个没离开的收件箱取 `files[<邮箱名>]` 所在目录，按记下的写法和 realpath 后的写法各算一个文件夹（去重），只扫这些文件夹里最近 50 份 `*.jsonl`。`run()` 把组名传进去。
- 现有 `HubTranscriptTest` 把记录放在 `-hub` 文件夹，组里也没有记下收件箱规则文件；改成在测试组里记下收件箱规则文件，把记录放进对应的编码文件夹。

## Task List

- **Task 1 停止钩子只对收件箱做卡片检查**（Spec 要做的 1；验收 1～4）：`tests/test_stophook.py` 新类，用子进程跑 `python3 -m decision_inbox hook stop`，`DECISION_INBOX_HOME` 指向临时组。组里有收件箱（规则文件记在 `<组>/hub/CLAUDE.md`）和开发线。会话记录本轮跑了 `decision-inbox view <组>`、回复是摘要。断言：cwd 为开发线 repo、组外目录时不出 block；cwd 为 `<组>/hub` 时出 block；payload 没有 cwd 时不出 block，stderr 有「收件箱停止检查放行」；`--group --session <开发线>` 不做卡片检查，`--session <收件箱>` 照做。现有的 `test_hook_entry_blocks_outside_any_group` 和这次要的行为相反，改成断言不拦。
- **Task 2 doctor 只试读收件箱的会话记录**（要做的 2；验收 5）：`tests/test_doctor.py` 的 `HubTranscriptTest` 加用例：别的文件夹里有一份读不懂但出过主视图的记录、收件箱文件夹里有一份读得懂的，报 ok，证据里有组名；只有别的文件夹里有，报 unknown；收件箱没有记下规则文件时报 unknown，写明原因；收件箱目录是 `/tmp` 这类别名时按 realpath 也找得到。现有三个用例改成用收件箱的编码文件夹。全量 `PYTHONPATH=tests:. python3 -m unittest discover -s tests`。

## Checkpoint（gate）：模块最终验收

列出实际改动的文件（新增、修改与行数，取自版本库）与测试数；在临时组复现一次 2026-10-20 的场景（非收件箱目录跑 view 后停下），把钩子的输出和 doctor 这一项的输出给你看；批准后开 PR。不改界面，没有 UI 自验。

## 风险

| 风险 | 对策 |
|---|---|
| 子进程测试读到本机真实的 `~/.decision-inbox` | 测试里设 `DECISION_INBOX_HOME` 指向临时目录（沿用现有测试的做法） |
| macOS 临时目录 `/var` → `/private/var` 别名，cwd 和记下的路径写法不同 | `locate` 本来就做 realpath；doctor 两种写法都试，测试覆盖 |
| 现有测试依赖「哪里都拦」 | `test_hook_entry_blocks_outside_any_group` 按 Spec 改为不拦，交付时列出 |
