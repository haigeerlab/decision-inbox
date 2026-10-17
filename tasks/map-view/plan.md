<!-- spec-guard: review approved -->
# Implementation Plan: map-view

> 依据：`spec/map-view.md`（已批准）。任务清单：`tasks/map-view/todo.md`。

## Overview

先做两处返工：message-protocol 解析「模块」字段，review-registry 记模块并按模块读取。然后按「单元格写法 → 表头 → 折叠与整表 → 全部线与选线 → 命令行」的顺序实现。每个任务先写失败的测试，再实现到全绿，单独提交。代码在 `decision_inbox/mapview.py`。

## Architecture Decisions

- **单元格写法各写成一个小函数**（状态、Spec/Plan 评审、架构审查、备注），每个函数只读一个 `ModuleFact` 和本插件的少量数据，测试可以逐个断言。
- **整表由三部分拼成**：表头行、表格头两行（列名和分隔行）、模块行（按位次排序，折叠后的合并行插在对应位置）。合并行的位置：已完成的合并行放在被合并模块里最小位次的地方，未就绪的合并行同理。
- **review-registry 的模块**：存在每个审查编号的记录里，键名 `module`。新一轮写了模块就更新，没写就保留原值。旧记录没有这个键，读作 None。`module_reviews` 返回 `ModuleReview` 元组，按审查编号排序。
- **时间写法**：用 hub-view 的 `ago`；「更新于 HH:MM」按本机时区。
- **命令行**：在 `__main__.py` 的子命令表里加 `map`，沿用 Task 6 写好的参数解析方式。

## 影响面

- 新增：`decision_inbox/mapview.py`、`tests/test_mapview.py`。
- 修改（返工）：`decision_inbox/protocol.py`、`decision_inbox/reviews.py`，及其测试 `tests/test_protocol.py`、`tests/test_reviews.py`。另外，`spec/message-protocol.md`、`spec/review-registry.md` 要补接口，这两处需要复审。
- 修改：`decision_inbox/__main__.py`（加 `map` 子命令）、`tasks/map-view/todo.md`（勾选）、`.agent/state.json`（最终验收时切换当前模块）。
- 用户可见界面：输出是收件枢纽里显示的 Markdown 表格，要等 onboarding 接上收件枢纽后才能在桌面版里看。验收时贴出默认视图、`全部`、`all` 三种样例输出；桌面版的显示效果记为「UI 未验证」。

## Task List

### Phase 1：返工与单元格

- [ ] Task 1：返工——【审查结论】的「模块」字段、review-registry 记模块与 `module_reviews`（Spec 验收 11）
- [ ] Task 2：状态、Spec/Plan 评审、架构审查三列的写法（Spec 验收 2、3、4 的列内部分）

### Checkpoint 1（report）

- [ ] 全部测试全绿

### Phase 2：整表与查询

- [ ] Task 3：表头 3～4 行与备注（Spec 验收 4 的表头部分、6、7）
- [ ] Task 4：折叠与整表，和完整期望文本逐字比对（Spec 验收 1、5）
- [ ] Task 5：`/map all`、选线、读不出能力图（Spec 验收 8、9、10）
- [ ] Task 6：命令行 `map` 子命令与只读校验（Spec 验收 12）

### Checkpoint 2（gate）：模块最终验收

- [ ] 全部测试全绿；12 条验收标准逐条对应测试；贴出三种样例输出；列出实际改动的文件；给出 message-protocol、review-registry 两份规格的修订内容供复审
- [ ] 本 Plan 获批即授权：
  - Task 1 的返工；
  - 每个任务完成后在当前分支做一次本地提交。
  - 不授权推送、不授权开 PR。两份上游规格的修订要另行复审。

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| 返工改动影响已完成的协议解析和审查轮数 | 中 | 只加可选字段和只读函数；先确认原有测试不改也全过，再加新测试 |
| 完整期望文本里的表格空格、全角符号容易对不上 | 中 | 期望文本写成测试里的一整段常量，用 `assertMultiLineEqual` 显示差异 |
| 用本机真实的 spec-guard 跑命令行会慢，结果也随仓库变化 | 低 | 命令行测试用不存在的插件记录文件，不启动 spec-guard；另用 `map-0.63.json` 夹具测排版 |

## Open Questions

无。
