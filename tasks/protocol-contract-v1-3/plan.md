<!-- spec-guard: review approved -->
# Implementation Plan: protocol-contract-v1-3

> 依据：`spec/protocol-contract-v1-3.md`（已批准）。任务清单：`tasks/protocol-contract-v1-3/todo.md`。用户 2026-10-18 与规格一起批准本计划。

## Overview

两个任务：先把测试里的契约样例从 v1.0 换成 v1.3 并加跳过名单、做变异检查；再改文档、升版本、通知契约负责人。产品代码不改。

## Architecture Decisions

- 样例从契约仓库提交 42fe5f6 用 `git archive` 取出，替换 `tests/fixtures/session-protocol/v1.0/`，新目录 `v1.3/`；`SOURCE` 写 session-protocol、v1.3、42fe5f6。
- `tests/test_contract.py`：`VERSION` 改 v1.3；新增 `NOT_PARSED = {"review-request", "shared-change-request", "coordination-notice"}`，解析与生成都跳过；断言解析样例 45 份（其中检查 30 份）、生成 5 份、跳过的三类共 15 份。
- 原有 5 份 `tests/fixtures/protocol/` 样例与 v1.3 副本对照（这 5 份在 v1.3 里没变）。

## Task List

- [ ] Task 1：换 v1.3 样例、跳过名单、变异检查（Spec 验收 1、2、3）
- [ ] Task 2：能力图、README、版本 0.0.10、通知契约负责人（Spec 验收 4、5）

### Checkpoint（gate）：模块最终验收

- [ ] 全部测试全绿；5 条验收标准逐条有证据；列出实际改动的文件
- [ ] 本 Plan 获批即授权：替换样例副本、改一致性测试、改能力图与 README、版本升到 0.0.10；每个任务完成后本地提交并推送本分支；给契约负责人发消息
- [ ] 不授权：改契约仓库、改产品代码、开或合并 PR
