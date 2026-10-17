<!-- spec-guard: review pending -->
# Spec: protocol-contract-v1

> 能力图模块 `protocol-contract-v1`（2026-10-18 用 add-module 插入，排在 doctor-and-observer 之后、relay-presence-and-doubt 之前）。来源：用户 2026-10-18 批准的契约迁移计划——共用契约仓库 `session-protocol` v1.0 以 decision-inbox 0.0.7 的现行行为为准，契约仓库只在本地，decision-inbox 侧作为模块乙之后的新模块；契约仓库已建（`~/Documents/haigeerlab/session-protocol`，提交 7585be8）。

## 目标

decision-inbox 钉住契约 v1.0：契约的样例在本插件的测试里逐份跑通，以后协议有改动先改契约、再改实现。行为不变。

## 关键决策与取舍（请重点审）

1. **样例按版本复制进本仓库**：`tests/fixtures/session-protocol/v1.0/` 原样复制契约的 `fixtures/`（含 `SHA256SUMS`），旁边放 `SOURCE`，写契约版本 v1.0 和契约仓库提交号。测试运行时不读契约仓库。
2. **一致性测试** `tests/test_contract.py`：
   - 先核对 `SHA256SUMS`，样例被就地改过就失败；
   - 有 `parse` 的样例：用 `protocol.parse` 解析，经测试里的转换函数换成契约字段，与期望逐项比较；
   - 有 `generate` 的样例：用 `format_user_reply`、`format_multiline_replies`、`format_answer_notice` 按 `inputs` 生成，与原文逐字比较；
   - `answer-notice` 只生成不解析（收件枢纽发出、开发线读），按契约的一致性说明跳过解析。
3. **转换函数放在测试里**，不进产品代码：契约字段名只在一致性测试里用，产品代码继续用内部名。
4. **原有的 5 份 `tests/fixtures/protocol/` 样例保留**，现有协议测试照旧用它们；契约样例里已含同样的 5 份，测试里核对两边内容一致，以后改协议时两边一起改。
5. **指向契约的位置**：不改已验收的 `spec/message-protocol.md`（改了要重新评审）；改为在能力图「外部依赖」表加一行 `session-protocol v1.0`，在 README 加一小节「消息协议」说明以契约为准。这与已批准计划里「message-protocol 规格加一行」不同，请确认。
6. **版本 0.0.8**。

## 范围

做：`tests/fixtures/session-protocol/v1.0/`（复制）、`tests/test_contract.py`、`spec/CAPABILITY-MAP.md` 外部依赖表一行、`README.md`、两份 `plugin.json`。

不做：

- 改解析或生成代码：样例跑不过时先查是样例错还是代码错，停下来问用户，不顺手改行为。
- 契约 v1.1（【交审】【公共变更请求】【协调通知】）：另行批准后再做。
- 契约仓库的远端。

## 接口约定

```python
# tests/test_contract.py
to_contract(msg: protocol.Message) -> dict   # 契约 PROTOCOL.md 第 12 节的字段
```

## 测试策略

- 一致性测试本身先在「改坏一份期望结果」「改坏一份样例」两种情况下各跑一次，确认会失败（变异检查），再还原。
- 全部测试全绿。

## 边界

- 始终：行为不变；契约样例只读复制，不在本仓库改。
- 先问：样例与代码不一致时怎么处理。
- 绝不：为让测试通过改契约样例。

## 验收标准

1. 本仓库有契约 v1.0 样例的原样副本和来源说明，指纹核对通过。
2. 一致性测试对 27 份解析样例逐项比较、对 5 份生成样例逐字比较，全部通过；改坏样例或期望时测试失败。
3. 原有 5 份样例与契约副本内容一致。
4. 能力图外部依赖表与 README 写明以契约 v1.0 为准。
5. 两份清单 0.0.8；原有测试全部通过。

## 假设

1. 契约仓库提交 7585be8 的样例由本插件 0.0.7 的代码生成并人工核对过，本插件现有代码（0.0.7）应当全部跑通。
2. 契约以后由用户批准改动；本插件升级契约版本时复制新版本样例另开模块。

## 未决问题

1. 第 5 条：指向契约写在能力图和 README（推荐），还是按原计划改 `spec/message-protocol.md`（改后该规格要重新评审）。

## 文档建议

README 加「消息协议」一小节：各会话之间的消息格式以 `session-protocol` v1.0 为准，本插件测试里跑契约样例。
