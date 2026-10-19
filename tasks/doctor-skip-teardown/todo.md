# Todo: doctor-skip-teardown

- [x] Task 1：doctor 跳过已卸载的组（Spec 验收 1–5）
  - 验证：`tests/test_doctor.py` 新断言先失败后通过；原有巡视测试不变；本机 di-e2e、pp-probe 实跑为 ✔ 已卸载；全量测试通过

## Checkpoint（gate）：模块最终验收

- [x] 全部测试通过（836 个）；每条验收标准有证据；列出实际改动的文件（用户 2026-10-19 验收通过）
