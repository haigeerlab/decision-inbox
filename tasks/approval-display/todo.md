# Todo: approval-display

- [x] Task 1：改钉契约 v2.1（Spec 验收 1）
  - 验证：`tests/test_contract.py` 指纹 188 行、解析样例全过；原有测试全过
- [ ] Task 2：取原文 `sources.py`（Spec 验收 2、3）
  - 验证：`tests/test_sources.py`：全文逐字一致（含 150KB）、上一版差异、六种读不到各一条
- [ ] Task 3：记录与背景 `approval.py`（Spec 验收 4）
  - 验证：`tests/test_approval.py`：能力图位置（假 /map）、/map 读不到、模块节点、第几次交审与上次原话、相关决定
- [ ] Checkpoint A（report）：前三个任务测试全过
- [ ] Task 4：审批项展示（Spec 验收 2、5）
  - 验证：`tests/test_view.py`：段落顺序、无代码块、原文逐字一致、读不到写原因
- [ ] Task 5：主视图排布与「看 N」（Spec 验收 6）
  - 验证：`tests/test_view.py`、`tests/test_hub.py`：第一项展开其余一行、「看 N」、「N 详情」照旧、一次答完跳过
- [ ] Task 6：多模块分节（Spec 验收 7）
  - 验证：`tests/test_view.py`、`tests/test_hub.py`：按模块分节、回执提示「按决定 47」
- [ ] Task 7：R17 验收标准与证据对照（Spec 验收 8）
  - 验证：`tests/test_approval.py`：缺证据标记、Spec 取不到写明
- [ ] Checkpoint B（report）：测试全过
- [ ] Task 8：R15 规则、README、解耦快照（Spec 验收 9、10）
  - 验证：`tests/test_onboard.py` 三种角色；普通卡片快照；`python3 -m unittest discover -s tests` 全过

## Checkpoint（gate）：模块最终验收

- [ ] 全部测试通过；每条验收标准有证据；列出实际改动的文件；实际渲染一个审批项给用户看
- [ ] 实测（Spec 验收 11）放到冻结之后，开始前另问用户
