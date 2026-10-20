# Todo: roster-stale-wake

- [ ] Task 1：读出持有者并核对名册（Spec 要做的 1、2；验收 6）
  - 验证：`tests/test_relay.py`、`tests/test_desktop.py` 新用例在 6511882 上失败、改后通过；重新 join 回归测试通过
- [ ] Task 2：巡视唤醒实际持有者（要做的 3；验收 1～3）
  - 验证：`tests/test_patrol.py` 的 `RosterStaleTest` 在 6511882 上失败、改后通过；现有巡视测试不改、全部通过
- [ ] Task 3：停滞询问与主视图（要做的 3、4；验收 4、5）
  - 验证：`tests/test_stall.py`、`tests/test_hub.py` 新用例改前失败、改后通过；全量 `PYTHONPATH=tests:. python3 -m unittest discover -s tests` 通过
- [ ] Task 4：版本 0.0.35 与 README 升级步骤
  - 验证：`tests/test_packaging.py` 通过；README 写清哪些会话要重开、要不要重跑 join 或 hub-setup

## 检查点

- [ ] Checkpoint（gate）：模块最终验收——全部测试通过；列出实际改动的文件；临时组重放 di-p0 场景；批准后开 PR

## 外部审查意见

<!-- spec-guard: external-review declined -->
