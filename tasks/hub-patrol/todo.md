# Todo: hub-patrol

测试命令：`python3 -m unittest discover -s tests -v`

- [x] Task 1：`patrolDue` 与 `--from-hub`
  - 验收：Spec 验收 1、2
  - 文件：`decision_inbox/hub.py`、`decision_inbox/patrol.py`、`decision_inbox/__main__.py`、`tests/test_hub.py`、`tests/test_patrol.py`、`tests/test_consume.py`
  - 记录（2026-10-18）：先写用例（登记 11 分钟没跑、最近一轮 11 分钟前为真，9 分钟内为假，没登记为假；`--from-hub` 不叫醒收件枢纽、计划记 `by`；receive／reply 输出 `patrolDue`），先报错；实现 `hub.patrol_due`、`HUB_PATROL_MINUTES = 10`、`patrol.plan(from_hub=)`、`Plan.by`、命令参数与输出。Ran 592 tests, OK

- [ ] Task 2：巡视记录来源与按来源统计
  - 验收：Spec 验收 3
  - 文件：`decision_inbox/patrol.py`、`decision_inbox/query.py`、`tests/test_patrol.py`、`tests/test_stats.py`

- [ ] Task 3：约定块加「顺带巡视」
  - 验收：Spec 验收 4
  - 文件：`decision_inbox/hub.py`、`tests/test_hub.py`

- [ ] Task 4：文档与版本 0.0.14
  - 验收：Spec 验收 5
  - 文件：`README.md`、`docs/host-differences.md`、两份 `plugin.json`、`tests/test_packaging.py`

- [ ] Checkpoint（gate）：实测，开始前另问用户

- [ ] Checkpoint（gate）：模块最终验收，等用户确认
