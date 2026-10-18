# Todo: patrol-stop-fixes

- [x] Task 1：停止巡视约定与卸载先停再归档（Spec 验收 1–3）
  - 验证：`tests/test_onboard.py`、`tests/test_hub.py`、`tests/test_packaging.py` 新断言先失败后通过；只有旧定时任务时输出不变
- [ ] Task 2：「身份」改名与 README（Spec 验收 4、5）
  - 验证：旧称扫描加「身份」后全过；全量测试通过

## Checkpoint（gate）：模块最终验收

- [ ] 全部测试通过；每条验收标准有证据；列出实际改动的文件
