# Todo: loop-detection

- [ ] Task 1：读新事实（gates、answers、waitUser 明细）
  - 验证：`tests/test_specguard.py`、`tests/test_crew.py` 新用例先失败后通过；原有用例不变
- [ ] Task 2：打标与每个模块的事实（Spec 第 1、2 节）
  - 验证：`tests/test_loops.py` 先失败后通过
- [ ] Task 3：打转判断与答复写法（Spec 第 3、4 节；验收 1、2、3、7）
  - 验证：新用例先失败后通过；原有答复用例不变
- [ ] Task 4：展示（Spec 第 4、5、6、8 节；验收 4、5、6、8、10）
  - 验证：新用例先失败后通过；di-p0 状态目录临时副本上出一次主视图，结果记在这里
- [ ] Task 5：停滞判断与文档（Spec 第 7 节；验收 8、9）
  - 验证：新用例先失败后通过；旧称扫描、全量测试通过

## Checkpoint（gate）：模块最终验收

- [ ] 全部测试通过；每条验收标准有证据；列出实际改动的文件
