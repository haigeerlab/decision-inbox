<!-- spec-guard: review approved f1da2f85d866 -->

# Spec: patrol-stop-fixes

> 能力图模块 `patrol-stop-fixes`（2026-10-19 用户确认插入，显式插队；#27 实测记录还没合并，main 上 stall-and-patrol 的实测项仍显示未勾）。来源：stall-and-patrol 冻结后实测（`tasks/stall-and-patrol/field-test.md`，#27）发现的问题 1、3；插入时的假设 1–5 用户 2026-10-19 确认。

## 目标

1. 卸载决策收件箱时，巡视会话能被顺利归档：先让它停掉自己的 `/loop` 循环，再归档。
2. 给人看的文字里不再出现单独的「身份」，统一叫「邮箱名」（术语表 v1.1）。

## 现状（已核对代码与实测）

- **归档被拒**：巡视会话按 hub-setup 的提示词用 `/loop 5m` 在会话里建了定时任务。0.0.23 实测时，照卸载输出的「用 archive_session 归档巡视会话」去做，宿主回「still has live work」拒绝归档；巡视会话用 CronDelete 删掉循环任务之后，才归档成功。
  - 开巡视会话的步骤在 `onboard.hub` 的后续步骤里（提示词开头是「用 /loop 5m 执行下面的巡视提示词，每轮做完就等下一轮，不做别的事」），没有约定怎么让它停。
  - `onboard.teardown` 的后续步骤只有「用 archive_session 停掉并归档巡视会话 <编号>」。
  - `hub.patrol_session_fix`（巡视停摆时主视图的提示）让用户「在里面重新发一次『/loop 5m』加巡视提示词」，也没带停止约定。
  - `commands/teardown.md` 允许的工具里没有 `send_message`。
- **「身份」漏改**：旧称扫描只查「身份名」。代码里还有 3 处给人看的「身份」：
  - `patrol.PROMPT`「把 text 原样发给身份 target」；
  - `stophook`「名册里没有身份 X」；
  - `query`「身份失效（agent-relay 里这个身份已退役）」。

  README 里还有几处，比如「登记身份」「联调身份」「是否登记了身份」。

## 要做的

1. **约定停止巡视的说法**：hub-setup 开巡视会话的提示词开头那句改成：「用 /loop 5m 执行下面的巡视提示词，每轮做完就等下一轮，不做别的事；收到『停止巡视』时，用 CronDelete 删掉这个循环任务，回一句『已停』就结束」。`hub.patrol_session_fix` 里「重新发一次『/loop 5m』……」也要带上这句约定。
2. **卸载先停再归档**：`onboard.teardown` 登记过巡视会话时，后续步骤改成两条：
   - 第 1 条：「用 send_message 给巡视会话 <编号> 发『停止巡视』，等它回『已停』」；
   - 第 2 条：「用 archive_session 归档巡视会话 <编号>；它不认这句话（旧版巡视会话）或归档仍被拒时，请用户在那个会话里停掉循环，或从侧边栏归档」。
3. **命令文件**：`commands/teardown.md` 允许的工具加上 `mcp__ccd_session_mgmt__send_message`，第 3 步写明先发停止消息、等回复，再归档。
4. **「身份」改名**：上面 3 处代码和 README 里给人看的「身份」改成「邮箱名」，读不通的地方按句意改写。旧称扫描的词表加上「身份」（→ 邮箱名）。
5. **README 升级一节**：写明这一版之前开的巡视会话不认「停止巡视」，要重跑 hub-setup 才拿到新提示词；卸载旧组时，巡视会话要手动停掉或从侧边栏归档。

## 关键决策与取舍

1. **由巡视会话自己删任务**：`/loop` 建的是会话内的定时任务，只有那个会话能用 CronDelete 删掉；决策收件箱只能发消息请它删。
2. **不让卸载自动等待**：命令行程序只输出步骤，由执行卸载的会话照做、等回复，和现有「按后续步骤逐条做」的方式一致。

## 范围

做：`decision_inbox/onboard.py`（开巡视会话的步骤、卸载步骤）、`hub.py`（`patrol_session_fix`）、`patrol.py`（PROMPT 里的「身份」）、`stophook.py`、`query.py`、`commands/teardown.md`、README、`tests/test_glossary.py`，以及对应测试。

不做：
- 不自动更新已经在跑的巡视会话；
- 不改 agent-relay 或宿主；
- 不动版本号（另开版本号 PR，冻结和安装切换另请用户批准）。

## 验收标准

1. 开巡视会话的步骤和 `patrol_session_fix` 里都有「收到『停止巡视』」「CronDelete」「已停」。
2. `onboard teardown` 登记过巡视会话时：
   - 后续步骤里先出现「send_message」「停止巡视」，后出现「archive_session」；
   - 第 2 条写明旧巡视会话不认这句话时怎么办；
   - 没有巡视会话、只有旧定时任务时，输出不变。
3. `commands/teardown.md` 允许的工具里有 `mcp__ccd_session_mgmt__send_message`，正文先停再归档。
4. 旧称扫描加入「身份」后全部通过：代码、命令、SKILL、README 里不再有单独的「身份」。
5. 全量测试通过。

## 假设

1. 宿主的 `/loop` 在会话里建的任务可以用 CronDelete 删掉（实测里巡视会话照做成功）。
2. 「邮箱名」能涵盖 agent-relay 里的 agent 名字和登记（例如「登记身份」改成「登记邮箱名」）。

## 未决问题

无。

## 文档建议

README：改「身份」的用词、写明卸载要先停后归档、升级一节加上旧巡视会话的说明。其余无。
