<!-- spec-guard: review approved -->

# Implementation Plan: r20-fixes

> 依据：`spec/r20-fixes.md`（用户 2026-10-19 批准）。任务清单：`tasks/r20-fixes/todo.md`。分支 `claude/r20-fixes`（叠在 #19 上）。

## Overview

三个任务，各自先写失败的测试再改：停止钩子（唯一的代码改动）→ 卡片字母自检与收件枢纽规则段 → 三种角色规则段与 README。不升版本号。

## Architecture Decisions

- **Task 1 停止钩子**（`stophook._who`）：
  - 开头取 `left = store.left_relays(g)`；
  - `--session` 找到的条目在 left 里，返回 `(None, "<名字> 已退出协作组")`，于是放行；
  - 按 cwd 找时，列表推导里加上 `e["relayName"] not in left`。
- **Task 2 字母自检与「逐字粘贴」**：
  - 测试辅助函数：扫描文本，记住最近一行选项（`^(推荐 )?([A-Z])：` 或审批项里的 `^([A-Z])：`），每遇到 `回 N X` 就断言 X 等于最近那个选项的字母。对主视图（推荐项排第一）、「看 N」、「N 详情」三种输出都跑一遍。
  - 插件输出本来就对，这条测试应当一写就过，目的是以后改坏时能立刻报出来。
  - `hub.CONVENTION` 里两处「原样显示给用户」改成「逐字粘贴给用户，不要手抄、不要改写其中任何一行（包括选项和『回 N X』）；看起来不对时以命令输出为准，并告诉用户哪里不对」。先写测试，断言规则段里有这句。
- **Task 3 规则段与 README**：
  - `onboard._COMMON` 里「收到【用户答复】后，做完要发【已恢复】……」那一行后面，加「多线事项（事项行里写了『多线事项』）的适用线不用发【已恢复】，结项只认发起方」。
  - 测试断言三种角色的规则段都有这句。
  - README 升级一节写明：收件枢纽和各工作会话都要重新接入（和 approval-display 那一句合并）。

## Task List

- **Task 1 停止钩子**（Spec 验收 3）。验证（`tests/test_stophook.py`）：
  - 两个条目共用一个仓库，其中一个已退出：按 cwd 能认出留下的那个，它有人在等时被拦；
  - `--session` 指向已退出的条目：放行，原因里有「已退出协作组」；
  - 原有测试全部通过。
- **Task 2 字母自检与「逐字粘贴」**（Spec 验收 1）。验证（`tests/test_view.py`、`tests/test_hub.py`）：三种输出的字母自检；收件枢纽规则段里有「逐字粘贴」「不要手抄、不要改写」。
- **Task 3 规则段与 README**（Spec 验收 2、4）。验证（`tests/test_onboard.py`）：三种角色的规则段；`python3 -m unittest discover -s tests` 全部通过。

## Checkpoint（gate）：模块最终验收

列出改动的文件、每条验收标准的证据、测试数，然后开 PR（base 是 `claude/approval-display`）。

## 影响面

- 停止钩子按 cwd 找会话的路径；
- 收件枢纽和工作会话的规则段文字（都要重新 join）。

## 风险

| 风险 | 对策 |
|---|---|
| 排除已退出的条目后，某些原来能拦的情况改成放行 | 已退出的条目本来就不该再被拦；测试覆盖「留下的那个照样能拦」 |
| 改了规则段文字，doctor 会报「约定块不是当前版本」 | 这是预期的提示；README 写明要重新接入 |
