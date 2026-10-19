# Todo: decision-cards

- [x] Task 1：超时与报批计数（DI-8 的 I-12、I-13；验收 12、13）
  - 验证：`tests/test_crew.py`、`tests/test_stall.py` 新用例先失败后通过
- [x] Task 2：答复解析与操作指令（DI-7；验收 9、10）
  - 验证：`tests/test_items.py`、`tests/test_hub.py` 新用例先失败后通过；答法示例扫描通过
  - 改写的旧测试（按 Spec 第 7 节，带编号却没有选项字母的话不再静默转出）：`test_items` 的 `test_copy_block_and_free_sentence`、`test_free_sentence_forwarded_verbatim` 改用「N 原话：…」；`test_loops` 的 `test_words_are_plain_text_without_a_hint` 改为先断言被问回、再用「N 原话：继续等」
- [x] Task 3：发送记账与「已转达」（DI-5、DI-6；验收 7、8）
  - 验证：新用例先失败后通过
  - 改写的旧测试：措辞——`test_hub` 的 `test_letter_answer`、`test_owner_item_copies_its_dev_lines`、`test_receive_reply_sent_view`（「已转达」→「已收下你的答复」，sent 输出多了 show）、`test_view_without_relay_and_unsent`、`test_main_view_warns_unsent_and_unreadable_relay`（「有 N 条没发出去」→逐条列出）、`test_superseded_and_withdrawn_closed_once`（已撤回的不进 alsoAnswers）；造数据——`test_view` 的 `forward`、`test_patrol` 的 `answered_item`、`test_stophook` 的 `answered` 与 crew 用例补发送记录（不改被测行为）
  - 顺带：巡视「答复卡在离线负责人」只看已发出的答复（patrol._handoffs），否则没发出去的答复也会叫醒负责人
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
