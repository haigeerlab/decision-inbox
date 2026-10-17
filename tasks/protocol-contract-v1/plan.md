<!-- spec-guard: review pending -->
# Implementation Plan: protocol-contract-v1

> 依据：`spec/protocol-contract-v1.md`（已批准）。任务清单：`tasks/protocol-contract-v1/todo.md`。

## Overview

两个任务：先把契约 v1.0 的样例原样复制进测试并写一致性测试（变异检查确认它真会失败），再写明以契约为准、升版本。产品代码不改。

## Architecture Decisions

- **样例来源**：从契约仓库的标签 `v1.0`（提交 7585be8）取，`git -C <契约仓库> archive v1.0 fixtures | tar -x`，不从工作区复制——另一个会话正在工作区里写 v1.1，还没提交。
- **`SOURCE` 文件**：三行：契约名 session-protocol、版本 v1.0、提交 7585be8。
- **`tests/test_contract.py`**：
  - `to_contract(msg)` 把 `protocol.Message` 换成契约字段（与生成期望结果时用的转换一致）；
  - 指纹：读 `SHA256SUMS`，逐个文件算 sha256 比较，文件多了或少了也算失败；
  - 解析：每个带 `parse` 的 `.json`，只比较 `parse` 里出现的键（契约一致性说明的写法）；
  - 生成：`user-reply`、`multiline-user-reply`（`waitUserFixture` 指向副本里的样例、取 `forSession` 那一版）、`answer-notice`，逐字比较；
  - 原有 5 份样例与副本里对应文件逐字相同。
- **变异检查**：临时改坏一份期望结果、改坏一份样例原文，各跑一次一致性测试确认失败，再还原（还原后指纹核对通过）。
- **文档**：能力图「外部依赖」表加一行 `protocol-contract-v1 | session-protocol | v1.0 样例（tests/fixtures/session-protocol/v1.0/） | 已钉住`；README 加「消息协议」一小节。
- **版本**：两份 `plugin.json` 升到 0.0.8，打包测试的版本断言随之改。

## 影响面

- 新增：`tests/fixtures/session-protocol/v1.0/`（56 个文件 + `SHA256SUMS` + `SOURCE`）、`tests/test_contract.py`。
- 修改：`spec/CAPABILITY-MAP.md`（外部依赖表一行）、`README.md`、两份 `plugin.json`、`tests/test_packaging.py`。
- 产品代码不改；用户可见界面不变。
- 最大风险：样例与现有代码不一致。按规格，遇到就停下问用户，不顺手改代码或样例。

## Task List

- [ ] Task 1：复制契约 v1.0 样例与一致性测试（Spec 验收 1、2、3）
- [ ] Task 2：能力图外部依赖、README「消息协议」、版本 0.0.8（Spec 验收 4、5）

### Checkpoint（gate）：模块最终验收

- [ ] 全部测试全绿；5 条验收标准逐条有证据；列出实际改动的文件；规格有改动时原样附上差异
- [ ] 本 Plan 获批即授权：在本仓库新增样例副本与一致性测试、改能力图外部依赖表与 README、版本升到 0.0.8；每个任务完成后本地提交并推送本分支；在契约仓库只做只读读取（`git archive`）
- [ ] 不授权：改解析或生成代码、改契约仓库的内容、开或合并 PR
