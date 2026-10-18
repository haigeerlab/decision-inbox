# Todo: r20-fixes

- [x] Task 1：停止钩子排除已退出条目（Spec 验收 3）
  - 验证：`tests/test_stophook.py`：共用仓库时认出留下的条目并能拦；--session 指向已退出条目放行并写原因；原有测试过
- [ ] Task 2：卡片字母自检与收件枢纽「逐字粘贴」（Spec 验收 1）
  - 验证：`tests/test_view.py`、`tests/test_hub.py`：主视图、看 N、N 详情三种输出字母自检；规则段文字
- [ ] Task 3：三种角色规则段「适用线不发【已恢复】」、README（Spec 验收 2、4）
  - 验证：`tests/test_onboard.py`；全量测试通过

## Checkpoint（gate）：模块最终验收

- [ ] 全部测试通过；每条验收标准有证据；列出实际改动的文件
