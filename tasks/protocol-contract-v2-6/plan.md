<!-- spec-guard: review approved -->

# Implementation Plan: protocol-contract-v2-6

> 依据：`spec/protocol-contract-v2-6.md`。任务清单：`tasks/protocol-contract-v2-6/todo.md`。分支 `claude/v0037`（stage-c3-fixes 已验收，34e461a）。

需要的外部条件：无。契约样例取自本机 session-protocol 仓库的 92309e7。

## 架构决定

- **样例**：`tests/fixtures/session-protocol/v2.6/` 原样拷贝 92309e7 的 `fixtures/`，包括 `SHA256SUMS`，然后删掉 v2.4 目录，`protocol.CONTRACT_VERSION = "2.6"`。拷贝那一刻，v2.6 新增的样例会在契约测试里先失败，作为后面各任务的失败测试；之后每个任务让其中一部分变绿。
- **「任务」**：
  - `protocol` 里【等待用户】【审查结论】的字段名单加上「任务」。
  - `Message` 新增 `task` 字段：合格时是原文，否则为 None。
  - 问题代码在各类型原有检查之后追加，先 `bad-task-ref`、后 `module-task-both`；`module-task-both` 只在「模块」去掉首尾空白后不是空、也不是「无」时报。
  - `tests/test_contract.py` 的 `to_contract` 加 `"task"` 键。
  - `items._record` 存 `task`。
- **C 待定编号**：
  - `protocol._DECISION_HEAD_RE` 改成认 `D\d+` 或 `C\d+-\d+`。
  - `items._DECISION_ANSWER_RE` 同样认这两种，再加「选」「：」两种写法（这两种 D 编号本来就认）。
  - `items._PREFIXED_RE` 加上 `T\d+` 和 `C\d+-\d+`。
  - `_split_inline` 和夹带检查不把前面紧挨「-」的数字当事项号，统一写成一个判断函数 `_bare_number_at(text, i)`：前一个字符是 ASCII 字母、数字或「-」时就不算。
- **新小项名**：
  - `_SPEC_POINTS`、`_PLAN_POINTS` 改成「认得的名字」集合，新旧名都在里面。
  - `_points` 按书写顺序收进来，名字保留原样，不换算。
  - 卡片显示照收到的名字原样列出。
- **卡片显示「任务」**：`cards` 生成抬头时，事项有 `task` 就在原来写模块的位置写「任务 T3」。
- **规则段与文档**：
  - 收件箱规则段加一句：用户回复里的 T 编号、C 待定编号不是事项号，待定问题按 C 编号或 D 编号逐条答。
  - README 写 0.0.37（两个模块）的说明和升级步骤。
  - 术语表加「轻任务」「C 待定编号」。
  - 两个 plugin.json 改成 0.0.37。

## 任务清单

- **Task 1 拷入 v2.6 样例，读「任务」**（Spec 假设 1、2；验收 1、2、7 的解析部分）
  - 验证：拷入后，task-escalation、task-module-both、task-bad-ref、review-conclusion/task 四份在契约测试里改前失败、改后通过。
  - 另加 `tests/test_protocol.py` 用例：问题代码的顺序；「模块：无」和「任务」同时写时合格。
- **Task 2 C 待定编号与 T 编号**（假设 3、4；验收 3、4、5）
  - 验证：decision-cnum、decision-cnum-bad 在契约测试里转绿。
  - `tests/test_items.py` 新类覆盖下面几种，改前失败、改后通过：
    - 「41 A；C15-1 B」只答 #41，C15-1 选 B，不碰事项 1；
    - 「C15-1：B」「C15-1 选 B」也认；
    - 只答「41 A」时整条追问，写明缺 C15-1；
    - 只剩 #78 一项待答时，「T78 先缓一缓」被追问；
    - 「78 A；T3 先做」照常答 #78，T3 原样留在原话里。
- **Task 3 新小项名**（假设 5；验收 6）
  - 验证：card-spec-upstream、card-plan-upstream 在契约测试里转绿。
  - `tests/test_cards.py` 加用例：新名卡片显示「边界」「未决问题」「架构决定」；新旧名同时出现时两行都在；旧名卡片输出不变（现有用例不改）。
- **Task 4 卡片抬头显示任务**（假设 2 的显示部分；验收 7）
  - 验证：`tests/test_cards.py` 加用例：带「任务：T3」的审批卡，抬头有「任务 T3」，没有「模块 未知」。
  - 契约测试全部通过，`SHA256SUMS` 核对一致。
- **Task 5 规则段、文档与版本 0.0.37**（假设 7、8；验收 8）
  - 规则段加 T 编号和 C 待定编号的说明，`test_hub` 断言规则段里有这两句。
  - README 写 0.0.37 说明和升级步骤（收件箱重跑 hub-setup；开发线不用重跑 join），排查表不再加。
  - 术语表加两条，`test_glossary` 通过。
  - 两个 plugin.json 和 `test_packaging` 改成 0.0.37。
  - 全量测试通过。

## Checkpoint（gate）：模块最终验收

- 列出实际改动的文件（新增、修改与行数，取自版本库）和测试数。
- 在临时组重放两件事：
  - 统筹的沙箱场景：只剩 #78 时说「T78 先缓一缓」；
  - 「41 A；C15-1 B」从收到卡片到转达的全过程（发给提出方的【用户答复】里的原话）。
- 批准后开 PR（base main，由用户合并），PR 包含 stage-c3-fixes 和本模块；合并后打标签、建固定副本，再回报统筹。

## 风险

| 风险 | 对策 |
|---|---|
| 删掉 v2.4 目录后，有别的测试直接读 v2.4 路径 | 改前先 grep `v2.4`，只有按 `CONTRACT_VERSION` 拼路径的才保留 |
| C 待定编号的正则误吃提交号、日期（如 2026-10） | 只认大写 C 开头、前后不紧挨字母和数字；有反例测试 |
| 新旧小项名混用，卡片显示顺序乱 | 按书写顺序原样显示，不排序、不换算，和契约的期望结果一致 |

## 未决问题

- 无（Spec 的两条未决问题都不在本模块范围内）。
