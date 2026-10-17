<!-- spec-guard: review pending -->
# Spec: protocol-contract-v1-3

> 能力图模块 `protocol-contract-v1-3`（2026-10-18 用 add-module 插入，排在 relay-presence-and-doubt 之后）。来源：session-protocol 契约负责人 2026-10-18 通知 v1.3 已提交（42fe5f6，用户批准），补上了 protocol-contract-v1 验收时发现缺的过简要点样例；用户 2026-10-18 决定先做这个升级，再开始第 ⑥ 阶段实地验收。

## 目标

decision-inbox 钉住的契约从 v1.0 升到 v1.3，让一致性测试能抓到「要点够行数、但含过简词」的规则。产品代码不改，行为不变。

## v1.0 → v1.3 的变化（已在临时目录核对）

- v1.1（78da46f）：新增【交审】【公共变更请求】【协调通知】三种消息和它们的 15 份样例；decision-inbox 不解析这三种。
- v1.2（1bc5ce7）：`unknown/unknown-kind` 样例的标签由【交审】改为【未定义的标签】，期望结果不变。
- v1.3（42fe5f6）：新增 `wait-user/brief-thin-see-detail`、`brief-thin-already-clear`、`brief-thin-ditto`，要点各 2 行、各含一个过简词，期望 hints 为 `brief-thin`、problems 为空。
- 用现有代码试跑 v1.3：decision-inbox 负责的 30 份解析样例、5 份生成样例全部一致；对不上的只有三种新消息的 15 份。

## 关键决策与取舍（请重点审）

1. **替换，不并存**：`tests/fixtures/session-protocol/v1.0/` 换成 `v1.3/`，样例从契约仓库提交 42fe5f6 原样取出（`git archive`），`SOURCE` 写 v1.3 和 42fe5f6。只钉一个版本，升级就是换一份样例再跑通（契约一致性说明的做法）。
2. **跳过名单写在测试里**：`review-request`、`shared-change-request`、`coordination-notice` 三类不解析也不生成，跳过；`answer-notice` 仍是只生成。跳过名单就是本插件在契约里登记的「不解析」范围，测试里同时断言这三类的样例数，契约以后再加样例时测试会提醒。
3. **变异检查补上过简词**：分别把「详见」「已明确」「同上」从过简词表里去掉，确认各有一份 v1.3 样例失败，再还原。
4. **契约仓库的登记行由契约负责人改**：本模块不改契约仓库；做完后通知契约负责人把 conformance 说明里 decision-inbox 一行改成「钉住 v1.3（42fe5f6），跳过 review-request、shared-change-request、coordination-notice」。
5. **文档与版本**：能力图外部依赖表与 README「消息协议」一节里的 v1.0 改为 v1.3；两份 `plugin.json` 升到 0.0.10。

## 范围

做：`tests/fixtures/session-protocol/`（换成 v1.3）、`tests/test_contract.py`、`spec/CAPABILITY-MAP.md` 外部依赖表一行、`README.md`、两份 `plugin.json`、`tests/test_packaging.py`。

不做：解析三种新消息（decision-inbox 不需要）；改解析或生成代码；改契约仓库。

## 验收标准

1. 样例副本是契约 42fe5f6 的原样内容，指纹核对通过，`SOURCE` 写明 v1.3。
2. 一致性测试：30 份解析样例逐项、5 份生成样例逐字全部通过；三类新消息按名单跳过，测试写明跳过数。
3. 三个过简词各被一份样例抓到（变异检查记录）。
4. 能力图与 README 写 v1.3；两份清单 0.0.10；原有测试全部通过。
5. 已通知契约负责人更新登记行。

## 假设

1. 契约 42fe5f6 之后的提交（ad18325、a4d7fff）只改 conformance 说明，不改样例（已核对 `git diff --stat`）。
2. 契约以后加新消息类型时，decision-inbox 是否要解析，届时另开模块决定。

## 未决问题

无。

## 文档建议

README「消息协议」一节写明钉住 v1.3 和跳过的三类消息。
