# Todo: line-health

测试命令：`python3 -m unittest discover -s tests -v`

- [x] Task 1：输入整理、进度快照与常量
  - 验收：Spec 验收 11（沿用／更新变化时间、首次为 None、可 JSON 序列化）、12（常量数值与 Spec 表一致；`assess` 前后 group-store 文件逐字节不变）
  - 验证：`python3 -m unittest discover -s tests -p test_health.py -v`
  - 文件：`decision_inbox/health.py`、`tests/test_health.py`

- [x] Task 2：7 个状态词
  - 验收：Spec 验收 1（判定顺序）、2（阻塞两种写法）、3（干活中与 running 不算）、4（停住 N 小时）、5（已结项、无能力图退回无活动）
  - 验证：`python3 -m unittest discover -s tests -p test_health.py -v`
  - 文件：`decision_inbox/health.py`、`tests/test_health.py`

- [x] Checkpoint 1（report）：全部测试全绿，记下命令与结果后继续
  - 记录：`python3 -m unittest discover -s tests -v` → Ran 170 tests, OK（2026-10-16）

- [x] Task 3：会话与积压类信号 1、2、4、5、10
  - 验收：Spec 验收 6、7（各信号的正例与边界反例）
  - 验证：`python3 -m unittest discover -s tests -p test_health.py -v`
  - 文件：`decision_inbox/health.py`、`tests/test_health.py`

- [x] Task 4：进度与审查类信号 3、6、7、8、9
  - 验收：Spec 验收 8（挂起挡住、返工两种门槛）、9（变慢：历史门槛、兜底、快照优先、shallow、首次）、10（孤儿等待）；信号 3 与「停住」一致
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/health.py`、`tests/test_health.py`

- [x] Checkpoint 2（gate）：模块最终验收——全部测试全绿、12 条验收标准逐条对应测试、列出实际改动文件；停下等用户确认
  - 记录：184 个测试全绿（连跑 2 次），本模块 24 个；用户 2026-10-16 验收通过，并批准规格修订（分钟写法、无数据写法、LineState.since）
