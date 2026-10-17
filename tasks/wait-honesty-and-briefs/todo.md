# Todo: wait-honesty-and-briefs

测试命令：`python3 -m unittest discover -s tests -v`

- [ ] Task 1：A2 等待单可能已失效
  - 验收：Spec 验收 1（发送方之后有消息时标可能已失效；信号 1 与推送行不计入；只剩这类单时不报全线停住；「看等待」和计数行写明；「关掉 #N」照常；老记录从事件日志补读发送方）
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/hub.py`、`tickets.py`、`health.py`、`view.py`、对应测试

- [ ] Task 2：A3 区分没带、读不到、查不到
  - 验收：Spec 验收 2
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/health.py`、`hub.py`、`view.py`、`query.py`、`__main__.py`、对应测试

- [ ] Task 3：A7 新事项默认取代
  - 验收：Spec 验收 3（默认取代同一会话同类待答事项；【并行】保留；单线多线互不取代；别的会话不动；回执提示；约定块一条改写）
  - 验证：`python3 -m unittest discover -s tests -p test_items.py -v`
  - 文件：`decision_inbox/items.py`、`onboard.py`、对应测试

- [ ] Checkpoint 1（report）：全部测试全绿，记下命令与结果后继续

- [ ] Task 4：B1 约定硬规则与停止钩子检查
  - 验收：Spec 验收 4
  - 验证：`python3 -m unittest discover -s tests -p test_stophook.py -v`
  - 文件：`decision_inbox/stophook.py`、`onboard.py`、对应测试

- [ ] Task 5：B2、B5、邮箱派活、README、版本 0.0.6
  - 验收：Spec 验收 5、6、7、8
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/protocol.py`、`onboard.py`、`hub.py`、`README.md`、两份 `plugin.json`、对应测试

- [ ] Checkpoint 2（report）：全部测试全绿；scratchpad 临时协作组命令行实跑，记下输出；推送本分支

- [ ] Task 6：di-e2e 实测
  - 验收：Spec 验收 9
  - 说明：先问用户

- [ ] Checkpoint 3（gate）：模块最终验收，等用户确认
