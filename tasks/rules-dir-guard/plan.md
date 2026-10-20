<!-- spec-guard: review approved -->

# Implementation Plan: rules-dir-guard

> 依据：`spec/rules-dir-guard.md`。任务清单：`tasks/rules-dir-guard/todo.md`。分支 `claude/exciting-hertz-bc870f`（从 main 0714203）。

需要的外部条件：无。

## Overview

五个任务，每个先写在 0714203 上失败的测试：目录核对与 hub → join → `--drop-old` → doctor → 文档与版本。之后最终验收、开 PR（base main，由用户合并），不打标签、不升级本机。

## Architecture Decisions

- `onboard.py` 新增 `_member_dirs(g, skip_relay)`：按 Spec 假设 1 给出其他成员的 `(entry, 目录, 是不是规则文件目录)`；`_dir_guard(g, entry, rules)` 返回要拦的成员（T 是成员目录本身或上级，抛 `JoinError`）和要提示的规则文件（T 在别人规则文件目录的下级，进 `out.warnings`）。路径一律 `os.path.realpath` 后比较，`/tmp` 和 `/private/tmp` 这类别名不会漏判。
- hub 在组还不存在时没有其他成员，核对直接通过；hub 和 join 在 `place` 之前做核对，预览和 `--confirm` 走同一条路，拦下时什么都不写。
- `_old_rules(g, entry, rules)`：`files[<邮箱名>]` 记下的旧文件 R 与这次不同、R 里是本角色的规则段时，给出提示；`drop_old` 为真时在 `_commit` 之后按 leave 的写法删段或删文件、改 `created`、事件 data 加 `droppedOld`。`Outcome` 加一个 `old_rules` 字段，`_print_outcome` 据此打印「确认后从 R 删掉旧协作规则段」或「已删掉」。
- `doctor._ancestor_blocks(g)`：对每个成员目录向上逐级查 `CLAUDE.md`、`CLAUDE.local.md`、`AGENTS.md`，用 `onboard._MARK_RE` 找标记；排除这个成员自己记下的规则文件；按文件合并受影响成员；在 `run()` 里接在 `_conventions` 之后。
- 命令行 `onboard hub`、`onboard join` 加 `--drop-old`，传给 `hub(..., drop_old=)`、`join(..., drop_old=)`。

## Task List

- **Task 1 目录核对与 hub 拦下／提示**（Spec 要做的 1；验收 1、2）：`tests/test_onboard.py` 新类。造组：审查者在 `<组>/owner`；在 `<组>` 跑 hub 预览和 `--confirm` 都抛 `JoinError`，报错有原因、审查者目录、建议目录（没记下时 `<组>/hub`，记下过时用记下的目录），文件系统和状态目录前后不变；开发线 repo 与 T 相同也拦；命令行退出码非 0。
- **Task 2 join 拦下／提示**（要做的 1；验收 3）：join 目标是收件箱或其他成员目录的上级时拦下；目标在收件箱规则文件目录下级时不拦，`warnings` 里有提示。
- **Task 3 `--drop-old`**（要做的 2；验收 4）：hub 从 `<组>/hub` 换到 `<组>/inbox`：不带开关时有提示、旧文件不动；带 `--drop-old --confirm` 时旧文件只少了规则段（其余逐字不变），新建且删完为空的被删掉、`created` 里没有它；旧文件是别的角色的段时不动；没有旧段时写「没有旧规则段要删」。join 换项目目录同样一条。命令行两个子命令接受 `--drop-old`。
- **Task 4 doctor「上级目录的协作规则段」**（要做的 3；验收 5）：`tests/test_doctor.py` 新类。`<组>/CLAUDE.md` 有收件箱段、审查者在 `<组>/owner` 时 bad，写明文件与受影响成员、修复办法分「有人记下」和「没人记下」两种；删掉后 ok；成员自己记下的文件不算；离开的成员不算；同一文件只报一项。
- **Task 5 文档与版本 0.0.34**（要做的 4）：`commands/hub-setup.md`、`commands/join.md`、`skills/decision-inbox-join/SKILL.md` 按 Spec 补说明；README 升级说明加 0.0.34；两份 `plugin.json` 升到 0.0.34；打包测试里有版本或命令文本检查的一并更新；全量 `PYTHONPATH=tests:. python3 -m unittest discover -s tests`。

## Checkpoint（gate）：模块最终验收

列出实际改动的文件（新增、修改与行数，取自版本库）与测试数；用临时目录复现一次 2026-10-20 的场景（审查者在 `<组>/owner`，在 `<组>` 跑 hub），把拦下的输出和 doctor 的输出给你看；批准后开 PR。不改界面，没有 UI 自验。

## 风险

| 风险 | 对策 |
|---|---|
| macOS 临时目录有 `/var` → `/private/var` 别名，判断上下级漏判 | 统一 `realpath`；测试里用 `tempfile` 的原始路径和 realpath 各跑一次 |
| doctor 一路查到根目录时，本机真实的上级目录里恰好有标记，测试不稳 | 测试只断言自己造的文件那一项；只在临时目录树里判 ok 时，用 monkeypatch 把向上查的终点限制在临时目录根 |
| 现有 hub／join 测试的目录布局本来就是上下级（例如 hub 在 repo 的上级） | 先跑一遍现有测试找出这类布局；属于测试造数据随意的，改成兄弟目录，并在交付说明里列出改了哪些用例 |
| 打包测试对 README、命令文档、版本号有硬编码检查 | Task 5 一并更新 |
