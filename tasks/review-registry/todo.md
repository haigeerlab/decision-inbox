# Todo: review-registry

测试命令：`python3 -m unittest discover -s tests -v`

- [x] Task 1：审查者登记
  - 验收：Spec 验收 1（生效前后、事件带批准依据）、2（审查者不是负责人、送审方是收件枢纽、第五类节点、批准依据为空都被拒且状态不变）；修改登记保留旧记录并写 `until`；撤销后 `registration_at` 返回 None
  - 验证：`python3 -m unittest discover -s tests -p test_reviews.py -v`
  - 文件：`decision_inbox/reviews.py`、`tests/test_reviews.py`

- [x] Task 2：显示标签
  - 验收：Spec 验收 3（五种写法逐字、highlight）、4（⚠ 未标审查与 mentions）、5（没登记一律「本会话无审查者」）、6（生效前后、撤销前后）
  - 验证：`python3 -m unittest discover -s tests -p test_reviews.py -v`
  - 文件：`decision_inbox/reviews.py`、`tests/test_reviews.py`

- [x] Checkpoint 1（report）：全部测试全绿，记下命令与结果后继续
  - 记录：`python3 -m unittest discover -s tests -v` → Ran 93 tests, OK（2026-10-16）

- [x] Task 3：审查结论与轮数
  - 验收：Spec 验收 7（三轮后通过）、8（三种问题代码，不计轮数）、9（结束后重开并提示）、10（快照与事件一致，`store show` 正常）
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/reviews.py`、`tests/test_reviews.py`

- [ ] Checkpoint 2（gate）：模块最终验收——全部测试全绿、10 条验收标准逐条对应测试、列出实际改动文件；停下等用户确认
