# Todo: patrol-launchd

- [x] Task 1 脚本调用：`relayscript.script_argv`／`run_script`（relay.py 有「不导入 subprocess」的测试约束，改放新文件），读 `interface.json` 的 `script`，低于 0.9.0 报升级
- [x] Task 2 `patrol tick`：锁 → 读状态 → plan → 发信／通知 → record → watch.check；读不到 agent-relay 与脚本身份没登记的通知
- [x] Task 3 `onboard patrol-identity`、`patrol_alarm` 认 launchd、收件箱收到脚本身份的信只确认
- [ ] Task 4 hub-setup 步骤、`onboard watch` 跑 `patrol tick`、doctor「巡视定时任务」与脚本身份检查、teardown 一行
- [ ] Task 5 README、`commands/hub-setup.md`、术语表 v1.3 同步与「脚本身份」、版本 0.0.38、全量测试、真实 agent-relay 只读核对
- [ ] Checkpoint（gate）：模块最终验收 —— 批准后告诉负责人、推送、开 PR
