# Todo: patrol-cadence

测试命令：`python3 -m unittest discover -s tests -v`

- [x] Task 1：停摆提示写两种原因
  - 验收：Spec 验收 1
  - 文件：`decision_inbox/hub.py`、`decision_inbox/doctor.py`、`tests/test_hub.py`、`tests/test_doctor.py`、`tests/test_query.py`
  - 记录（2026-10-18）：先改主视图期望文字、doctor 断言含两种原因，4 失败；新增 `hub.patrol_fix`，主视图、/flow、doctor 共用。Ran 585 tests, OK

- [x] Task 2：`query stats` 加巡视节奏
  - 验收：Spec 验收 2
  - 文件：`decision_inbox/query.py`、`decision_inbox/__main__.py`、`tests/test_stats.py`
  - 记录（2026-10-18）：先在构造的事件里加 5 轮巡视并写用例（全部：5 轮、最长隔 1350 分钟、超 15 分钟 2 次；10-18 起：2 轮、4 分钟、0 次；无数据），2 失败 1 报错；实现 `_patrol_cadence`（按 data.now 排序）、文本一行、`query stats --json`（schemaVersion 1，含 patrolRuns／patrolMaxGap／patrolStale）。Ran 586 tests, OK

- [ ] Task 3：文档与版本 0.0.13
  - 验收：Spec 验收 3、4
  - 文件：`README.md`、`docs/stage6-field-acceptance.md`、两份 `plugin.json`、`tests/test_packaging.py`

- [ ] Checkpoint（gate）：模块最终验收，等用户确认
