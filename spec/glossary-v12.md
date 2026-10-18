<!-- spec-guard: review approved 862d5d2c0e8a -->

# Spec: glossary-v12

> 能力图模块 `glossary-v12`（2026-10-19 用户确认插入，排在最后，不插队）。来源：接入协调人转来术语表 v1.2（`livesaas-integration/GLOSSARY.md`），与 spec-guard 0.75.0（display-terms）对齐；插入时的假设 1–6 用户 2026-10-19 确认。

## 目标

给人看的文字跟上术语表 v1.2：`/map` 审查列的批准标记与 spec-guard 的 `/map` 写法一致，术语表副本更新到 v1.2，旧称扫描挡住「评审节奏」「待审核」「待审」再出现。

## 现状（已核对代码）

- **术语表 v1.2 比 v1.1 多三处**：
  - 「评审节奏」改名为「批准节奏」，配置键仍是 `reviewCadence`；
  - 「待审核」改名为「待批准」；
  - 新增「审阅」，指用户把一份东西看一遍，不等于批准。
- **`/map` 审查列**：`decision_inbox/mapview.py` 的 `_REVIEW_MARKS` 把 spec-guard 的五种取值写成「通过／待审／改后待复审／异常／不适用」。spec-guard 0.75.0 的 `REVIEW_WORDS` 写成「✔／待批准／改过待重审／标记无效／无标记」。表头「Spec/Plan 批准」已经是新叫法，不用改。
- **README**：第 106 行照写了旧的五个词。
- **术语表副本**：`docs/glossary.md` 还是 v1.1。
- **旧称扫描**：`tests/test_glossary.py` 的 `OLD` 已经有「评审」→「审查」。「评审节奏」含「评审」，已经挡住；「待审核」「待审」还没挡。
- 代码、命令、skill 里没有「评审节奏」「待审核」。

## 要做的

1. **审查列标记**：`_REVIEW_MARKS` 改成和 spec-guard 0.75.0 一致：approved→✔，pending→待批准，revised→改过待重审，invalid→标记无效，none→无标记。有外部参考意见时的后缀「（有参考意见）」不变。
2. **README**：第 106 行的五个词同步更新。
3. **术语表副本**：`docs/glossary.md` 按原件更新到 v1.2，开头的来源行写 v1.2。
4. **旧称扫描**：`OLD` 加上「待审核」→「待批准」、「待审」→「待批准」。「评审节奏」已经被「评审」覆盖，不重复加。模块文档字符串里的「v1.1」改成「v1.2」。

## 关键决策与取舍

1. **五个标记全部照 spec-guard 写**（假设 1）：用户在两个插件的 `/map` 里看到的同一个状态，写法一致。这会推翻 doctor-and-observer 决定 3 里「对照表由本插件维护」的具体写法，但「由本插件维护」这一点不变：映射仍写在本插件里，不在运行时读 spec-guard 的写法。
2. **「待审」也算旧称**：它是「待审核」的简写，按术语表应改成「待批准」。扫描时如果把「待审查」误判成旧称，写进 ALLOWED 并说明原因（预计不会有：现行文字里没有「待审查」）。

## 范围

做：`decision_inbox/mapview.py`、`README.md`、`docs/glossary.md`、`tests/test_glossary.py`、`tests/test_mapview.py`，以及其他断言旧写法的测试。

不做：
- 契约标签、字段名、JSON 取值和行为都不改；
- 历史记录（`spec/`、`tasks/`、`docs/requirements-record.md`）不改（假设 4）；
- 本仓库 `CLAUDE.md` 的 spec-guard 约定块不改，等 spec-guard 的 `setup-convention --replace` 更新（假设 5）；
- 不动版本号：另开版本号 PR，冻结和安装切换另请用户批准（假设 6）。

## 验收标准

1. `/map` 审查列五种取值分别显示 ✔、待批准、改过待重审、标记无效、无标记；有外部参考意见时仍带「（有参考意见）」。
2. README 的审查列说明与第 1 条一致。
3. `docs/glossary.md` 与 `livesaas-integration/GLOSSARY.md` 的正文一致（除开头来源行），版本写 v1.2。
4. 旧称扫描加入「待审核」「待审」后全部通过。
5. 全量测试通过。

## 假设

1. spec-guard 0.75.0 的 `REVIEW_WORDS` 就是它以后的稳定写法；以后再改，本插件另开模块跟进。
2. `/map` 的表格宽度不受影响：新写法和旧写法一样短。

## 未决问题

无。

## 文档建议

README：第 106 行改审查列的五个词。其余无。
