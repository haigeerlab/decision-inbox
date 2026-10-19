# Todo: host-permission-check

- [x] Task 1：读宿主事实与 Plan 需要（Spec 验收 1–6 的判断部分）
  - 验证：`tests/test_hostperm.py` 先失败后通过；配置文件读前读后逐字相同
- [x] Task 2：doctor 的「宿主权限」一项（Spec 验收 1–6 的展示部分）
  - 验证：doctor 新用例先失败后通过；原有测试不变
- [ ] Task 3：接入预览与文档（Spec 验收 7、8）
  - 验证：接入预览新用例先失败后通过；本机 di-p0 只读实跑 doctor；旧称扫描、全量测试通过

## Checkpoint（gate）：模块最终验收

- [ ] 全部测试通过；每条验收标准有证据；列出实际改动的文件
