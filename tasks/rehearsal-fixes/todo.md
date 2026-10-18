# Todo: rehearsal-fixes

- [x] Task 1：【撤回】写成自己邮箱号时点明事项号（Spec 验收 3）
  - 验证：`tests/test_items.py` 新用例：正式会话【撤回】写自己没结束事项的邮箱号被退回且说明点明「对应事项 #M」和改写；写不存在的号说明照旧；【取代】原断言不变；旧格式会话写邮箱号照旧生效
- [x] Task 2：doctor 对只登记条目报 ok（Spec 验收 1）
  - 验证：`tests/test_doctor.py` 新用例：enroll 后该项为 ok，写「只登记，不写约定块」；正式条目照旧
- [x] Task 3：leave 预览列出没了结的事项和等待单（Spec 验收 2）
  - 验证：`tests/test_onboard.py` 新用例：正式条目、只登记条目各一：有没结束事项和开着的等待单时逐条列出并写明后果与处理办法；确认后照常 leave；没有时输出与现在相同
- [x] Task 4：doctor 核对 Claude、Codex 两边的版本（Spec 验收 4）
  - 验证：`tests/test_doctor.py` 新用例：一致 ok；不一致 bad 带命令；Codex 缓存两个版本 bad；Codex 没启用或没装 ok；Claude 没装 ok；配置读不到 unknown
- [x] Task 5：`.gitignore`、README、版本 0.0.19（Spec 验收 5、6）
  - 验证：`python3 -m unittest discover -s tests` 全部通过；两份清单 0.0.19

## Checkpoint（gate）：模块最终验收

- [ ] 全部测试通过；每条验收标准都有证据；列出实际改动的文件
- [ ] 实测（Spec 验收 7）放到冻结之后，开始前另问用户
