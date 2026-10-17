# Todo: protocol-contract-v1

测试命令：`python3 -m unittest discover -s tests -v`

- [ ] Task 1：复制契约 v1.0 样例与一致性测试
  - 验收：Spec 验收 1、2、3（副本与来源说明、指纹核对；27 份解析、5 份生成全过，改坏即失败；原有 5 份与副本一致）
  - 验证：`python3 -m unittest discover -s tests -p test_contract.py -v`
  - 文件：`tests/fixtures/session-protocol/v1.0/`、`tests/test_contract.py`

- [ ] Task 2：能力图外部依赖、README「消息协议」、版本 0.0.8
  - 验收：Spec 验收 4、5
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`spec/CAPABILITY-MAP.md`、`README.md`、两份 `plugin.json`、`tests/test_packaging.py`

- [ ] Checkpoint（gate）：模块最终验收，等用户确认
