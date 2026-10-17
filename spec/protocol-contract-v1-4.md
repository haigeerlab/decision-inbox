<!-- spec-guard: review pending -->
# Spec: protocol-contract-v1-4

> 能力图模块 `protocol-contract-v1-4`（2026-10-18 用 add-module 插入，排在 protocol-contract-v1-3 之后）。来源：session-protocol 契约负责人 2026-10-18 通知 v1.4 已提交（e33c077，用户批准）；用户 2026-10-18 同意升级，规格与计划一起交审。

## 目标

decision-inbox 钉住的契约从 v1.3 升到 v1.4，让「架构审查：」行的取值和「用户原话」首行空白的读法有契约样例保护。产品代码不改，行为不变。

## v1.3 → v1.4 的变化（已在临时目录核对）

- PROTOCOL.md 第 3 节写明「架构审查：」行的五种写法与状态代码、末尾审查编号、半角逗号与半角括号按全角读、对不上记 `unrecognized`（照本插件 `protocol._review` 的现行做法）；写明「用户原话」的「一字不改」管发出的正文，解析读回时首行首尾空白去掉。第 12 节补全 `reviewLine` 三项取值。
- 新增 7 份样例：`wait-user/review-passed-ref`、`review-advice-halfwidth`、`review-in-progress`、`review-not-applicable`、`review-waived`、`review-unrecognized`；`user-reply/original-whitespace`（同时有生成与解析）。
- `git diff 42fe5f6 e33c077 -- fixtures` 只有新增，没有删除或改动；已有样例的期望结果不变。
- 用现有代码试跑 v1.4（临时目录）：解析样例 52 份、生成样例 6 份，Ran 568 tests, OK。

## 关键决策与取舍（请重点审）

1. **替换，不并存**：`tests/fixtures/session-protocol/v1.3/` 换成 `v1.4/`，样例从契约仓库提交 e33c077 用 `git archive` 原样取出，`SOURCE` 写 v1.4 和 e33c077。做法同 protocol-contract-v1-3。
2. **跳过名单不变**：仍跳过 `review-request`、`shared-change-request`、`coordination-notice` 三类（15 份）；`answer-notice` 仍只生成。
3. **计数**：解析样例 45 → 52，生成样例 5 → 6。
4. **变异检查**：分别临时去掉 `protocol._review` 里「半角逗号、半角括号转全角」和 `protocol.parse` 读字段时去首尾空白这两处，确认各有新样例失败（`review-advice-halfwidth`、`user-reply/original-whitespace`），再还原。
5. **契约仓库的登记行由契约负责人改**：做完后通知对方把 decision-inbox 一行改为钉住 v1.4（e33c077）。
6. **文档与版本**：能力图外部依赖表与 README「消息协议」一节里的 v1.3 改为 v1.4；两份 `plugin.json` 升到 0.0.11。

## 范围

做：`tests/fixtures/session-protocol/`（换成 v1.4）、`tests/test_contract.py`、`spec/CAPABILITY-MAP.md` 外部依赖表一行、`README.md`、两份 `plugin.json`、`tests/test_packaging.py`。

不做：改解析或生成代码；改契约仓库；解析三种不解析的消息。

## 验收标准

1. 样例副本是契约 e33c077 的原样内容，指纹核对通过，`SOURCE` 写明 v1.4。
2. 一致性测试：解析样例 52 份、生成样例 6 份全部通过；三类按名单跳过，跳过数仍为 15。
3. 变异检查记录：半角符号读法、原话首行空白各被一份新样例抓到。
4. 能力图与 README 写 v1.4；两份清单 0.0.11；原有测试全部通过。
5. 已通知契约负责人更新登记行。

## 假设

1. 契约 e33c077 是 v1.4 的最终样例；之后若只改 conformance 说明，不影响本模块。
2. 第 ⑥ 阶段实地验收 P0 与本模块互不依赖，可以穿插进行。

## 未决问题

无。

## 文档建议

README「消息协议」一节把 v1.3 改为 v1.4。
