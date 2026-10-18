# Todo: glossary-rename

- [x] Task 1：旧称扫描测试骨架
  - 验证：`tests/test_glossary.py` 辅助函数测试过（标签、字段名、复合词不算命中）；各区域扫描先标 expectedFailure
- [x] Task 2：等待记录 W 编号（Spec 验收 2）
  - 验证：主视图、列表显示 W3；「关掉 W3」「关掉 #3」都能关，回复写 W3；「看 W3」能查；「结束：#3」照旧
- [x] Task 3：命令输出换用词、收件箱线名（Spec 验收 1、3）
  - 验证：对应区域去掉 expectedFailure；旧线名「收件枢纽」显示为「决策收件箱」
- [x] Checkpoint A（report）：全量测试通过（816 个，预期失败 9 项留给 Task 4、5）
- [x] Task 4：协作规则段（Spec 验收 1、5）
  - 验证：规则段扫描过；契约标签原文仍在；契约 v2.1 样例全过
- [x] Task 5：命令说明、SKILL、README、术语表帮助页（Spec 验收 1、4）
  - 验证：扫描过；`glossary` 输出与副本逐字一致；打包测试含新文件
- [ ] Task 6：全量收尾与 UI 自验（Spec 验收 1、6）
  - 验证：无 expectedFailure；例外都有原因；全量测试通过；渲染主视图、「看 W3」、规则段对照
- [ ] Checkpoint B（report）：全量测试通过

## Checkpoint（gate）：模块最终验收

- [ ] 全部测试通过；每条验收标准有证据；列出实际改动的文件
