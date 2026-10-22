# Todo: protocol-contract-v2-6

- [x] Task 1：拷入 v2.6 样例，读「任务」与 bad-task-ref、module-task-both（Spec 假设 1、2；验收 1、2）
  - 验证：四份 task 样例在契约测试里改前失败、改后通过；test_protocol 新用例通过
  - 结果：92309e7 的 fixtures 原样拷入 v2.6（SHA256SUMS 全部核对一致），删 v2.4，CONTRACT_VERSION 2.6，SOURCE 记 92309e7，样例计数 parse 104→115、跳过 40→43；四份 task 样例改前失败、改后通过；TaskFieldTest 3 条（「模块：无」配「任务」合格、问题代码在原有代码之后、事项记录存 task），存 task 那条改前失败；剩 cnum 与 upstream 共 7 处样例留给 Task 2、3
- [x] Task 2：C 待定编号与 T 编号（假设 3、4；验收 3、4、5）
  - 验证：decision-cnum 两份样例转绿；test_items 新用例改前失败、改后通过
  - 结果：decision-cnum、decision-cnum-bad 及 card-spec-upstream 的 decisions 转绿；CNumberReplyTest 4 条，3 条改前失败（改前「2 A；C15-1 B」被当成同时答了 #2 和 #1，正是契约点名的误读），「T78 先缓一缓」一条因 stage-c3-fixes 已通过、留作回归保护；行内切分与夹带检查合用 _bare_number_at；全量只剩两份 upstream 的 points
- [x] Task 3：Spec／Plan 新小项名（假设 5；验收 6）
  - 验证：card-spec-upstream、card-plan-upstream 转绿；test_cards 新用例通过、旧用例不改
  - 结果：两份 upstream 样例转绿；V26CardTest 3 条（Spec 新名、Plan 新名、新旧名同时出现两行都在）改前失败、改后通过；加新名后卡片行数上限按名字个数算变大（spec-plan 22→26），改为按模板小项数与卡片实际小项数取大（cards.max_lines），旧用例不改全部通过；契约样例全部通过；全量 1257 项通过
- [x] Task 4：卡片抬头显示任务（假设 2；验收 7）
  - 验证：test_cards 新用例改前失败、改后通过；契约测试全部通过
  - 结果：TaskCardTest 改前抬头是「模块 未知」、改后是「任务 T3」；契约测试全部通过（SHA256SUMS 一致）；全量通过
- [x] Task 5：规则段、README、术语表、版本 0.0.37（假设 7、8；验收 8）
  - 验证：test_hub、test_glossary、test_packaging 通过；全量测试通过
  - 结果：规则段第 5 步写明 T 编号、C 待定编号不是待决事项编号（ContractV26RulesTest 改前失败）；README 契约段改 v2.6 并加 v2.5／v2.6 说明，加 0.0.37 说明与升级步骤（收件箱重跑 hub-setup，其他会话不用重跑接入）；两个 plugin.json 0.0.37，test_packaging 跟着改；**术语表没改**：docs/glossary.md 是 livesaas-integration/GLOSSARY.md 的副本（「原件以来源为准」，测试要求逐字一致），「轻任务」「C 待定编号」要由术语表负责人加到原件，交付时提出；按术语检查把「事项号」「待答事项」改成「待决事项编号」「待答的待决事项」；全量 1264 项通过

## 检查点

- [x] Checkpoint（gate）：模块最终验收——全部测试通过；列出实际改动的文件；重放「T78 先缓一缓」与「41 A；C15-1 B」；批准后开 PR（用户 2026-10-22 批准；1264 项测试通过；两段重放符合预期）

## 外部审查意见

<!-- spec-guard: external-review declined -->
