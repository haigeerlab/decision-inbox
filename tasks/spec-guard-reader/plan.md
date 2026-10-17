<!-- spec-guard: review approved -->
# Implementation Plan: spec-guard-reader

> 依据：`spec/spec-guard-reader.md`（已批准）。任务清单：`tasks/spec-guard-reader/todo.md`。

## Overview

先做不需要子进程的两块：按安装记录找脚本、把 JSON 文本解析成 `LineMap`；再做子进程调用与 8 种结果分类；最后补一个真实调用本机 spec-guard 的集成测试。每个任务先写失败的测试，再实现到全绿，单独提交。代码在 `decision_inbox/specguard.py`。

## Architecture Decisions

- 三层函数：`locate(project)` 只读安装记录；`parse_map(text)` 只把 JSON 文本变成 `LineMap`（不碰子进程）；`read_line(project, timeout)` 组合前两者并调用子进程。解析层与调用层分开，大部分测试不用启动子进程。
- 子进程：`subprocess.run([sys.executable, "-B", script, "--project", project, "--json"], capture_output=True, text=True, timeout=timeout)`，不传 `shell`；`TimeoutExpired` 归为 `timeout`。
- 假脚本：测试在临时目录里写一个 `hooks/map_view.py`，从同目录的 `behavior.json` 读要输出的 stdout、stderr、退出码和要睡的秒数；安装记录也写在临时目录，用 `DECISION_INBOX_PLUGINS_FILE` 指过去。
- JSON 样例：`tests/fixtures/specguard/map-0.63.json` 取自本机实跑 spec-guard 0.63.0 读本仓库的输出（只保留 3 个模块，项目路径改成占位）；`map-0.62.json` 由它去掉停滞字段得到。

## 影响面

新增：`decision_inbox/specguard.py`、`tests/test_specguard.py`、`tests/fixtures/specguard/` 下 2 个 JSON 样例。修改：`tasks/spec-guard-reader/todo.md`（勾选）、`.agent/state.json`（最终验收时切换当前模块）。不改其他已有文件，不涉及用户可见界面。

## Task List

### Phase 1：不需要子进程

- [ ] Task 1：按安装记录找脚本（Spec 验收 1、2）
- [ ] Task 2：解析 JSON 为 LineMap（Spec 验收 3、7、8，及 5 的解析部分）

### Checkpoint 1（report）

- [ ] 全部测试全绿

### Phase 2：调用

- [ ] Task 3：子进程调用与结果分类（Spec 验收 4、5、6、9、11）
- [ ] Task 4：本机 spec-guard 集成测试（Spec 验收 10）

### Checkpoint 2（gate）：模块最终验收

- [ ] 全部测试全绿；11 条验收标准逐条对应测试；列出实际改动的文件
- [ ] 本 Plan 获批即授权：每个任务完成后在当前分支做一次本地提交；不授权推送、不授权开 PR

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| 超时测试拖慢整套测试 | 低 | 超时用例把 timeout 设为 1 秒、假脚本睡 3 秒 |
| 集成测试依赖本机安装，换机器失败 | 中 | 安装记录里没有 spec-guard 或脚本不存在时 `skipTest` 并写明原因 |
| 样例里带本机路径或分支名 | 低 | 写样例时把项目路径、分支名、sha 换成占位 |

## Open Questions

无。
