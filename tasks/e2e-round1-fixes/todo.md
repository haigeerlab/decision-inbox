# Todo: e2e-round1-fixes

测试命令：`python3 -m unittest discover -s tests -v`

- [x] Task 1：答复、多线答复、告知写原消息号
  - 验收：Spec 验收 1（三种正文都带「原消息 #R」；`source_relay_id` 为空时正文不变；带括号的「事项」解析出的事项号不变）；F1 回归：开发A 抛 #4540，答「1 A」，答复正文含「你的原消息 #4540」
  - 验证：`python3 -m unittest discover -s tests -p "test_*.py" -v`
  - 文件：`decision_inbox/protocol.py`、`items.py`、`hub.py`、对应测试
  - 记录（2026-10-17）：4 个新测试先失败；实现后 Ran 451 tests, OK。【答复告知】本来不被 `protocol.parse` 识别（kind 为 unknown），测试改为只核对正文

- [x] Task 2：开发线追问自动退回
  - 验收：Spec 验收 3（标了要回复或填了 replyTo 的未知消息退回；replyTo 指向已发答复或告知时第三行带事项号和原消息号；主视图附注照旧；异常计数加一）、验收 4（回复退回消息、bridge 通知不退回；没标要回复的未知消息只记附注）；F2 回归：#4543 产生退回
  - 验证：`python3 -m unittest discover -s tests -p test_hub.py -v`
  - 文件：`decision_inbox/hub.py`、`view.py`（若需要）、`tests/test_hub.py`
  - 记录（2026-10-17）：5 个新测试先失败；实现后全量 Ran 456 tests, OK。变异检查：去掉「不退回对退回的回复」，被 `test_no_return_for_plain_notes_bridge_or_replies_to_a_return` 抓住。异常行经 `view.render(extra=…)` 进入主视图的异常段和计数

- [x] Checkpoint 1（report）：全部测试全绿，记下命令与结果后继续
  - 记录（2026-10-17）：`python3 -m unittest discover -s tests -v` → Ran 456 tests, OK

- [x] Task 3：`inbox reply --relayed-from`
  - 验收：Spec 验收 5（不改事项和等待单；记 `hub.relayed-input`，actor 为来源；提示含来源、原话和「请你在这里亲手回一遍」）
  - 验证：`python3 -m unittest discover -s tests -p "test_hub.py" -v` 和命令行测试
  - 文件：`decision_inbox/hub.py`、`__main__.py`、对应测试
  - 记录（2026-10-17）：3 个新测试先失败；实现后 Ran 459 tests, OK。转来的话（包括「以后 X 都这样」）都不进入任何解析分支

- [x] Task 4：巡视停摆报警
  - 验收：Spec 验收 7（从没跑完且登记超过 15 分钟、最近一轮超过 15 分钟都报警；15 分钟内不报；没登记巡视任务不报；老协作组没有 `patrolTaskAt` 时只按 `lastRunAt` 判断；主视图和 `query flow` 第一行都有）
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/hub.py`、`onboard.py`、`__main__.py`、对应测试
  - 记录（2026-10-17）：7 个新测试和断言先失败；实现后 Ran 465 tests, OK。判断函数 `hub.patrol_alarm` 由主视图和 `query flow` 共用，阈值常量 `PATROL_STALE_MINUTES = 15`

- [ ] Task 5：「在等谁」认身份名
  - 验收：Spec 验收 9
  - 验证：`python3 -m unittest discover -s tests -p test_tickets.py -v`
  - 文件：`decision_inbox/tickets.py`、`tests/test_tickets.py`

- [ ] Task 6：卸载删掉空的新建规则文件
  - 验收：Spec 验收 10（新建且删块后为空才删；原有文件、另加了内容的新建文件都保留；预览写明会删；静态扫描只放行 `_drop_created_rules`）
  - 验证：`python3 -m unittest discover -s tests -p "test_onboard.py" -v`、`-p test_package.py`
  - 文件：`decision_inbox/onboard.py`、`tests/test_onboard.py`、`tests/test_package.py`

- [ ] Checkpoint 2（report）：全部测试全绿；scratchpad 临时协作组上命令行跑一遍 S0 和各项新行为，记下输出后继续

- [ ] Task 7：约定块、hub-setup、README、需求记录、版本 0.0.4
  - 验收：Spec 验收 2、6、8、11
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/onboard.py`、`hub.py`、`commands/hub-setup.md`、`README.md`、`docs/requirements-record.md`、两份 `plugin.json`、对应测试

- [ ] Checkpoint 3（report）：全部测试全绿；推送本分支、开 PR（不合并）；给 spec-guard-monitor 发会话消息说明可以重跑，附分支、版本和改动要点

- [ ] Task 8：spec-guard-monitor 在 di-e2e 重跑 S0
  - 验收：Spec 验收 12；结果写进规格的实测记录
  - 说明：重跑由 spec-guard-monitor 主持，本会话不动测试环境

- [ ] Checkpoint 4（gate）：模块最终验收，等用户确认
