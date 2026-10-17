<!-- spec-guard: review approved -->
# Implementation Plan: group-store

> 依据：`spec/group-store.md`（已批准）。任务清单：`tasks/group-store/todo.md`。

## Overview

先把插件骨架和测试框架立起来，再按「组目录 → 快照读写 → 编号与事件日志 → 一致性检查 → 名册」的顺序逐层加能力。每个任务先写失败的测试，再实现到全绿，然后单独提交。并发和崩溃这两类高风险行为放在前半段（任务 3、4），尽早暴露问题。

## Architecture Decisions

- 全部逻辑在 `decision_inbox/store.py` 一个文件里；CLI 只在 `decision_inbox/__main__.py` 做参数解析和中文输出，不含存储逻辑。
- 组锁用 `fcntl.flock` 锁 `<组>/.lock`；事务对象在 `__exit__` 时一次性落盘：先追加事件（`fsync`），再按「临时文件 → `fsync` → `os.replace`」替换快照和 `counter.json`。事务内的读取看到本事务尚未落盘的修改。
- 事务异常时只丢弃内存里的修改，不触碰磁盘，所以「事务前后逐字节相同」不依赖回滚代码。
- 事件日志读取按行解析；只有最后一行允许不完整（跳过并给警告），中间行坏了按损坏处理（`StoreCorrupt`）。
- 并发测试用 `multiprocessing`（`spawn` 上下文，避免 macOS 上 fork 的隐患）。
- 测试统一通过 `tests/helpers.py` 设置 `DECISION_INBOX_HOME` 到 `tempfile.mkdtemp()`，并在每个测试后清理临时目录（只删测试自己建的临时目录，不触及状态目录约定）。

## 影响面

全部是新文件：`.claude-plugin/plugin.json`、`.codex-plugin/plugin.json`、`decision_inbox/__init__.py`、`decision_inbox/__main__.py`、`decision_inbox/store.py`、`tests/helpers.py`、`tests/test_package.py`、`tests/test_store_group.py`、`tests/test_store_state.py`、`tests/test_store_events.py`、`tests/test_store_roster.py`。不改任何已有文件（`tasks/group-store/todo.md` 的勾选与 `.agent/state.json` 除外）。不涉及用户可见界面，不需要 UI 验证。

## Task List

### Phase 1：骨架

- [ ] Task 1：插件骨架与包级静态检查（验收标准 11、12）

### Checkpoint 1（report）

- [ ] `python3 -m unittest discover -s tests -v` 全绿

### Phase 2：存储核心

- [ ] Task 2：根目录、协作组名校验、`store init`（验收标准 1、2、10）
- [ ] Task 3：快照读写、版本与损坏检测、事务回滚（验收标准 4、5、6）
- [ ] Task 4：编号分配、事件日志与多进程并发（验收标准 3、7）

### Checkpoint 2（report）

- [ ] 全部测试全绿；并发测试连续跑 5 次都通过

### Phase 3：排查与名册

- [ ] Task 5：一致性检查与 `store show`（验收标准 8，及 5 中 `show` 的部分）
- [ ] Task 6：会话名册（验收标准 9）

### Checkpoint 3（gate）：模块最终验收

- [ ] 全部测试全绿；逐条对照 Spec 的 12 条验收标准，写明各由哪个测试覆盖
- [ ] 在对话里列出本模块实际改动的文件（新增、修改、删除与行数，取自 `git diff --stat`）
- [ ] 本 Plan 获批即授权：每个任务完成后在当前分支做一次本地提交；不授权推送、不授权开 PR

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| macOS 上 `flock` 与 `multiprocessing` 组合出现偶发失败 | 高 | 任务 4 的并发测试连续跑 5 次；用 `spawn` 上下文 |
| 「快照落后于日志」的判断写错，误报或漏报 | 中 | 任务 5 用人工构造的文件覆盖落后、一致两种情况 |
| 测试误写真实 `~/.decision-inbox` | 高 | 测试基类在 `setUp` 断言 `DECISION_INBOX_HOME` 已指向临时目录，否则直接失败 |
| 文件权限受 umask 影响不是 `0700`／`0600` | 低 | 创建后显式 `chmod`，测试断言权限位 |

## Open Questions

无。
