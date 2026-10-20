# Todo: roster-stale-wake

- [x] Task 1：读出持有者并核对名册（Spec 要做的 1、2；验收 6）
  - 验证：`tests/test_relay.py`、`tests/test_desktop.py` 新用例在 6511882 上失败、改后通过；重新 join 回归测试通过
  - 结果：RosterHolderTest 9 项、HolderSessionIdTest 3 项改前全部失败（没有 holders／session_id／claude_id）；重新 join 回归测试改前也报错，原因是调到了还不存在的 desktop.holders，名册更新这一半本来就成立；改后全部通过
- [x] Task 2：巡视唤醒实际持有者（要做的 3；验收 1～3）
  - 验证：`tests/test_patrol.py` 的 `RosterStaleTest` 在 6511882 上失败、改后通过；现有巡视测试不改、全部通过
  - 结果：RosterStaleTest 6 项，改前 4 项失败（唤醒发给旧会话、没有名册过期通知、只有旧会话在运行时仍唤醒旧会话、收件箱唤醒旧会话），名册一致和两边都不在运行这 2 项改前就通过（行为不变）；改后全部通过，现有巡视测试未改，全量 1150 项通过
- [x] Task 3：停滞询问与主视图（要做的 3、4；验收 4、5）
  - 验证：`tests/test_stall.py`、`tests/test_hub.py` 新用例改前失败、改后通过；全量 `PYTHONPATH=tests:. python3 -m unittest discover -s tests` 通过
  - 结果：RosterStaleStallTest 4 项、RosterStaleViewTest 的名册过期行 1 项改前失败（asks／overdue_rows 不收 holders，巡视没传，主视图没有过期行）；名册一致时不显示的 1 项改前就通过；改后全部通过，全量 1156 项通过
- [x] Task 4：版本 0.0.35 与 README 升级步骤
  - 验证：`tests/test_packaging.py` 通过；README 写清哪些会话要重开、要不要重跑 join 或 hub-setup
  - 结果：两个 plugin.json 改为 0.0.35；README 写了 0.0.35 段（含 #53、#54 与本修复，4 步升级：开新会话刷新 shim、误拦过的会话新开、只有接管过邮箱名的会话重跑 join／hub-setup、上级目录的规则段按 doctor 重跑）；排查表加「名册过期」一行；按 hooks.json（停止钩子用 CLAUDE_PLUGIN_ROOT）和 install.write_shim（SessionStart 刷新 shim）写会话重开说明；全量 1156 项通过

## 检查点

- [x] Checkpoint（gate）：模块最终验收——全部测试通过；列出实际改动的文件；临时组重放 di-p0 场景；批准后开 PR（用户 2026-10-20 批准；1156 项测试通过；重放中唤醒发给 local_cb182a33，计划里旧编号 0 次）

## 外部审查意见

<!-- spec-guard: external-review declined -->
