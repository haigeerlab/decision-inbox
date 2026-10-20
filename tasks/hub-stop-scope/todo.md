# Todo: hub-stop-scope

- [x] Task 1：停止钩子只对收件箱做卡片检查（Spec 要做的 1；验收 1～4）
  - 验证：`tests/test_stophook.py` 新用例在 e88e7d9 上失败、改后通过
  - 结果：HubScopeHookTest 4 项加改写的 test_hook_entry_passes_outside_any_group，改前 6 处失败（非收件箱目录、组外、没有 cwd、--session 开发线都被拦），收件箱照旧拦的一项改前就通过；改后全部通过，全量 1128 项通过
- [ ] Task 2：doctor 只试读收件箱自己的会话记录（要做的 2；验收 5）
  - 验证：`tests/test_doctor.py` 新用例在 e88e7d9 上失败、改后通过；全量 `PYTHONPATH=tests:. python3 -m unittest discover -s tests` 通过

## 检查点

- [ ] Checkpoint（gate）：模块最终验收——全部测试通过；列出实际改动的文件；临时组复现实测场景；批准后开 PR
