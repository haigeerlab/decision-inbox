# Todo: stage-c2-fixes

- [x] Task 1：I-16 答复按项切开（Spec 要做的 1；验收 1～3）
  - 验证：`tests/test_items.py` 的 `InlineSplitTest` 和 test_hub 重放用例在 06739cc 上失败、改后通过
  - 结果：InlineSplitTest 5 项，改前 3 项失败（重放 said.txt 时 #69 原话是整个第一行、#70/#71 取的是后面的单独行；单行两项不切；夹带别的项不问），「正文数字不切」「字母不是该项选项不切」2 项改前就通过（回归保护）；转达正文的检查在 test_items 里用 items.answer 做（与 hub 发出的正文同源），没另加 test_hub 用例；全量 1161 项通过
- [x] Task 2：I-17 巡视换到自己的目录（要做的 2；验收 4、5）
  - 验证：test_onboard、test_stophook 新用例改前失败、改后通过；teardown 步骤不变
  - 结果：PatrolDirTest 3 项、PatrolDirAllowTest 2 项、PatrolDirHookTest 2 项；改前 6 项失败（没有 patrol_dir、步骤仍写「在决策收件箱目录开巡视会话」、旧巡视会话不先退场、放行规则只写一份），teardown 步骤不变一项改前就通过；停止钩子重放：收件箱目录出 block（复现实测），巡视目录不出；commands/hub-setup.md 写明巡视目录；全量通过
- [x] Task 3：I-18 旧事项写明来历（要做的 3；验收 6）
  - 验证：`AnsweredNotResumedTest` 新用例改前失败、改后通过；本会话自己的事项和没有记录时提示不变
  - 结果：InheritedItemTest（继承 AnsweredNotResumedTest，原有 8 项照跑）新增 4 项，改前 2 项失败（没有 session_start、旧事项照旧写「用户已答复」），本会话自己的事项、读不到记录 2 项改前就通过；开始时间由 decide 从 payload 自己读，不经 _hook 传（入口不用改，和 Plan 写法略有出入，效果相同）；【撤回】写法引用契约字段「事项：#N」以过术语检查；全量 1180 项通过
- [x] Task 4：I-19 收窄【答复告知】（要做的 4；验收 7）
  - 验证：`AnswerNoticeTest` 新用例改前失败、改后通过；全量测试通过
  - 结果：新类 NarrowNoticeTest 5 项（认不出不发、审查编号认提交方、能力图里唯一一条有该模块、两条都有就不发、模块协调的模块也算），改前全部失败（同线开发线和测试身份都收到）；按 Spec 改了 3 条旧测试的前提（AnswerNoticeTest 的 test_owner_item_copies_its_dev_lines、test_notice_sent_does_not_move_the_item，QuestionReturnTest 的 test_notice_reply_names_the_notice）：加 trace_to_fe 让事项带审查编号 R-1 追到前端，断言本身未改；命令行 inbox reply 已传 maps、crews；全量 1185 项通过
- [ ] Task 5：版本 0.0.36 与 README
  - 验证：`tests/test_packaging.py` 通过；README 写清升级步骤

## 检查点

- [ ] Checkpoint（gate）：模块最终验收——全部测试通过；列出实际改动的文件；重放 I-16／I-17／I-18；批准后开 PR

## 外部审查意见

<!-- spec-guard: external-review declined -->
