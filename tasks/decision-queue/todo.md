# Todo: decision-queue

测试命令：`python3 -m unittest discover -s tests -v`

- [x] Task 1：收单与退回
  - 验收：Spec 验收 1（入表、共用编号、存原文要点与审查标签、事件）、2（退回不占编号、逐条说明、事件）、3（`scope-session-unknown`、开发线多线按普通事项并提示 `multiline-not-allowed`）；非【等待用户】【撤回】的消息 `handled` 为假
  - 验证：`python3 -m unittest discover -s tests -p test_items.py -v`
  - 文件：`decision_inbox/items.py`、`tests/test_items.py`

- [x] Task 2：取代、撤回与排序
  - 验收：Spec 验收 4（取代、撤回、`not-owner`）、5（排序）
  - 验证：`python3 -m unittest discover -s tests -p test_items.py -v`
  - 文件：`decision_inbox/items.py`、`tests/test_items.py`

- [x] Checkpoint 1（report）：全部测试全绿，记下命令与结果后继续
  - 记录：`python3 -m unittest discover -s tests -v` → Ran 112 tests, OK（2026-10-16）

- [x] Task 3：解析用户回复
  - 验收：Spec 验收 6（三种写法）、7（一次答多项的两种切分）、8（六种情况只问不转）；原话里含「，」但不是多项时不误切
  - 验证：`python3 -m unittest discover -s tests -p test_items.py -v`
  - 文件：`decision_inbox/items.py`、`tests/test_items.py`

- [x] Task 4：生成答复与多线分发
  - 验收：Spec 验收 9（多线三份外发、各自范围）、10（审查中照样转发）；「12 B」附选项原文
  - 验证：`python3 -m unittest discover -s tests -p test_items.py -v`
  - 文件：`decision_inbox/items.py`、`tests/test_items.py`

- [x] Checkpoint 2（report）：全部测试全绿，记下命令与结果后继续
  - 记录：`python3 -m unittest discover -s tests -v` → Ran 124 tests, OK（2026-10-16）

- [x] Task 5：状态推进与追溯
  - 验收：Spec 验收 11（状态推进、多收件人取最慢、别人的【已恢复】不影响）、12（history）、13（快照与事件一致）
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/items.py`、`tests/test_items.py`

- [ ] Checkpoint 3（gate）：模块最终验收——全部测试全绿、13 条验收标准逐条对应测试、列出实际改动文件；停下等用户确认
