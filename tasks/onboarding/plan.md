<!-- spec-guard: review approved -->
# Implementation Plan: onboarding

> 依据：`spec/onboarding.md`（已批准）。任务清单：`tasks/onboarding/todo.md`。

## Overview

先做不碰状态的两块：约定块的放入、替换与删除，以及三个角色的约定块文本。再做 `hub`、`join`（含名册与审查者登记），然后做 `task`、`leave`、`teardown`，最后接命令行并实测一遍。每个任务都先写失败的测试，再实现到全绿，然后单独提交。代码在 `decision_inbox/onboard.py`。

## Architecture Decisions

- **约定块操作是纯文本函数**：`place(text, role, block)` 和 `strip(text)` 只处理字符串，不读写文件，方便逐字比较块外内容。
  - 标记用整行匹配，块的范围从 BEGIN 行到 END 行（含这两行）。
  - 放入时，块和原有内容之间空一行；删除时，连同块后面的一个空行一起去掉，块外的其他字节不动。
- **先算后写**：`hub` 和 `join` 先在内存里算出新的规则文件文本、名册条目和审查者登记，全部校验通过后才写。预览时只返回这些结果。
  - 名册条目的校验沿用 group-store 的 `_validate_session`：在内存里拿现有名册试一遍。
  - 写的顺序：先在一个事务里写名册和领域 `onboarding`，成功后再写规则文件，最后登记审查者（`register` 自己开事务）。规则文件用临时文件加改名的方式原子写入。
- **约定块文本**：放在 `onboard.py` 里，三个常量模板加一个共用部分，按协作组名和收件枢纽身份名填好。消息模板写成代码块，测试从块里取出来交给 `protocol.parse` 解析。
- **领域 `onboarding`**：`patrolTask`（巡视任务编号）、`files`（身份名 → 写过约定块的规则文件路径）。`leave` 和 `teardown` 不带 `--project` 时，就用这里记下的路径。
- **后续步骤**：`Outcome.steps` 是一个字符串列表。命令行逐条加编号打印，测试直接核对列表内容。

## 影响面

- 新增：`decision_inbox/onboard.py`、`tests/test_onboard.py`。
- 修改：
  - `decision_inbox/__main__.py`：加 `onboard` 子命令和用法说明；
  - `spec/onboarding.md`：Task 6 实测后补「实测记录」；
  - `tasks/onboarding/todo.md`：勾选；
  - `.agent/state.json`：最终验收时切换当前模块。
- 用户可见界面：写进各项目规则文件的约定块、命令打印的预览和后续步骤。由 Task 6 实测时在临时项目目录里看到并记录；约定块全文在最终验收时原样展示。

## Task List

### Phase 1：文本

- [ ] Task 1：`place`、`strip` 与 `BlockConflict`（Spec 验收 1、2）
- [ ] Task 2：三个角色的约定块文本（Spec 验收 3）

### Checkpoint 1（report）

- [ ] 全部测试全绿

### Phase 2：接入与卸载

- [ ] Task 3：`hub`（Spec 验收 4、10）
- [ ] Task 4：`join`，含名册与审查者登记（Spec 验收 5、6、7、10）
- [ ] Task 5：`task`、`leave`、`teardown` 与命令行 `onboard`（Spec 验收 8、9、11）

### Checkpoint 2（report）

- [ ] 全部测试全绿；在 scratchpad 的临时项目目录里用命令行跑一遍预览与 `--confirm`，记下输出和文件变化

### Phase 3：实测

- [ ] Task 6：实测「收件枢纽接入 → 开发线接入 → 建巡视任务并手动立即运行一次 → 卸载并删除任务」（Spec 验收 12）。先问用户，结果写进规格的实测记录

### Checkpoint 3（gate）：模块最终验收

- [ ] 全部测试全绿；12 条验收标准逐条有测试或实测记录；列出实际改动的文件；原样附上三个角色约定块的全文和规格的改动差异
- [ ] 本 Plan 获批即授权：
  - 每个任务完成后在当前分支做一次本地提交；
  - 在 scratchpad 里建临时项目目录和临时协作组。
- [ ] 不授权：Task 6 的实测（创建定时任务、登记测试身份，到时另外问你）、推送、开 PR

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| 放入或删除约定块时改动了用户自己写的内容 | 高 | 纯文本函数加逐字节比较的测试，覆盖块在开头、中间、结尾，以及有没有结尾换行 |
| 写到一半失败，名册和规则文件不一致 | 中 | 先校验后写；名册在规则文件之前写，重复接入可以替换，重跑就能补齐 |
| 约定块里的模板和 message-protocol 对不上，会话照抄后被退回 | 中 | 测试把模板交给 `protocol.parse`，要求认出类型且没有问题 |
| 实测建的定时任务留在用户机器上 | 低 | 实测最后一步就是卸载并删除任务；删不掉就如实告诉你，并给出删除方法 |

## Open Questions

无。
