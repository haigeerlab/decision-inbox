# Todo: transition-compat

测试命令：`python3 -m unittest discover -s tests -v`

- [ ] Task 1：契约升到 v1.7
  - 验收：Spec 验收 6
  - 文件：`tests/fixtures/session-protocol/v1.7/`（删掉 v1.5）、`tests/test_contract.py`、`README.md`

- [ ] Task 2：`legacyFormat` 字段、`onboard enroll`、leave 只登记的条目
  - 验收：Spec 验收 1；验收 5 里 leave 的部分
  - 文件：`decision_inbox/store.py`、`decision_inbox/onboard.py`、`decision_inbox/__main__.py`、`tests/test_store_roster.py`、`tests/test_onboard.py`

- [ ] Task 3：输出旧写法；答复告知、多线事项跳过旧格式和已退出的会话
  - 验收：Spec 验收 2、3、5
  - 文件：`decision_inbox/protocol.py`、`decision_inbox/items.py`、`decision_inbox/hub.py`、相应测试

- [ ] Task 4：认旧编号；退回说明写双编号
  - 验收：Spec 验收 4
  - 文件：`decision_inbox/items.py`、`tests/test_items.py`

- [ ] Task 5：约定块写明【负责人转交】
  - 验收：Spec 验收 7
  - 文件：`decision_inbox/onboard.py`、`tests/test_onboard.py`

- [ ] Task 6：文档和版本 0.0.17
  - 验收：Spec 验收 8
  - 文件：`README.md`、`commands/leave.md`、两份 `plugin.json`、`tests/test_packaging.py`

### Checkpoint（gate）：模块最终验收

- [ ] 全部测试通过；每条验收标准都有证据；列出实际改动的文件
