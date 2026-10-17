<!-- spec-guard: review pending -->
# Implementation Plan: protocol-contract-v1-4

> 依据：`spec/protocol-contract-v1-4.md`（与本计划一起交审）。任务清单：`tasks/protocol-contract-v1-4/todo.md`。

## Overview

两个任务：先把测试里的契约样例从 v1.3 换成 v1.4、调计数、做变异检查；再改文档、升版本、通知契约负责人。产品代码不改。

## Architecture Decisions

- 样例从契约仓库提交 e33c077 用 `git archive` 取出，替换 `tests/fixtures/session-protocol/v1.3/`，新目录 `v1.4/`；`SOURCE` 写 session-protocol、v1.4、e33c077。
- `tests/test_contract.py`：`VERSION` 改 v1.4，来源提交改 e33c077；解析计数 52、生成计数 6，跳过名单与跳过数 15 不变。

## Task List

- [ ] Task 1：换 v1.4 样例、调计数、变异检查（Spec 验收 1、2、3）
- [ ] Task 2：能力图、README、版本 0.0.11、通知契约负责人（Spec 验收 4、5）

### Checkpoint（gate）：模块最终验收

- [ ] 全部测试全绿；5 条验收标准逐条有证据；列出实际改动的文件
- [ ] 本 Plan 获批即授权：替换样例副本、改一致性测试、改能力图与 README、版本升到 0.0.11；每个任务完成后本地提交并推送本分支；给契约负责人发消息
- [ ] 不授权：改契约仓库、改产品代码、开或合并 PR
