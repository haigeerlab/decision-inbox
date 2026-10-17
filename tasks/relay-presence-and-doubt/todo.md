# Todo: relay-presence-and-doubt

测试命令：`python3 -m unittest discover -s tests -v`

- [ ] Task 1：relay-reader 读出 activity、doubtfulIds、wake.doubt
  - 验收：有、无三个字段的输入都能读；旧版本输出读出 None／空
  - 验证：`python3 -m unittest discover -s tests -p test_relay.py -v`
  - 文件：`decision_inbox/relay.py`、`tests/test_relay.py`

- [ ] Task 2：干活中、信号 5 拆分、没带状态不报全线停住、各线一行说实话
  - 验收：Spec 验收 1、4、5
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/health.py`、`view.py`、对应测试

- [ ] Checkpoint 1（report）：全部测试全绿，记下命令与结果后继续

- [ ] Task 3：送达存疑的异常行、巡视通知、`/item` 措辞
  - 验收：Spec 验收 2
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/health.py`、`view.py`、`patrol.py`、`query.py`、对应测试

- [ ] Task 4：收件枢纽 `alsoAnswers` 与约定块 `withdraws`
  - 验收：Spec 验收 3
  - 验证：`python3 -m unittest discover -s tests -p "test_hub.py" -v`
  - 文件：`decision_inbox/hub.py`、`onboard.py`、对应测试

- [ ] Task 5：停止钩子说明、需求记录、README、版本 0.0.9
  - 验收：Spec 验收 6、7
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/stophook.py`、`docs/requirements-record.md`、`README.md`、两份 `plugin.json`、对应测试

- [ ] Checkpoint 2（report）：全部测试全绿；scratchpad 临时协作组命令行实跑主视图与 `/item`，记下输出；推送本分支

- [ ] Task 6：实测 owesReplies 回落
  - 验收：Spec 验收 8
  - 说明：先问用户

- [ ] Checkpoint 3（gate）：模块最终验收，等用户确认
