# Todo: protocol-contract-v2-6

- [ ] Task 1：拷入 v2.6 样例，读「任务」与 bad-task-ref、module-task-both（Spec 假设 1、2；验收 1、2）
  - 验证：四份 task 样例在契约测试里改前失败、改后通过；test_protocol 新用例通过
- [ ] Task 2：C 待定编号与 T 编号（假设 3、4；验收 3、4、5）
  - 验证：decision-cnum 两份样例转绿；test_items 新用例改前失败、改后通过
- [ ] Task 3：Spec／Plan 新小项名（假设 5；验收 6）
  - 验证：card-spec-upstream、card-plan-upstream 转绿；test_cards 新用例通过、旧用例不改
- [ ] Task 4：卡片抬头显示任务（假设 2；验收 7）
  - 验证：test_cards 新用例改前失败、改后通过；契约测试全部通过
- [ ] Task 5：规则段、README、术语表、版本 0.0.37（假设 7、8；验收 8）
  - 验证：test_hub、test_glossary、test_packaging 通过；全量测试通过

## 检查点

- [ ] Checkpoint（gate）：模块最终验收——全部测试通过；列出实际改动的文件；重放「T78 先缓一缓」与「41 A；C15-1 B」；批准后开 PR

## 外部审查意见

<!-- spec-guard: external-review declined -->
