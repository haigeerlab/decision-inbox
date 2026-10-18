# Todo: review-nearby

- [x] Task 1：重新 join 的写入回执（Spec 验收 7）
  - 验证：`tests/test_onboard.py`：确认输出有「已写入：名册…」，有审查者时有「审查者…已重新登记」，预览没有，内容不变仍写「（没有变化）」
- [x] Task 2：doctor 两边都没装时报异常（Spec 验收 8）
  - 验证：`tests/test_doctor.py`：两边都没装报 problem；现有一边、同版本、不同版本用例不变
- [x] Task 3：返工轮次显示（Spec 验收 5）
  - 验证：`tests/test_crew.py`、`tests/test_health.py`：rework、reviewing（round 0／>0）、null、缺字段、形状不对；`tests/test_hub.py`：有须修改项的【审查结论】不产生事项
- [x] Task 4：合批摘要卡片（Spec 验收 6）——2026-10-19 用户确认回退显示（R8 由 R12 取代，移到 approval-display），只保留存 `brief`
  - 验证：`tests/test_view.py`：module-crew 新格式样例显示摘要段与「回『N 详情』」；bodies/8.txt 取前 5 行；单项卡片快照不变；详情照旧
- [x] Checkpoint A（report）：Phase 1 测试全过（708 个）；契约未发布时停在这里等
- [x] Task 5：改钉契约 v2.0.1（Spec 验收 1）
  - 验证：`tests/test_contract.py`：指纹核对、解析样例全过、回执生成后再解析一致、跳过数写明；原有测试全过
- [x] Task 6：编号前缀（Spec 验收 3）
  - 验证：`tests/test_items.py`：「21 B，C15 退回」；C15、#C15、R-3、D1、4c5d6e7 不当事项号；四种老写法不变
- [x] Task 7：待用户决定（Spec 验收 2）
  - 验证：`tests/test_items.py`、`tests/test_view.py`：缺 Dn、只答一半、错字母、重复、没答主选项都追问；答全转发原话；卡片列 Dn；一次答完跳过
- [x] Task 8：登记回执（Spec 验收 4）
  - 验证：`tests/test_hub.py`：receipt 无 replyTo、wake false、能解析为合格回执；取代、写法提示；旧格式、退回、撤回不发
- [x] Checkpoint B（report）：Phase 3 测试全过（733 个）
- [x] Task 9：解耦、约定块、README、版本 0.0.21（Spec 验收 9、10）
  - 验证：解耦对比测试只多 receipt；`python3 -m unittest discover -s tests` 全过；两份清单 0.0.21

## Checkpoint（gate）：模块最终验收

- [ ] 全部测试通过；每条验收标准有证据；列出实际改动的文件
- [ ] 实测（Spec 验收 11）放到冻结之后，开始前另问用户
