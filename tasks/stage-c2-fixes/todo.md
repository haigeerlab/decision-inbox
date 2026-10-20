# Todo: stage-c2-fixes

- [ ] Task 1：I-16 答复按项切开（Spec 要做的 1；验收 1～3）
  - 验证：`tests/test_items.py` 的 `InlineSplitTest` 和 test_hub 重放用例在 06739cc 上失败、改后通过
- [ ] Task 2：I-17 巡视换到自己的目录（要做的 2；验收 4、5）
  - 验证：test_onboard、test_stophook 新用例改前失败、改后通过；teardown 步骤不变
- [ ] Task 3：I-18 旧事项写明来历（要做的 3；验收 6）
  - 验证：`AnsweredNotResumedTest` 新用例改前失败、改后通过；本会话自己的事项和没有记录时提示不变
- [ ] Task 4：I-19 收窄【答复告知】（要做的 4；验收 7）
  - 验证：`AnswerNoticeTest` 新用例改前失败、改后通过；全量测试通过
- [ ] Task 5：版本 0.0.36 与 README
  - 验证：`tests/test_packaging.py` 通过；README 写清升级步骤

## 检查点

- [ ] Checkpoint（gate）：模块最终验收——全部测试通过；列出实际改动的文件；重放 I-16／I-17／I-18；批准后开 PR

## 外部审查意见

<!-- spec-guard: external-review declined -->
