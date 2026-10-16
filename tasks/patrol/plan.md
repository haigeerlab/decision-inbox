<!-- spec-guard: review approved -->
# Implementation Plan: patrol

> 依据：`spec/patrol.md`（已批准）。任务清单：`tasks/patrol/todo.md`。

## Overview

先做 group-store 的小返工（`desktopSession` 字段），再搭巡视的骨架：`plan` 算动作、`record` 记账、去重记录，用「叫醒」这一种动作把多轮测试的写法定下来。然后依次加进度预警与升级、给用户的通知，最后接命令行，并实测桌面通知和 `bridge_send`。每个任务先写失败的测试，再实现到全绿，单独提交。代码在 `decision_inbox/patrol.py`。

## Architecture Decisions

- **`plan` 是纯函数**：输入协作组状态、`now`、agent-relay 快照（可以为 None）和 spec-guard 结果，输出 `Plan`（动作、新快照、本轮看到的信号键、本轮在线的会话）。它只读，不写任何东西。
- **`record` 是唯一写入口**：在一个 group-store 事务里更新领域 `patrol`，并写一条 `patrol.run` 事件，事件里带完成和失败的动作编号。记账规则如下：
  - 本轮没看到的信号键：删掉；
  - 本轮看到在线的会话：清掉它的叫醒记录；
  - 已不在待答的事项：从 `reminded` 里删掉；
  - 写入新快照。
- **动作的去重规则写成三张小表**（叫醒、预警与升级、通知），各自一个函数，`plan` 依次调用后合并。通知最后统一做「每轮最多 3 条」的合并。
- **动作编号**按规格写：`wake:<身份名>`、`alert:<信号键>`、`notify:<事由键>`。信号键写成 `<编号>|<会话1>|<会话2>…`；事由键写成 `all-waiting`、`unwakeable:<身份名>`、`escalate:<信号键>`、`item:<编号>`、`relay-unreadable`、`no-owner:<信号键>`。
- **多轮测试的写法**：测试基类提供一个 `run_round(now, done=all, failed=())`，内部依次跑 `plan` 和 `record`，返回本轮的动作编号。每个场景都写成「几轮、时间往后推」的形式。
- **提示词**：`patrol prompt` 的文本放在 `patrol.py` 里的常量模板中，按协作组名填好，不另建文件。
- **建议句**：从 hub-view 的信号建议表里取。在 hub-view 里把那张表开放出一个公开的小函数，供本模块调用；只挪位置，不改内容。

## 影响面

- 新增：`decision_inbox/patrol.py`、`tests/test_patrol.py`。
- 修改：
  - `decision_inbox/store.py`、`tests/test_store_roster.py`：返工，加 `desktopSession` 字段；
  - `decision_inbox/view.py`：开放信号建议句的公开函数，只挪位置；
  - `decision_inbox/__main__.py`：加 `patrol` 子命令；
  - `spec/patrol.md`：Task 7 实测后补实测记录；
  - `tasks/patrol/todo.md`：勾选；
  - `.agent/state.json`：最终验收时切换当前模块。
- 用户可见界面：桌面通知的文字、发给负责人的预警。由 Task 7 实测看到；收件枢纽主视图不改。

## Task List

### Phase 1：骨架

- [ ] Task 1：group-store 返工——`desktopSession` 可选字段（Spec 验收 12）
- [ ] Task 2：`plan`、`record`、去重记录与叫醒（Spec 验收 1、2、7、10、11）

### Checkpoint 1（report）

- [ ] 全部测试全绿

### Phase 2：预警、通知与入口

- [ ] Task 3：进度预警与 30 分钟升级（Spec 验收 3、4）
- [ ] Task 4：给用户的通知——全线停住、超时提醒、读不到 agent-relay、每轮 3 条（Spec 验收 5、6、8、9）
- [ ] Task 5：命令行 `patrol plan`、`record`、`prompt`（Spec 验收 13）

### Checkpoint 2（report）

- [ ] 全部测试全绿；在临时协作组上用命令行实跑一轮 plan 和 record，记下计划文件和状态的变化

### Phase 3：实测

- [ ] Task 6：实测桌面通知与 `bridge_send`（Spec 验收 14）。先问用户，结果写进规格的实测记录

### Checkpoint 3（gate）：模块最终验收

- [ ] 全部测试全绿；14 条验收标准逐条有测试或实测记录；列出实际改动的文件；原样附上规格的改动差异（实测记录），批准本次验收即同时批准修订后的规格
- [ ] 本 Plan 获批即授权：
  - Task 1 的返工；
  - 每个任务完成后在当前分支做一次本地提交；
  - 在 scratchpad 里建临时协作组。
- [ ] 不授权：Task 6 的实测（到时另外问你）、推送、开 PR

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| 去重规则多，组合起来互相干扰 | 中 | 每种规则一个函数、一组多轮测试；另有「同一 `now` 连跑两轮」的总测试 |
| 时间门槛的边界（29 分钟、30 分钟）因时区或取整出错 | 中 | 全部转成绝对时间，按秒比较；测试覆盖两侧的边界 |
| 实测时桌面通知被系统权限挡住 | 中 | 如实记下，回来改规格（例如改成只叫醒收件枢纽），先问你 |
| 给测试身份发消息影响真实会话 | 低 | 实测用一个专门的测试身份，不发给真实协作组里的会话；发之前先给你看内容 |

## Open Questions

无。
