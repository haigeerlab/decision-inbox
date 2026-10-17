# Todo: patrol-cadence

测试命令：`python3 -m unittest discover -s tests -v`

- [x] Task 1：停摆提示写两种原因
  - 验收：Spec 验收 1
  - 文件：`decision_inbox/hub.py`、`decision_inbox/doctor.py`、`tests/test_hub.py`、`tests/test_doctor.py`、`tests/test_query.py`
  - 记录（2026-10-18）：先改主视图期望文字、doctor 断言含两种原因，4 失败；新增 `hub.patrol_fix`，主视图、/flow、doctor 共用。Ran 585 tests, OK

- [ ] Task 2：`query stats` 加巡视节奏
  - 验收：Spec 验收 2
  - 文件：`decision_inbox/query.py`、`tests/test_stats.py`

- [ ] Task 3：文档与版本 0.0.13
  - 验收：Spec 验收 3、4
  - 文件：`README.md`、`docs/stage6-field-acceptance.md`、两份 `plugin.json`、`tests/test_packaging.py`

- [ ] Checkpoint（gate）：模块最终验收，等用户确认
