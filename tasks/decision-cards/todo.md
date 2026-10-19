# Todo: decision-cards

- [ ] Task 1：超时与报批计数（DI-8 的 I-12、I-13；验收 12、13）
  - 验证：`tests/test_crew.py`、`tests/test_stall.py` 新用例先失败后通过
- [ ] Task 2：答复解析与操作指令（DI-7；验收 9、10）
  - 验证：`tests/test_items.py`、`tests/test_hub.py` 新用例先失败后通过；答法示例扫描通过
- [ ] Task 3：发送记账与「已转达」（DI-5、DI-6；验收 7、8）
  - 验证：新用例先失败后通过
- [ ] Task 4：7 类卡片与一次答完（DI-1、DI-2、I-10；验收 1、2、3、11）
  - 验证：`tests/test_cards.py` 等新用例先失败后通过；列出改写的旧测试
- [ ] Task 5：看 N 与看 N 全文（DI-3；验收 5）
  - 验证：新用例先失败后通过
- [ ] Task 6：收件箱停止检查（DI-4；验收 6）
  - 验证：`tests/test_stophook.py` 新用例先失败后通过；原有用例不变
- [ ] Checkpoint（gate）：DI-9 信号样本——用户让一个会话停在权限弹窗上，抓桌面版会话列表样本
- [ ] Task 7：会话停在弹窗上的兜底提醒（DI-9；验收 14）
  - 验证：样本 fixture 上的新用例先失败后通过
- [ ] Task 8：规则段、文档与真实数据验收（验收 4、15）
  - 验证：di-p0 副本实跑结果记在这里；真实状态目录 md5 不变；全量测试通过

## 检查点

- [ ] Checkpoint（gate）：模块最终验收——全部测试通过；每条验收标准有证据；列出实际改动的文件；批准后开 PR
