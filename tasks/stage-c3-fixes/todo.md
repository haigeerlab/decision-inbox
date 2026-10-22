# Todo: stage-c3-fixes

- [x] Task 1：I-20 不带编号的回复认不出选项就追问（Spec 假设 1；验收 1）
  - 验证：`test_unnumbered_chat_is_not_an_answer` 与 test_items 新用例改前失败、改后通过
  - 结果：test_unnumbered_chat_is_not_an_answer 与改写后的 test_no_number_with_single_pending 改前失败、改后通过；「没有选项的事项照收整句」改前就通过（行为不变）；按 Spec 改了两条旧断言：test_no_number_with_single_pending（「按推荐来」原断言被收下，改为追问）、PrefixTest.test_old_forms_unchanged（不带编号的「A」原断言 letter=None，现在读出 A）；全量除调查分支其余 6 条外通过
- [x] Task 2：I-20 没发出的答复可重答替换、「撤下 N」（假设 2、3；验收 2、3）
  - 验证：`UnsentAnswerTest` 其余三条与新用例改前失败、改后通过
  - 结果：UnsentAnswerTest 三条改前失败、改后通过；新增 UnsentAnswerMoreTest 两条（还没发就重答、规则段和指令提示有「撤下 N」）；调查分支「重答替换」一条的断言改为「只剩新答复待发、旧的失败原因不再显示」（新答复本身待发，主视图出现「重发 1」是正当的）；按 Spec 改了三条旧断言：ReplyTest.test_main_view_warns_unsent_and_unreadable_relay（主视图那一行新文字）、AnswerTest 两条（先模拟已发出，保持「发出后不能改」的原意）；规则段第 5 步加「撤下 N」，收件箱须重跑 hub-setup
- [x] Task 3：I-21 停滞起点加模块最近一次抛出事项的时间（假设 4；验收 4）
  - 验证：`RaisedItemStallTest` 与普通开发线用例改前失败、改后通过
  - 结果：RaisedItemStallTest（模块）与 RaisedItemPlainLineTest（普通开发线）各 1 条改前失败、改后通过；「别的模块的事项不算」「撤回的事项不算」两条对照改前就通过；现有停滞用例未改；全量只剩 I-22 两条
- [x] Task 4：I-22 回复提到待答事项却没贴卡片时拦一次（假设 5；验收 5）
  - 验证：`HubTurnWithoutViewTest` 与命令行用例改前失败、改后通过
  - 结果：HubTurnWithoutViewTest 两条（改前因没有 pending 参数报错）与新的 HubTurnWithoutViewHookTest 命令行用例（改前不拦）改后通过；命令行用例同时覆盖闲聊放行、提到的编号不在待答放行；全量 1232 项通过
- [x] Task 5：onboard watch --remove、重跑 join 改线名提示、README 排查行（假设 6、7；验收 6、7）
  - 验证：test_onboard 新用例改前失败、改后通过；全量测试通过
  - 结果：WatchRemoveCommandTest 两条（放在 test_watch，和现有 onboard watch 命令测试同处）与 test_rejoin_with_a_new_short_name_says_so 改前失败、改后通过；README 排查表加「误收的答复／撤下 N」「只卸巡视提醒」两行；全量 1242 项通过

## 检查点

- [ ] Checkpoint（gate）：模块最终验收——全部测试通过；列出实际改动的文件；重放 I-20／I-21／I-22

## 外部审查意见

<!-- spec-guard: external-review declined -->
