# Todo: stage-c3-fixes

- [ ] Task 1：I-20 不带编号的回复认不出选项就追问（Spec 假设 1；验收 1）
  - 验证：`test_unnumbered_chat_is_not_an_answer` 与 test_items 新用例改前失败、改后通过
- [ ] Task 2：I-20 没发出的答复可重答替换、「撤下 N」（假设 2、3；验收 2、3）
  - 验证：`UnsentAnswerTest` 其余三条与新用例改前失败、改后通过
- [ ] Task 3：I-21 停滞起点加模块最近一次抛出事项的时间（假设 4；验收 4）
  - 验证：`RaisedItemStallTest` 与普通开发线用例改前失败、改后通过
- [ ] Task 4：I-22 回复提到待答事项却没贴卡片时拦一次（假设 5；验收 5）
  - 验证：`HubTurnWithoutViewTest` 与命令行用例改前失败、改后通过
- [ ] Task 5：onboard watch --remove、重跑 join 改线名提示、README 排查行（假设 6、7；验收 6、7）
  - 验证：test_onboard 新用例改前失败、改后通过；全量测试通过

## 检查点

- [ ] Checkpoint（gate）：模块最终验收——全部测试通过；列出实际改动的文件；重放 I-20／I-21／I-22

## 外部审查意见

<!-- spec-guard: external-review declined -->
