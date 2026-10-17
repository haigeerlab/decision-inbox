# Todo: answer-handoff-gaps

测试命令：`python3 -m unittest discover -s tests -v`

- [ ] Task 1：停止钩子拦「已答未恢复」
  - 验收：Spec 验收 1（第一次收工被拦，说明含编号和原话，原话超过 40 字截断；第二次放行）、验收 2（恢复后不拦；自己开着等待单时放行）、验收 3（和「有人在等你」合成一条，前者在前）；H17 场景写成回归测试
  - 验证：`python3 -m unittest discover -s tests -p test_stophook.py -v`
  - 文件：`decision_inbox/stophook.py`、`tests/test_stophook.py`

- [ ] Task 2：巡视处理离线负责人压着的答复
  - 验收：Spec 验收 4（当轮出 `wake:<负责人>` 和 `notify:handoff:…`，文字含编号、短名、挡住的线数）、验收 5（排最前；超过 3 条时最后才合并）、验收 6（取走或上线后清记录；不重复通知；离线的是开发线时行为不变；叫醒不重复）
  - 验证：`python3 -m unittest discover -s tests -p test_patrol.py -v`
  - 文件：`decision_inbox/patrol.py`、`tests/test_patrol.py`

- [ ] Task 3：收件枢纽抄送【答复告知】
  - 验收：Spec 验收 7（负责人抛的单线事项给其线上每个开发线一条；正文含「不是批准」「不作执行依据」；多线事项、开发线抛的事项不抄送）、验收 8（sent 记编号但不改事项状态、不关单）
  - 验证：`python3 -m unittest discover -s tests -p test_hub.py -v`
  - 文件：`decision_inbox/hub.py`、`decision_inbox/protocol.py`、`tests/test_hub.py`

- [ ] Checkpoint 1（report）：全部测试全绿，记下命令与结果后继续

- [ ] Task 4：约定块加三条、README 一句、版本 0.0.3
  - 验收：Spec 验收 9（三条分别出现在共用、开发线、负责人部分；原有要点和模板解析不变）、验收 10（两份清单 0.0.3，原有测试全过）
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/onboard.py`、`README.md`、两份 `plugin.json`、`tests/test_onboard.py`、`tests/test_packaging.py`

- [ ] Checkpoint 2（report）：全部测试全绿；scratchpad 临时协作组上命令行实跑三种新行为，记下输出后继续

- [ ] Task 5：实测【答复告知】送达
  - 验收：Spec 验收 11。先问用户：本会话扮演收件枢纽，登记负责人和开发线两个测试身份，负责人抛一项单线事项，答复后开发线测试身份收到【答复告知】；结果写进规格实测记录
  - 验证：命令输出、测试身份收件箱
  - 文件：`spec/answer-handoff-gaps.md`

- [ ] Checkpoint 3（gate）：模块最终验收——全部测试全绿、11 条验收标准逐条有测试或实测记录、列出实际改动文件、原样附上规格差异、列出拟回告；停下等用户确认
