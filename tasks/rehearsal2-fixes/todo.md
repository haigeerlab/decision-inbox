# Todo: rehearsal2-fixes

- [ ] Task 1：已退出条目不进线状态（Spec 验收 1）
  - 验证：`tests/test_health.py` 新用例：left 条目不在 lines、信号里；现有旧格式、leave 测试通过
- [ ] Task 2：stopped 能叫醒时不写「掉线」，模块写「停着」（Spec 验收 2）
  - 验证：`tests/test_health.py` 新用例：Claude stopped+desktopSession、stopped+wake 绑定、stopped 叫不醒、unreachable、Codex stopped 五种；模块 stopped 写「停着」；`tests/test_patrol.py` 现有测试通过
- [ ] Task 3：巡视中间文件、notify 命令和 allow 放行（Spec 验收 3）
  - 验证：`tests/test_patrol.py` 提示词断言 io 目录与 notify 命令；`tests/test_cli.py`（或对应文件）notify 子命令用假 osascript 验证传参；`tests/test_onboard.py` allow 预览含 Edit 规则
- [ ] Task 4：【等待用户】写法提示与收件提示（Spec 验收 4）
  - 验证：`tests/test_protocol.py` 用 bodies/8.txt 样例出四条提示、完整样例无提示；`tests/test_hub.py` 收下并给发件人发收件提示；退回测试不变
- [ ] Task 5：join 提醒新开会话、内容相同不重写（Spec 验收 5）
  - 验证：`tests/test_onboard.py` 步骤含提醒；重跑 join 时规则文件 mtime 不变
- [ ] Task 6：README、版本 0.0.20（Spec 验收 6）
  - 验证：`python3 -m unittest discover -s tests` 全部通过；两份清单都是 0.0.20

## Checkpoint（gate）：模块最终验收

- [ ] 全部测试通过；每条验收标准都有证据；列出实际改动的文件
- [ ] 实测（Spec 验收 7）放到冻结之后，开始前另问用户
