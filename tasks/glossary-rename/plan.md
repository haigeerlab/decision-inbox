<!-- spec-guard: review approved -->

# Implementation Plan: glossary-rename

> 依据：`spec/glossary-rename.md`（用户 2026-10-19 批准）。任务清单：`tasks/glossary-rename/todo.md`。分支 `claude/glossary-rename`（从 main 开出，main 已含 #18–#22）。

## Overview

六个任务。先把「旧称扫描」测试搭起来（第一次跑会列出所有旧称），再按区域逐块换掉，每块换完就把这块加入扫描范围，最后扫描范围覆盖全部、全绿。不升版本号（版本号和冻结另外问你）。

## Architecture Decisions

- **旧称扫描**（`tests/test_glossary.py`，新增）：
  - 辅助函数 `old_terms(text)`：先去掉【…】标签和契约字段名（「适用会话」「待用户决定」等，以 `protocol.FIELDS` 里的字段名为准，只在「」里或行首「字段名：」形式时去掉），再找旧称表里的词，返回命中的词和所在行。
  - 「事项」只在前面不是「待决」「多线」「单线」时算命中。
  - 例外表 `ALLOWED`：逐条写文件、词和原因（例如 README 升级一节里「旧称『收件枢纽』」这种对照说明）。
- **等待记录 W 编号**：
  - 新增 `view.wait_no(n) -> "W{n}"`，所有显示等待记录编号的地方都用它：`view` 的等待记录列表和已关闭列表、`query` 的「看 N」、`health` 的提醒、`stophook`、`onboard` 的 leave 预览、`tickets` 的提示、`hub` 的「关掉」回复。
  - `hub._CLOSE_RE` 和 `_LOOK_RE` 改成接受 `W` 或 `#` 前缀，也接受无前缀数字；编号空间不变。
  - `view.py:124` 从健康信号文字里抽编号的正则，跟着改成 `W(\d+)`。
- **收件箱线名**：
  - `view._short` 和 `query._short` 遇到 role 为 hub 的条目，一律返回「决策收件箱」；
  - `onboard` 新建 hub 条目时 shortName 写「决策收件箱」。
- **协作规则段**：
  - `onboard._COMMON` 等四种角色的规则段和 `hub.CONVENTION` 换新用词；
  - 线要照写的标签和字段名照旧，第一次出现时括号注明新名称；
  - doctor 比对规则段是否最新的机制不动，旧组会提示过期。
- **术语表帮助页**：
  - `docs/glossary.md` 复制术语表 v1.1 原文，开头加一行来源、版本、日期；
  - `__main__` 新增子命令 `glossary`，读这个文件原样打印（路径按包目录定位，不依赖当前目录）；
  - `commands/glossary.md` 运行它并要求逐字显示；
  - 打包测试的关键词表加入这两个文件。

## Task List

- **Task 1 旧称扫描测试骨架**：写 `tests/test_glossary.py` 的辅助函数和例外表，以及辅助函数自身的单元测试（标签、字段名、复合词不算命中）。扫描各区域的测试先登记为 `expectedFailure`，后面的任务每做完一块就去掉一个。
  - 验证：辅助函数测试通过；扫描输出列出现有旧称的分布。
- **Task 2 等待记录 W 编号**（Spec 验收 2）：
  - `view.wait_no`；
  - 显示处全部改用它；
  - 「关掉」「看」接受 W、# 和无前缀数字。
  - 验证（`tests/test_hub.py`、`tests/test_view.py`、`tests/test_query.py`、`tests/test_tickets.py`）：
    - 主视图和列表显示 W3；
    - 「关掉 W3」「关掉 #3」都能关，回复写 W3；
    - 「看 W3」能查；
    - 契约消息「结束：#3」照旧能关。
- **Task 3 命令输出换用词**（Spec 验收 1、3）：
  - 涉及 `hub.py`（不含 CONVENTION）、`view.py`、`query.py`、`health.py`、`patrol.py`、`stall.py`、`doctor.py`、`items.py` 和 `protocol.py` 里给人看的提示、`stophook.py`、`__main__.py` 的帮助文字、`onboard.py` 的步骤和预览输出；
  - 收件箱线名显示为「决策收件箱」。
  - 验证：
    - 去掉这几块的 `expectedFailure`；
    - 名册里线名为「收件枢纽」的条目显示成「决策收件箱」；
    - 改动的断言同步更新。
- **Checkpoint A（report）**：全量测试通过，记下测试数。
- **Task 4 协作规则段**（Spec 验收 1）：
  - 四种角色的规则段和收件箱的 CONVENTION 换用词，标签和字段名带括号注明新名称。
  - 验证：
    - 规则段扫描通过；
    - 规则段里仍有【已恢复】【用户答复】等契约标签原文；
    - session-protocol v2.1 的测试样例全部通过（Spec 验收 5）。
- **Task 5 命令说明、SKILL、README、术语表帮助页**（Spec 验收 1、4）：
  - 改 `commands/*.md` 的说明和 frontmatter，以及 `skills/decision-inbox-join/SKILL.md`；
  - 新增 `docs/glossary.md`、`commands/glossary.md` 和 CLI 子命令 `glossary`；
  - README 全文换用词，加术语表入口，升级一节写明要重新 join。
  - 验证：
    - 这几个文件的扫描通过；
    - `decision-inbox glossary` 的输出和副本逐字一致；
    - 打包测试包含两个新文件。
- **Task 6 全量收尾**（Spec 验收 1、6）：
  - 扫描测试里不再有 `expectedFailure`；
  - 每条例外都写了原因；
  - 全量测试通过。
  - UI 自验：在临时目录里渲染主视图、「看 W3」和规则段，对照新用词逐行看。
- **Checkpoint B（report）**：全量测试通过，记下测试数。

## Checkpoint（gate）：模块最终验收

列出改动的文件、每条验收标准的证据、测试数和 UI 自验结果，然后开 PR（base main）。

## 影响面

- 几乎所有给人看的输出：主视图、查询、提醒、onboard、doctor、停止钩子；
- 各角色规则段，都要重新 join；
- 「关掉」「看」两个指令的输入格式（只放宽，不收紧）。

## 风险

| 风险 | 对策 |
|---|---|
| 把契约标签或字段名一起换掉，线照新规则段写出契约不认的消息 | 扫描辅助函数只看显示文字；Task 4 断言规则段里标签原文还在；契约测试样例全跑 |
| 「事项」替换过头，把「多线事项」或代码字符串改坏 | 只改字面文字，不批量 sed；复合词有专门的测试 |
| 测试断言大量依赖旧文字，改起来容易漏 | 每个任务跑全量测试，失败的断言逐条对照新用词更新，不放宽断言 |
| 用户还按旧习惯打「关掉 #3」 | 保留兼容，回复里写成 W3，慢慢引导过来 |
