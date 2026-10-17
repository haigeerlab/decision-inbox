# Todo: protocol-contract-v1-3

测试命令：`python3 -m unittest discover -s tests -v`

- [x] Task 1：换 v1.3 样例、跳过名单、变异检查
  - 验收：Spec 验收 1、2、3
  - 验证：`python3 -m unittest discover -s tests -p test_contract.py -v`
  - 文件：`tests/fixtures/session-protocol/`、`tests/test_contract.py`
  - 记录（2026-10-18）：先改测试（版本、来源、样例数 45／5、跳过三类 15 份），在 v1.0 副本上 1 失败 7 报错；从契约 42fe5f6 `git archive` 取出 v1.3 样例替换后 `shasum -c` 通过、一致性测试 6 个全过。变异检查：分别去掉「详见」「已明确」「同上」，各只有对应的一份样例失败（brief-thin-see-detail、brief-thin-already-clear、brief-thin-ditto）；还原后产品代码无改动。Ran 568 tests, OK

- [ ] Task 2：能力图、README、版本 0.0.10、通知契约负责人
  - 验收：Spec 验收 4、5
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`spec/CAPABILITY-MAP.md`、`README.md`、两份 `plugin.json`、`tests/test_packaging.py`

- [ ] Checkpoint（gate）：模块最终验收，等用户确认
