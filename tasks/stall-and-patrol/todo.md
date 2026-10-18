# Todo: stall-and-patrol

- [ ] Task 1：R19 叫醒兜底（Spec 验收 1）
  - 验证：`tests/test_patrol.py`、`tests/test_relay.py`：offline 3 分钟 wake、再一轮带链接通知、无 desktopSession 通知、Codex not-loaded、空闲 3 分钟、快照 24 份；原有巡视测试过
- [ ] Checkpoint A（report）：R19 测试全过
- [ ] Task 2：R18 巡视会话（Spec 验收 2）
  - 验证：`tests/test_onboard.py`、`tests/test_doctor.py`：开巡视会话步骤、删旧定时任务步骤、record-patrol、doctor 超时与未登记
- [ ] Task 3：R16 常规授权（Spec 验收 3）
  - 验证：`tests/test_onboard.py`、`tests/test_view.py`：settings 规则预览与写入（保留已有、不变不写）、Codex 信任步骤、确认卡片链接
- [ ] Task 4：R14 停滞提问（Spec 验收 4）
  - 验证：`tests/test_health.py`、`tests/test_patrol.py`、`tests/test_view.py`：三种触发、stall-ask 正文、30 分钟后主视图列选项、12 小时不重问、阈值可配
- [ ] Task 5：协作规则段与 README
  - 验证：三种角色规则段、Codex 授权说明、打包关键词
- [ ] Checkpoint B（report）：全量测试通过
- [ ] Task 6：上报 module-crew（原文先给用户看）

## Checkpoint（gate）：模块最终验收

- [ ] 全部测试通过；每条验收标准有证据；列出实际改动的文件
- [ ] 实测（Spec 验收 6）放到冻结之后，开始前另问用户
