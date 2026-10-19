# Todo: decision-cards

- [x] Task 1：超时与报批计数（DI-8 的 I-12、I-13；验收 12、13）
  - 验证：`tests/test_crew.py`、`tests/test_stall.py` 新用例先失败后通过
- [x] Task 2：答复解析与操作指令（DI-7；验收 9、10）
  - 验证：`tests/test_items.py`、`tests/test_hub.py` 新用例先失败后通过；答法示例扫描通过
  - 改写的旧测试（按 Spec 第 7 节，带编号却没有选项字母的话不再静默转出）：`test_items` 的 `test_copy_block_and_free_sentence`、`test_free_sentence_forwarded_verbatim` 改用「N 原话：…」；`test_loops` 的 `test_words_are_plain_text_without_a_hint` 改为先断言被问回、再用「N 原话：继续等」
- [x] Task 3：发送记账与「已转达」（DI-5、DI-6；验收 7、8）
  - 验证：新用例先失败后通过
  - 改写的旧测试：措辞——`test_hub` 的 `test_letter_answer`、`test_owner_item_copies_its_dev_lines`、`test_receive_reply_sent_view`（「已转达」→「已收下你的答复」，sent 输出多了 show）、`test_view_without_relay_and_unsent`、`test_main_view_warns_unsent_and_unreadable_relay`（「有 N 条没发出去」→逐条列出）、`test_superseded_and_withdrawn_closed_once`（已撤回的不进 alsoAnswers）；造数据——`test_view` 的 `forward`、`test_patrol` 的 `answered_item`、`test_stophook` 的 `answered` 与 crew 用例补发送记录（不改被测行为）
  - 顺带：巡视「答复卡在离线负责人」只看已发出的答复（patrol._handoffs），否则没发出去的答复也会叫醒负责人
- [x] Task 4：7 类卡片与一次答完（DI-1、DI-2、I-10；验收 1、2、3、11）
  - 验证：`tests/test_cards.py` 等新用例先失败后通过；列出改写的旧测试
  - 改写的旧测试（都是断言旧卡片写法的，按模板改写，原意保留）：`test_view` 的 ItemCardTest 全部、ReviewLineTest 全部、DecisionCardTest 全部（含「一次答完」改为包含带 D 的项）、NeedsUserCardTest 一条、LetterSelfCheckTest 的自检正则、FullViewTest 的样例（hub-view 主视图样例里的卡片段换成模板卡片，其余照旧）、`card()` 辅助；`test_approval` 的「主视图只展开第一项」改为「一项都不展开，看 N／看 N 全文」；`test_go_to_session` 两条（第 7 类卡片的抬头与提醒写法）；`test_loops` ShowTest 四条（卡片抬头不带打转数据、不再折叠历史，历史只在「看模块」）
  - 写法细节（最终验收时交用户看）：①「一次答完」各项都没有「，；」时用「，」连成一行（同模板例子），有任何一项带这些符号（如 `49 B 换方案：…，先给我看预览`、`40 A；D1 A`）就一项一行，保证能被一次解析；②第 6 类卡片也带第二行「项目 · 线」，不然看不出是哪条线问的；③「注意」按 Spec 假设 3 取审查标签的「正文提到」和写法提示（writingNotes）
- [x] Task 5：看 N 与看 N 全文（DI-3；验收 5）
  - 验证：新用例先失败后通过
  - 改写的旧测试：`test_approval` 的 VerbatimTest（不再加围栏）与 DisplayTest 一条（原文每行带「│ 」）
  - 补充规则：Markdown 原文里自带的围栏行（``` 或 ~~~ 开头）也加「│ 」，不然全文里仍会出现代码块
- [x] Task 6：收件箱停止检查（DI-4；验收 6）
  - 验证：`tests/test_stophook.py` 新用例先失败后通过；原有用例不变
  - 真实数据回放（只读，复制到 scratchpad 逐轮截断）：di-p0 收件箱主会话记录 81 轮，78 轮出过主视图，按新规则会拦 4 轮——2 轮是 0.0.29 旧格式（原文套 ```text 围栏、审批卡没复制块）对不上；2 轮是收件箱在没有待答事项时自己编了一个复制块「开 rh2-zeta 会话；D1 A」，正是 I-8 那类问题。其余 74 轮放行
  - doctor 新增「收件箱停止检查」：在最近 50 份会话记录里找收件箱出过主视图的那份试读，读得懂 ok，读不懂 bad，找不到 unknown；会话记录目录可用 DECISION_INBOX_TRANSCRIPTS 改
- [x] Task 7：会话停在弹窗上的兜底提醒（DI-9；验收 14）
  - 验证：`bridge_sessions` 夹具上的新用例先失败后通过（waiting 字段值按 rh2-coord 转述，夹具注明来源）
  - 巡视提示词已加「读 bridge_sessions 写入 sessions.json」与 `--sessions`；收件箱规则段的对应步骤放到 Task 8 一起改
  - 待核对：第一次遇到真弹窗时读一次 `bridge_sessions`，看 `status`／`waitingFor` 是不是转述的写法
- [x] Task 9：升到 session-protocol v2.3，卡片改读新字段（Spec 要做的 10；验收 15）
  - 验证：v2.3 样例一致性测试先失败后通过；card-final、card-spec-plan 卡片用例先失败后通过
  - 样例：`tests/fixtures/session-protocol/v2.2` 改名 v2.3，用契约 6b8810e 的 `git archive` 覆盖解出（已有样例零改动，新增 4 份，SHA256SUMS 全部对上）
  - 偏差（最终验收时交用户看）：「Spec 与 Plan」九项、「接口提案」七项放不进 18 行，行数上限按小项数放宽（超过 5 项的每项加 1 行：spec-plan 22、interface 20），不砍模板要求的小项
  - 顺带：停止检查也把 DI-9 的弹窗提醒抬头算作必须原样出现的行
- [x] Task 8：规则段、文档与真实数据验收（验收 4、16）
  - 验证：di-p0 副本实跑结果记在这里；真实状态目录 md5 不变；全量测试通过
  - 规则段（CONVENTION）：`inbox sent` 填失败原文和 skipped、贴 show；第 7 步与顺带巡视读 `bridge_sessions`、带 `--sessions`；停止检查说明；「看 N 全文」「重发 N」「N 原话：」。README「卡片怎么读」（取代「提请批准怎么读」）、「要你去会话里操作」「模块打转」、日常使用表、消息协议改 v2.3；`docs/glossary.md` 加「卡片」「复制块」「看 N 全文」
  - 真实数据（2026-10-19，本分支代码，DECISION_INBOX_HOME 指向 scratchpad 里 di-p0 的副本；#47、#49、#50、#54 置为待答，副本里原有的待答 #62 保留）：
    - #54（第 7 类）：抬头「#54 · 去 rh2-epsilon 模块会话（epsilon） 点一下弹窗」、被拦的操作、点、为什么批不了、链接、「你在 #47 已同意」、「点完不用回复」；0 个代码块；8 行
    - #49（第 6 类）：出了什么事 3 行＋「其余见：回「看 49 全文」」、A／B／C 各一行写后果、推荐 B、复制块 `49 B 换方案：给 delta、epsilon 追加放行 git merge main、node --test，先给我看预览`；14 行
    - #47（Plan）：抬头「epsilon 的 Plan，批不批」、第二行「crew-rehearsal · 并行协调2 · 模块 epsilon · Plan（第 1 次交审）」、内容要点 6 行、结论「main 审查通过（R-38）。#44 退回后的重交复审」、A／B 后果、推荐 A、复制块 `47 A`；18 行
    - #50（最终验收）：内容要点首行「验收结果：验收标准 7 条，标了通过的 7 条；完整检查…；例：1 word_counts(…)…」、结论「main 审查通过（R-39）…」、复制块 `50 A`；18 行
    - 一次答完一项一行（#49 的答复带「，」）：`49 B 换方案：…`、`62 A 同意`、`47 A`、`50 A`
    - 主视图里没有原文、没有 ```text 围栏；真实 `~/.decision-inbox/di-p0/state` 前后 md5 都是 53454b7c400721eceb530bc018a6ebe0
    - 和模板样例的差别（都是旧写法事项的已知限制，见 Spec 假设 1、3）：#47 的内容要点是「要点」原文前 6 行，不是模板的「分几步／会改哪些文件／风险」；#47、#50 的「注意」是写法提示「「你该回」只写了选项字母」（Spec 假设 3 的来源之一），模板样例写的是「无」；#47 显示「第 1 次交审」（#44 是 delta、epsilon 合在一项交的，模块对不上，不算同一模块的上一次）
    - 实跑时发现并修正：抬头「epsilon 的Plan」少一个空格
  - doctor（在 /tmp 下、指向副本）：新增的「收件箱停止检查」✔ 读得懂；另两项 ✘ 是副本没有转发脚本、收件箱规则段不是当前版本（规则段改了，升级后要重跑接入），都在预期内

## 检查点

- [ ] Checkpoint（gate）：模块最终验收——全部测试通过；每条验收标准有证据；列出实际改动的文件；批准后开 PR
