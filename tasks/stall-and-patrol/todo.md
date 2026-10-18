# Todo: stall-and-patrol

- [x] Task 1：R19 叫醒兜底（Spec 验收 1）
  - 验证：`tests/test_patrol.py`、`tests/test_relay.py`：offline 3 分钟 wake、再一轮带链接通知、无 desktopSession 通知、Codex not-loaded、空闲 3 分钟、快照 24 份；原有巡视测试过
- [x] Checkpoint A（report）：R19 测试全过（759 个）
- [x] Task 2：R18 巡视会话（Spec 验收 2）
  - 验证：`tests/test_onboard.py`、`tests/test_doctor.py`：开巡视会话步骤、删旧定时任务步骤、record-patrol、doctor 超时与未登记
- [x] Task 3：R16 常规授权（Spec 验收 3）
  - 验证：`tests/test_onboard.py`、`tests/test_view.py`：settings 规则预览与写入（保留已有、不变不写）、Codex 信任步骤、确认卡片链接
- [x] Task 4：R14 停滞提问（Spec 验收 4）
  - 验证：`tests/test_health.py`、`tests/test_patrol.py`、`tests/test_view.py`：三种触发、stall-ask 正文、30 分钟后主视图列选项、12 小时不重问、阈值可配
- [x] Task 5：协作规则段与 README
  - 验证：三种角色规则段、Codex 授权说明、打包关键词
- [x] Checkpoint B（report）：全量测试通过（774 个）
- [x] Task 6：上报 module-crew（原文先给用户看；用户 2026-10-19 同意后已发）

## Checkpoint（gate）：模块最终验收

- [x] 全部测试通过（774 个）；每条验收标准有证据；列出实际改动的文件（用户 2026-10-19 验收通过）
- [x] 实测（Spec 验收 6）：2026-10-19 在 0.0.23 上用测试组 di-t22 实测，R19、R14、R18、R16 规则写入通过；R16 用户会话弹窗与 Codex guardian 未实测（用户决定跳过）；卸载归档被循环任务挡住，见 `field-test.md`
