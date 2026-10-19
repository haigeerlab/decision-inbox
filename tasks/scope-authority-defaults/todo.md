# Todo: scope-authority-defaults

- [x] Task 1：授权默认打开（Spec 验收 1、2）
  - 验证：`tests/test_onboard.py` 新断言先失败后通过；CLI 两个开关各跑一次
- [x] Task 2：Claude 权限与旧规则清理（Spec 验收 3、4）
  - 验证：新接入的权限规则、旧规则预览与确认删除的测试先失败后通过；用户自己的规则保留
- [x] Task 3：规则段措辞与文档（Spec 验收 5、6、7）
  - 验证：规则段与文档断言先失败后通过；旧称扫描、全量测试通过

## Checkpoint（gate）：模块最终验收

- [ ] 全部测试通过；每条验收标准有证据；列出实际改动的文件
