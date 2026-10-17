# Todo: wait-honesty-and-briefs

测试命令：`python3 -m unittest discover -s tests -v`

- [x] Task 1：A2 等待单可能已失效
  - 验收：Spec 验收 1（发送方之后有消息时标可能已失效；信号 1 与推送行不计入；只剩这类单时不报全线停住；「看等待」和计数行写明；「关掉 #N」照常；老记录从事件日志补读发送方）
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/hub.py`、`tickets.py`、`health.py`、`view.py`、对应测试
  - 记录（2026-10-17）：5 个新测试中 4 个先失败（「用户照常能关」实现前已通过）；实现后 Ran 502 tests, OK。和计划的差别：判断写成 `tickets.stale_tickets(g)`，直接读收件枢纽的收件记录和事件日志，没有用传函数的办法（读的数据一样，且 tickets 不依赖 hub）

- [x] Task 2：A3 区分没带、读不到、查不到
  - 验收：Spec 验收 2
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/health.py`、`hub.py`、`view.py`、`query.py`、`__main__.py`、对应测试
  - 记录（2026-10-17）：2 个改写的测试和 1 个新测试先失败；实现后 Ran 503 tests, OK。`view` 命令区分三种；`inbox reply` 回复里附的主视图仍只区分「带了」和「没带」（读不到时按没带写），影响小，留作观察

- [x] Task 3：A7 新事项默认取代
  - 验收：Spec 验收 3（默认取代同一会话同类待答事项；【并行】保留；单线多线互不取代；别的会话不动；回执提示；约定块一条改写）
  - 验证：`python3 -m unittest discover -s tests -p test_items.py -v`
  - 文件：`decision_inbox/items.py`、`onboard.py`、对应测试
  - 记录（2026-10-17）：新测试先失败；实现后 4 个原有测试按新规则失败（同一会话挂着多项未标记事项），逐个补【与 #旧 并行】，测试原意不变；Ran 507 tests, OK。新事项写了任何标记（取代或并行）时不做默认取代；提示走附注通道（和 F13 一样），没有单独发给发送方

- [x] Checkpoint 1（report）：全部测试全绿，记下命令与结果后继续
  - 记录（2026-10-17）：Ran 507 tests, OK

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
