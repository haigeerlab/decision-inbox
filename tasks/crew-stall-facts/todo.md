# Todo: crew-stall-facts

- [x] Task 1：读新字段（Spec 验收 6、7 的解析部分）
  - 验证：`tests/test_crew.py` 新断言先失败后通过；原有断言不改
- [x] Task 2：按模块判断与叫醒（Spec 验收 1–4、6）
  - 验证：`tests/test_stall.py`、`tests/test_patrol.py` 新断言先失败后通过；线级 R14 原有测试不变
- [ ] Task 3：主视图、文档与实跑（Spec 验收 5、7、8）
  - 验证：主视图新断言先失败后通过；crew-rehearsal 实跑读出新字段且不叫醒；全量测试通过

## Checkpoint（gate）：模块最终验收

- [ ] 全部测试通过；每条验收标准有证据；列出实际改动的文件
