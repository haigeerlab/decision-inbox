<!-- spec-guard: review approved -->

# Implementation Plan: patrol-watch-runtime

> 依据：`spec/patrol-watch-runtime.md`。任务清单：`tasks/patrol-watch-runtime/todo.md`。分支 `claude/trusting-feistel-576ff8`（从 main c4d97ca）。

需要的外部条件：无。

## Overview

四个任务，每个先写在 c4d97ca 上失败的测试再改代码：运行副本 → plist → doctor → 文档与版本。之后在本机装 di-p0 的巡视提醒做实机验收，再最终验收、开 PR（base main，由用户合并），不打标签。

## Architecture Decisions

- 运行副本的复制与刷新放在 `install.py`（转发脚本也在这里），`install.runtime_dir()` = `store.root_dir() / "runtime"`；`write_runtime(root, if_present=False)` 比较文件内容，不同才整体替换（写临时目录 → 旧目录换名 → 新目录换名 → 删旧），返回是否变了。只复制 `bin/decision-inbox` 和 `decision_inbox/*.py`（不带 `__pycache__`）。
- `shim` 命令：写转发脚本后调用 `write_runtime(plugin_root, if_present=True)`，仍然静默、不让 SessionStart 失败（异常吞掉）。
- `watch.PLIST` 加 `EnvironmentVariables`；python 目录取 `os.path.dirname(sys.executable)`；受保护目录 = `~/Documents`、`~/Desktop`、`~/Downloads`（按 `Path.home()` 拼，比较前 `realpath`）。命中时 `install` 返回 `Plan.error` 且不写任何东西。
- `doctor._patrol_watch` 用 `plistlib` 读 `ProgramArguments[0]`；`watch.last_exit(group)` 解析 `launchctl print` 的 `last exit code = N`（`(never exited)` 记为 None）；日志取最后一个非空行。

## Task List

- **Task 1 运行副本**（Spec 要做的 1、4；假设 1、2）：测试——复制后内容一致且不含 `__pycache__`；内容不变时不重写；源有变化时整体替换；`if_present=True` 且目录不存在时不建；`shim --if-installed` 在运行副本存在时刷新它。
- **Task 2 plist 跑运行副本**（要做的 2、4；假设 3、4）：测试——`--confirm` 后运行副本已生成，plist 第一项是运行副本里的 `bin/decision-inbox`，带 `PATH`（以 `sys.executable` 目录开头）和 `DECISION_INBOX_HOME`；预览不复制；python 或运行副本落在受保护目录时拒绝、不写 plist、不调 launchctl；`onboard watch` 预览写明运行副本位置和 python。
- **Task 3 doctor 看上次退出码**（要做的 3、4；假设 5）：测试（假 `launchctl print` 输出可配）——旧任务（第一项不是运行副本）bad；运行副本缺失 bad；退出 126 且日志含 `Operation not permitted` 时 bad 并写明受保护目录；退出 1 bad 带日志最后一行；退出 0 与 `(never exited)` ok。
- **Task 4 README 与版本号**（要做的 5）：排查表加一行，升级说明写明 0.0.31 装过的重跑 `onboard watch`；两份 `plugin.json` 升到 0.0.32；全量测试。

## Checkpoint（gate）：本机实机验收

先问你：用本分支代码运行 `onboard watch di-p0 --confirm`（会写 `~/Library/LaunchAgents/com.haigeerlab.decision-inbox.patrol-watch.di-p0.plist`，并复制运行副本到 `~/.decision-inbox/runtime/`）。批准后装，再核对：`last exit code = 0`、弹出「巡视停了」、doctor 报 ok；再用临时 Label 指向 `~/Documents` 下脚本的任务复现 126，确认 doctor 判 bad，测完卸掉。

说明：这一步装的是本分支代码的运行副本；以后哪个宿主启动会话，SessionStart 就会用那个宿主的插件刷新运行副本（0.0.31 还没有刷新逻辑，所以在你升级前它保持本分支这份）。

## Checkpoint（gate）：模块最终验收

列出改动文件与测试数，批准后开 PR。

## 风险

| 风险 | 对策 |
|---|---|
| SessionStart 刷新失败影响开会话 | 刷新异常全部吞掉，`shim` 照旧返回 0；有测试 |
| 测试改到真实 `~/.decision-inbox` 或 LaunchAgents | 沿用 `TempHomeTestCase` 与 `DECISION_INBOX_LAUNCH_AGENTS`、假 `launchctl` |
| 实机验收时 0.0.31 的会话启动不会刷新运行副本，之后升级到 0.0.32 才会 | 预期如此，验收报告里写明 |
