# Todo: relay-presence-and-doubt

测试命令：`python3 -m unittest discover -s tests -v`

- [x] Task 1：relay-reader 读出 activity、doubtfulIds、wake.doubt
  - 验收：有、无三个字段的输入都能读；旧版本输出读出 None／空
  - 验证：`python3 -m unittest discover -s tests -p test_relay.py -v`
  - 文件：`decision_inbox/relay.py`、`tests/test_relay.py`
  - 记录（2026-10-18）：2 个新测试先报错；实现后 Ran 555 tests, OK。`activity` 只认 busy／idle，其他值读成 None；三个新字段都有默认值，旧输出不受影响

- [x] Task 2：干活中、信号 5 拆分、没带状态不报全线停住、各线一行说实话
  - 验收：Spec 验收 1、4、5
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/health.py`、`view.py`、对应测试
  - 记录（2026-10-18）：5 个新测试先失败；实现后 1 个原有测试（wait-honesty-and-briefs 的「新等待单照常算信号 1」）按规格第 4 条失败，它没带 agent-relay 状态；改为带一份空状态断言会报、并加一句没带时不报。Ran 560 tests, OK。建议文字改为可按信号代码区分（`idle-backlog` 与 `busy-backlog` 同属信号 5）

- [x] Checkpoint 1（report）：全部测试全绿，记下命令与结果后继续
  - 记录（2026-10-18）：`python3 -m unittest discover -s tests` → Ran 560 tests, OK

- [x] Task 3：送达存疑的异常行、巡视通知、`/item` 措辞
  - 验收：Spec 验收 2
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/health.py`、`view.py`、`patrol.py`、`query.py`、对应测试
  - 记录（2026-10-18）：4 个新测试先失败（3 失败 1 报错）；实现后 Ran 564 tests, OK。新信号 11 `delivery-doubt`，文字带存疑编号和来源；巡视通知的键含信号文字，同一批编号只通知一次，编号变了再通知

- [x] Task 4：收件枢纽 `alsoAnswers` 与约定块 `withdraws`
  - 验收：Spec 验收 3
  - 验证：`python3 -m unittest discover -s tests -p "test_hub.py" -v`
  - 文件：`decision_inbox/hub.py`、`onboard.py`、对应测试
  - 记录（2026-10-18）：5 个新断言先失败（4 失败 1 报错）；实现后 Ran 568 tests, OK。和计划的差别：`alsoAnswers` 只在有编号时出现在 send 里（没有的不加这个键，原有测试不受影响）；放过的编号记在收件枢纽状态的 `alsoClosed`，下次不重复；「重发」时照样带上。已接入的协作组需要重跑接入命令才能拿到新约定块（doctor 会报「约定块不是当前版本」）

- [x] Task 5：停止钩子说明、需求记录、README、版本 0.0.9
  - 验收：Spec 验收 6、7
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/stophook.py`、`docs/requirements-record.md`、`README.md`、两份 `plugin.json`、对应测试
  - 记录（2026-10-18）：先改停止钩子两处整段期望、版本和 README 断言，4 个失败；实现后 Ran 568 tests, OK。需求记录 13.5 末尾补了转给 agent-relay 的用例（只读的发件查询）；README 使用注意事项改一行、排查表加一行

- [x] Checkpoint 2（report）：全部测试全绿；scratchpad 临时协作组命令行实跑主视图与 `/item`，记下输出；推送本分支
  - 记录（2026-10-18）：Ran 568 tests, OK（含契约一致性测试）。scratchpad 临时协作组 cp5（收件枢纽、负责人、一条 Codex 开发线），手写 agent-relay 输出：
    1. 开发连发两条【等待用户】#6001、#6002：回执「#1 已被新事项自动取代」；用户答「2 A」后 `sends` 为 `{to: cp5-dev, replyTo: 6002, alsoAnswers: [6001]}`；
    2. 主视图（带 0.8.2 状态）：「负责人 阻塞：等开发」（短名）；异常区「负责人 空闲，有 2 条消息没读。建议：巡视会叫醒 负责人；叫不醒就打开它」「开发 有 1 条消息送达存疑（#6012）（来源：agent-relay）。建议：完全退出 ChatGPT 再打开 开发 的任务」；
    3. 不带状态：顶部「本次没带 agent-relay 状态」，没有「全线停住」；
    4. `/item 2` 带存疑状态：「agent-relay #6002：已接受但没读到（送达存疑，来源：agent-relay），唤醒 accepted」

- [x] Task 6：实测 owesReplies 回落
  - 验收：Spec 验收 8
  - 说明：先问用户
  - 记录（2026-10-18）：用户决定跳过，未实测。实测前要先用新代码重接 di-e2e 四个会话（约定块已改），并给开发B 开新任务

- [ ] Checkpoint 3（gate）：模块最终验收，等用户确认
