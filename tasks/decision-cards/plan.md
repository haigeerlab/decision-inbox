<!-- spec-guard: review approved -->

# Implementation Plan: decision-cards

> 依据：`spec/decision-cards.md`（用户 2026-10-19 批准，指纹 65ed289206df；D1 选 A）。任务清单：`tasks/decision-cards/todo.md`。分支 `claude/decision-cards-9de87b`（从 main a2ecc67 = v0.0.29 开出）。

需要的外部条件：无（不装依赖、不联网；只用仓库已有的 `python3`、`git` 与测试）。

## Overview

八个任务，每条修复先写在 v0.0.29 上会失败的测试再改：先做独立的小修复（超时、计数、答复解析），再做发送记账，然后是卡片本体、全文、停止检查、弹窗兜底，最后改规则段与文档，并用 di-p0 数据副本实跑。不升版本号，不推送。

## Architecture Decisions

- **`decision_inbox/cards.py`（新）**：卡片的分类和排版集中在这里，`view` 只负责调用。
  - `kind(it)`：返回 7 类之一，判据见 Spec 第 1 节；为第二期留好入口，以后读到契约的「类型」时优先用它。
  - `points(it)`：按 Spec 第 2 节的挑选规则，从「要点」挑出内容行，并返回「有没有截掉内容」。
  - `conclusion(it)`：审查原文能读到时，用 `protocol.parse` 解析【审查结论】；读不到退回审查标签；都没有写「未审查」。
  - `render(g, it, now, bg)`：输出一张卡的文字。
  - `copy_text(it)`：这张卡复制块里的内容，「一次答完」也调它。
- **`view`**：
  - `_item_card` 和 `render_approval` 的主视图部分都改调 `cards.render`；
  - `_combined` 改调 `cards.copy_text`，审批项和带 D 决定的项都算进去；
  - `render_approval` 改名为 `render_full`，作为「看 N 全文」，原文不再用代码块包；
  - 去会话操作那一栏改成第 7 类卡；
  - 审批卡不再调 `loop_head`。
- **发送记账（`hub`）**：
  - `_also_answers` 去掉 `withdrawn`；
  - `sent(g, done, failed, at, reasons=None, skipped=None)` 记下失败原因，从原因里认出「Cannot close request #X」后去掉 X，并记下 skipped；返回值里加上给用户看的 `show` 文字；
  - `reply` 不再写「已转达」，改成「已收下你的答复」；
  - 新增 `items.delivered(it)`：发给提出方的那条有成功记录才算已转达。主视图的「刚转达」、`/item`、`/lines`、停止钩子都用它判断。
- **`__main__ inbox sent`**：`--failed out:N[=原因]` 可以带原因，新增 `--skipped out:N=<id>[,<id>]`；输出加 `show`。
- **答复解析（`items.interpret_reply` 与 `hub.reply`）**：
  - 段尾去掉多余的标点；
  - 写了编号、却认不出选项字母时，回一个问题；
  - 新增「N 原话：…」写法；
  - `hub.reply` 新增「重发 N」「看 N 全文」两条指令；
  - 以「重发」「看」「关掉」开头但格式不对的话，告诉用户正确写法，不再当成答复去解析。
- **停止检查（`stophook.hub_turn_check(payload)`）**：
  - 读 `transcript_path` 指向的 JSONL：本轮从最后一条字符串型的 user 消息算起，找出最后一次运行 `decision-inbox view` 或 `inbox reply` 的 Bash 调用及其输出；输出不全时，读命令落盘的 `io/view.txt`、`io/reply.json`。
  - 拿这份输出对照本轮最后一条 assistant 文字。
  - `__main__._hook` 先做这项检查，再按 cwd 去找名册。已核对本机会话记录格式：user 消息、Bash 的 tool_use／tool_result、assistant 文字都能读到。
- **弹窗兜底（DI-9）**：
  - 新增 `decision_inbox/desktop.py`，解析巡视会话写下的桌面版会话列表 JSON；
  - `view` 和 `patrol plan` 新增选填 `--sessions`；
  - 字段名以 Task 7 抓到的真实样本为准。
- **小修**：
  - `crew.DEFAULT_TIMEOUT` 改为 15；
  - `stall._findings` 只数最后一次答复之后的事项；
  - `stall._module_findings` 只数 `answers[-1].at` 之后的 asks。

## Task List

- **Task 1：超时与报批计数**（DI-8 的 I-12、I-13；验收 12、13）
  - 先写测试：
    - `tests/test_crew.py`：默认超时为 15 秒；
    - `tests/test_stall.py`：同一件事最新那项已答复或已结项后，不再出「报批 M 次」；答复之后又来问 3 次，照常出；module-crew 的 asks 只数最后一次答复之后的。
  - 再改 `crew.py`、`stall.py`。
- **Task 2：答复解析与操作指令**（DI-7；验收 9、10）
  - 先写 `tests/test_items.py`、`tests/test_hub.py` 的用例：
    - `56 A」`、`56 A。`、`56 A）` 都解析成 A；
    - `56 好的` 得到提醒；`56 原话：好的` 原样转出、不带选项原文；
    - 「重发 56」「看 56 全文」被识别；「重发 #56 去掉 x」得到写法提示，不再是「没看出这句是答哪一项」；
    - 收件箱输出里所有答法示例的扫描测试：先收集一组典型视图的输出，从中抽出「回「…」」「说「…」」的内容，逐条喂给 `reply`。
  - 再改 `items.py`、`hub.py`。
- **Task 3：发送记账与「已转达」**（DI-5、DI-6；验收 7、8）
  - 先写测试：
    - 已撤回的事项不进 alsoAnswers；
    - `sent` 带原因「Cannot close request #X…」时，从那条消息里去掉 X，以后也不再放；
    - `--skipped` 记账；
    - `reply` 的显示里没有「已转达」；
    - `sent` 的 `show` 写清成功或失败（事项号、收件人、原因）；
    - 没发成的事项：主视图写「已答复，待发送」，「刚转达」里不出现，`/item` 也写「待发送」，停止钩子不催【已恢复】。
  - 再改 `hub.py`、`items.py`、`view.py`、`query.py`、`stophook.py`、`__main__.py`。
- **Task 4：7 类卡片与一次答完**（DI-1、DI-2、DI-8 的 I-10；验收 1、2、3、11）
  - 先写 `tests/test_cards.py`（新）和 `tests/test_view.py` 的用例：
    - 逐类断言外框与字段顺序；
    - 每张要回答的卡片恰好 1 个复制块，去会话操作卡和其他区块 0 个代码块；
    - 挑选规则：「验收标准与证据」压成一行、同一节重复只算一次、最多 6 行、每行截到 80 字、卡片不超过 18 行、截掉内容时有「看 N 全文」提示；
    - 「结论」：审查原文读得到、读不到、没有审查原文三种情况；
    - D 决定合进同一个复制块；
    - 「一次答完」含审批项，并能被 `interpret_reply` 一次解析成全部答复；
    - 有打转数据时，最终验收卡抬头里没有「进度」。
  - 再写 `cards.py`，改 `view.py`。
  - 旧测试里断言旧版卡片写法的，改成新写法，并在 todo 里列出改了哪些。
- **Task 5：看 N 与看 N 全文**（DI-3；验收 5）
  - 先写测试：
    - 「看 N」只出卡片；
    - 「看 N 全文」有原文且没有任何代码块，非 Markdown 文件每行带「│ 」；
    - 超过 300 行截断，并写明剩余行数；
    - 已结项、已失效的事项也能看。
  - 再改 `view.py`、`hub.py`。
- **Task 6：收件箱停止检查**（DI-4 选 A；验收 6）
  - 先写 `tests/test_stophook.py` 的用例，用造出来的会话记录 JSONL：
    - 拦：缺卡片抬头、缺复制块、复制块改了一个字、没有待答事项却出现代码块；
    - 放：本轮没跑 view 或 reply、`stop_hook_active` 已标、记录读不懂、全部对得上；
    - 原有开发线停止钩子的用例不变。
  - 再改 `stophook.py`、`__main__.py`。
  - doctor 加一项：用本机最近一份会话记录试读一次，报告「读得懂／读不懂」。
- **Checkpoint（gate）：DI-9 的信号样本**
  - 要你配合：让某个会话停在一次权限弹窗上（任意会话都行，弹窗不用点），我调桌面版会话列表抓一份样本，存进测试 fixture。
  - 样本里有「停在弹窗」的状态：照 Task 7 做。
  - 没有：我把实际字段报给你，你决定 Task 7 是缩成只覆盖登记过邮箱的会话，还是先挂起。
- **Task 7：会话停在弹窗上的兜底提醒**（DI-9；验收 14）
  - 先写测试，用样本 fixture：
    - 满 5 分钟、没有对应事项时出第 7 类提醒，且没有复制块；
    - 有对应事项、不满 5 分钟、读不到会话列表时都不出，读不到时写「读不到会话列表」；
    - 只看名册里的会话和它们开出来的会话。
  - 再写 `desktop.py`，改 `view.py`、`patrol.py`、`__main__.py`；巡视提示词加一步「读会话列表写入 io」。
- **Task 8：规则段、文档与真实数据验收**（Spec 第 10 节；验收 4、15）
  - 改 `hub.CONVENTION`：停止时会被程序检查；失败要填原因；`inbox sent` 的 show 也要贴；新增「看 N 全文」「重发 N」「N 原话：」三种写法。
  - 改 README「提请批准怎么读」「要你去会话里操作」两节，`docs/glossary.md` 加「复制块」「看 N 全文」。
  - 用 di-p0 的 `items.json` 副本实跑：放在 scratchpad，把 #47、#49、#50、#54 置为待答，用 `DECISION_INBOX_HOME` 指向副本。跑 `view`，再逐张对照模板样例，看外框、字段顺序、复制块、行数。结果写进 todo；真实状态目录前后的 md5 不变。
  - 全量测试通过。

## Checkpoint（gate）：模块最终验收

列出改动的文件和行数（取自版本库）、每条验收标准的证据和测试数。你批准后开 PR（base main），由你合并；不推送标签。

## 影响面

- 主视图卡片整体变短，审批卡不再展开原文，原文要回「看 N 全文」；「看 N」的含义改成只看卡片。
- `inbox sent` 多了 `show` 输出和 `--skipped` 参数，`--failed` 可以带原因；旧写法照样能用。
- 协作规则段改了，已接入的收件箱重跑接入才生效。di-p0 冻结期间不升级。
- 停止钩子新增一个分支，只在本轮跑过 `view` 或 `inbox reply` 的会话生效，其他会话的行为不变。
- 不改 `items.json` 的状态取值，不改契约，不改其他插件。

## 风险

| 风险 | 对策 |
|---|---|
| 会话记录格式变了，停止检查失效 | 读不懂就放行，并在 stderr 写原因；doctor 会报出来 |
| 停止检查误拦（例如会话把卡片按 Markdown 换了缩进） | 只对抬头行和复制块内容做逐字比较，忽略空白差异；只拦一次 |
| 挑选规则把关键内容挤掉 | 卡片上一律提示「看 N 全文」；用真实数据实跑核对 |
| 桌面版会话列表不给弹窗状态 | 前面设了检查点，先抓样本，没有就报给你定 |
| 旧测试大量断言旧卡片写法 | 按新写法改，并在 todo 列出改过哪些，最终验收时交你看 |
