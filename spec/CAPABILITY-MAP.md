# Capability Map: decision-inbox 第一版

> 由 `/spec` 的 Phase 0 产出。**必须经人工评审后才能往下走。**
> Addy 原文：把图搞错代价很大，评审十行不算什么。
> 唯一需求来源：`docs/requirements-record.md`（下文「需求 X.Y」指该文件的节号）。

## 目标

同时跑多个 AI 编码会话时，让用户只在收件枢纽一个地方看到所有等他决定的事，答一次就准确送回对应会话；同时由程序盯着哪个会话停了、卡在谁那里、消息有没有送到。第一版范围以需求 11.1 为准，只服务用户和收件枢纽（Claude 桌面版），工作会话支持 Codex 桌面版与 Claude 桌面版。

<!-- 这一段是 Proposal 评审的目标指纹底本（`spec-digest.py` 计算）。
     改写目标会让已发布的 Proposal 被判为过期，所以改了先人工评审；追加模块不需要改这里。
     标题必须是 `## 目标`（或 `## Goal`）—— 指纹脚本按标题定位这一节。 -->

## 模块

| Module id | Responsibility | Depends on |
|---|---|---|
| group-store | 插件骨架与协作组状态目录 `~/.decision-inbox/<协作组>/`：状态文件读写、编号分配、会话名册（短名、角色、所属线） | — |
| relay-reader | 只读解析 agent-relay 的 `bridge_agents`（presence、waiting）与 `bridge_outbox`（投递、确认、回复），转成统一的只读数据；`/item`、`/flow` 需要的 `bridge_wake_status`（按消息编号的状态、唤醒记录）留待 query-commands 时返工追加；不接 `bridge_thread`，消息正文不进本插件（用户 2026-10-16 确认） | — |
| spec-guard-reader | 只读调用各线仓库的 `map_view.py --project <路径> --json`：模块表与停滞数据，核对 schemaVersion；脚本从 `~/.claude/plugins/installed_plugins.json` 里 spec-guard 的 installPath 找，不写死版本路径；没装或找不到时降级为「无能力图」并说明原因，退出码 2／3／4 如实区分；不自己解析能力图和 todo | — |
| message-protocol | 第 4 节消息约定的解析与校验：消息类型、结束写法、选项写法、多线事项字段、架构审查状态行、「阻塞：等谁交付」报告 | — |
| review-registry | 审查者登记（哪个会话有审查者、审哪类节点、经用户批准才增改）、审查状态行的显示规则，以及同一审查节点来回的轮数（供信号 7） | group-store, message-protocol |
| decision-queue | 待答表：收单校验与退回（含多线事项缺各线范围）、有效性标记、排序、用户回复解析、答复转达（含多线分发） | group-store, message-protocol, review-registry |
| wait-tickets | 等待单：登记、四种理由关单、今天已关闭区、等待时长与对方离线标记 | group-store, message-protocol, relay-reader, decision-queue |
| line-health | 把 agent-relay、spec-guard 与本插件自己的事实组合成各线状态（统一状态词）与需求 8.1 的卡住信号，纯只读；有没有进展看本次已勾数与上次快照（由调用方传入）的对比，加上 agent-relay 的会话活动，不只凭 lastTickAt；history 为 unavailable／shallow 时不做时间类判断；信号 7「反复返工」由本插件的审查结论统计 | relay-reader, spec-guard-reader, review-registry, decision-queue, wait-tickets |
| hub-view | 收件枢纽主视图（需求第 6 节固定顺序与卡片）：「要你去原会话亲自确认」算进「等你决定」并排第一；第一行显示全线停住推送；「详情 / 看等待 / 看已关闭 / 看失效」展开 | review-registry, decision-queue, wait-tickets, line-health |
| query-commands | 只读查询 `/lines`、`/flow`、`/item`；`/flow` 顺着等待链找源头、按需求第 7 节归类并写明谁来做什么 | decision-queue, wait-tickets, line-health |
| map-view | 只读查询 `/map <线>`、`/map <线> 全部`、`/map all`：显示 spec-guard 给的模块表，不改它给的模块状态；「Spec/Plan 评审」列取 spec-guard、「架构审查」列取 review-registry，不共用「审查」一词；外部等待写进模块备注；叠加负责人、跨线归属和收件箱里等你决定的事项；未推送数显示在该线表头；`/map all` 做跨线汇总 | spec-guard-reader, review-registry, decision-queue, wait-tickets |
| stop-hook | 停止钩子，只管协作义务：第一版只在「有别的会话开着等待单在等本会话、本会话又没报阻塞」时拦一次；用户已答复未恢复、未读消息、提到在等却没报阻塞第一版不拦（用户 2026-10-16 确认）；不判断「还有已批准任务」（归 spec-guard，由巡视发现）；Codex 与 Claude 桌面版工作会话 | group-store, wait-tickets, decision-queue |
| patrol | 巡视：定时任务跑信号检测，每次记下各模块已勾数快照供下次对比；自动叫醒已停止的 Claude 会话（需求 13.2 的例外），叫不醒再通知；全线停住时主动推送；进度预警先给负责人、未处理再给用户；收件枢纽超时提醒 | group-store, line-health, relay-reader, spec-guard-reader, decision-queue, hub-view |
| hub-loop | 收件枢纽的主循环命令：`inbox receive` 读一条消息原文并分发给待答表、等待单、审查登记、已恢复处理，输出要退回的说明和要做的事；`inbox reply` 解析用户回复并给出要发的答复；`inbox sent` 记下发送编号；`view` 与四种展开视图的命令；收件枢纽会话自己的约定块（用户 2026-10-16 确认新增） | message-protocol, review-registry, decision-queue, wait-tickets, hub-view |
| onboarding | 一条命令接入与卸载：按角色（开发线、负责人、总协调）写约定块（第 4、5 节规则、负责人模式标签、被挡住必须报阻塞、审查结论写「模块」），用 BEGIN/END 标记包住、重装整块替换；提示在 Claude Code 和 Codex 各信任一次插件自带的钩子；登记名册（含 desktopSession）与审查者；创建巡视定时任务；卸载时删约定块和巡视任务，状态目录保留（第 12 节第 9 项，用户 2026-10-16 确认） | group-store, message-protocol, review-registry, patrol, hub-loop |
| plugin-packaging | 插件打包：Claude Code 插件清单；插件自带 `hooks/hooks.json` 注册 Stop 钩子（两边共用，stop-hook 返工：`--group` 改为可选，不给时按工作目录在所有协作组里找）；斜杠命令 `/lines`、`/flow`、`/item`、`/map`（先调 MCP 工具存原文、再跑命令行）；README 与安装说明（从 onboarding 拆出，用户 2026-10-16 确认） | query-commands, map-view, stop-hook, onboarding |
| answer-handoff-gaps | 答复交接的缺口：已答未恢复的会话收工前拦一次（宿主差异 H17）；答复积压在离线负责人时当轮叫醒并通知，转给负责人时抄送其线上开发线、仅告知（需求第 12 节第 17 项，用户 2026-10-17 确认） | stop-hook, patrol, hub-loop, onboarding |
| e2e-round1-fixes | 修 di-e2e 实测第一轮发现：答复正文写明原消息号、开发线追问自动退回、会话转来的话不当用户答复、巡视停摆报警、在等谁认身份名、卸载不留空规则文件（2026-10-17 实测，spec-guard-monitor 转来） | hub-loop, onboarding, patrol, wait-tickets, message-protocol, answer-handoff-gaps |
| relay-checkpoint-authority | 经收件枢纽中转的体验与直接对话一致：接入时核对 Codex 会话能加载约定块；可选打开「检查点答复即授权」并说明对宿主自动审批的覆盖范围；检查点之间开发线自主修正与重试；多项待答给组合答复；结束行指向事项时提示（2026-10-17 实测后提出，用户确认另开模块） | onboarding, hub-loop, hub-view, wait-tickets, e2e-round1-fixes |
| wait-honesty-and-briefs | 主视图说实话、事项写得清楚：发送方后来又有消息的等待单标为可能已失效，不再引发「全线停住」假警报；没读到 agent-relay 时说没读到而不是查不到；新【等待用户】默认取代本会话之前未答的事项；约定块写明没有已批准的下一步就必须抛事项、要点按事项类型写、邮箱派来的活按来源接；收件枢纽先讲清卡点原因（2026-10-17 实测与审查清单，用户确认拆分） | wait-tickets, line-health, hub-view, decision-queue, onboarding, hub-loop, relay-checkpoint-authority |
| doctor-and-observer | 装对了吗、跑得怎么样、出了问题找谁：doctor 逐项核对约定块、转发脚本、钩子信任、巡视、Codex 加载与依赖插件接口兼容（按 spec-guard、delegate 的 interface.json 读）；只读统计与事件导出、可转发的异常报告；评审状态对照表；hub-setup 一次性权限放行；问题标来源；宿主差异文档与 README 使用注意事项（2026-10-17 实测与审查清单，用户确认拆分） | onboarding, spec-guard-reader, map-view, query-commands, patrol, hub-loop, wait-honesty-and-briefs |
| protocol-contract-v1 | 钉住共用契约 session-protocol v1.0：把契约的样例与期望结果按版本复制进测试、核对指纹，用本插件的解析与生成代码逐份跑通；能力图外部依赖表与 README 写明以契约为准；行为不变（2026-10-18 用户批准契约迁移计划） | message-protocol, hub-loop, decision-queue, doctor-and-observer |
| relay-presence-and-doubt | 接上 agent-relay 0.8 的新事实并修实测观察：按 presence.activity 区分空闲与忙碌、显示送达存疑、合并答复用 alsoAnswers 一次关多条请求、事项被取代时撤回旧请求；没带 agent-relay 状态时不报「全线停住」；各线一行不按可能已失效的单写阻塞、写短名；停止钩子不把已发出的【已恢复】误判为没发（2026-10-17 依赖升级核对与实测，用户确认另开模块） | relay-reader, line-health, hub-view, hub-loop, stop-hook, decision-queue, wait-honesty-and-briefs |
| protocol-contract-v1-3 | 契约升到 session-protocol v1.3：复制 v1.3 样例替换 v1.0 副本，一致性测试跳过本插件不解析的三种新消息（交审、公共变更请求、协调通知），三个过简词各有一份样例能被变异检查抓到；登记契约仓库的接入现状；行为不变（2026-10-18 用户批准） | protocol-contract-v1 |
| protocol-contract-v1-4 | 契约升到 session-protocol v1.4：复制 v1.4 样例替换 v1.3 副本，审查行取值与用户原话首行空白读法有样例保护，计数调为解析 52、生成 6；登记契约仓库的接入现状；行为不变（2026-10-18 用户批准） | protocol-contract-v1-3 |
| p0-field-fixes | 修第 ⑥ 阶段 P0 实测发现的五个问题：取代写邮箱号被退回的约定与退回说明、巡视叫醒空闲且积压 ≥5 分钟的 Claude 会话（含收件枢纽）、巡视任务须先手动运行一次的文档、命令读完输入文件即删除以免巡视卡住；契约升到 session-protocol v1.5（2026-10-18 用户批准） | patrol, decision-queue, hub-view, hub-loop, onboarding, protocol-contract-v1-4 |
| patrol-cadence | 让巡视没按时跑这件事被看见、被正确归因：停摆提示写明权限卡住与宿主没触发两种原因，query stats 统计巡视轮数与最长间隔，P3 指标把宿主没触发单独记录；版本 0.0.13（2026-10-18 用户批准，F-P0-6 对策 E） | p0-field-fixes, query-commands, doctor-and-observer |
| hub-patrol | 定时任务基本不自动触发时巡视不断：收件枢纽被叫醒或用户对它说话时，巡视超过 10 分钟没跑就顺带跑一轮（不叫醒自己、通知改为显示），记录与统计巡视来源；版本 0.0.14（2026-10-18 用户批准，F-P0-6 对策 B） | patrol-cadence, hub-loop, patrol |
| crew-coordinator-seam | 接 module-crew 协调会话的接缝：约定块可写进 CLAUDE.local.md 并核对已被忽略；「并行开发协调会话」标记只在接入时经用户确认写入，带专门一节约定；停止钩子跳过已挂起的当前模块、对协调会话不做没勾完检查 | onboarding, stop-hook, spec-guard-reader |
| hub-cutover-settings | 换收件枢纽时的编号起点：接入收件枢纽可指定起始编号（只在还没编过号时）；核实并写明历史欠回复不进主视图与巡视 | group-store, onboarding |
| transition-compat | 迁移期对还没接入的会话（名册标「旧格式」、只登记不写约定块）用旧编号写法收发：用户答复与多线答复写「#原消息号（hub 编号 N）」、不发答复告知、认它们用邮箱号写的取代与撤回；已退出条目不再收消息；契约钉 v1.7，负责人约定块指向【负责人转交】 | decision-queue, hub-loop, onboarding, protocol-contract-v1-4 |
| crew-line-status | 并行开发线的线状态：协调会话那条线读 module-crew 发布的只读出口（sessions --json，按版本范围）列出各模块状态，按各模块会话的 agent-relay 忙闲判断「干活中」，消除「阻塞」「全线互等」误报，读不到写「模块状态未知」；doctor 读 module-crew 的 interface.json 核对版本、契约与出口能否读到 | relay-reader, line-health, hub-view, doctor-and-observer, crew-coordinator-seam |
| rehearsal-fixes | 联合演练批 1 发现的四项改进：doctor 对只登记条目不报未知；leave 预览列出名下没答的事项和开着的等待单；【撤回】写成自己邮箱号被退回时点明对应事项号；doctor 核对 Claude 与 Codex 两边装的 decision-inbox 是同一版本；仓库忽略 __pycache__ | doctor-and-observer, onboarding, decision-queue, transition-compat |
| rehearsal2-fixes | 联合演练批 2 发现的问题：主视图线状态不准（已退出条目、刚开的模块会话、刚答复的负责人）；巡视卡在权限确认；【等待用户】写法偏松时给提示；join 提醒重开会话、内容不变不重写规则文件 | hub-view, line-health, crew-line-status, patrol, message-protocol, onboarding |
| review-nearby | 审查就近整改中归 decision-inbox 的部分：合批【等待用户】的「待用户决定」逐条显示、没答全就追问；只把无前缀数字当事项号；登记后给发件会话【登记回执】；线状态显示返工轮次；合批先摘要、回「详情」展开；重新 join 输出写入回执；契约升到 session-protocol v2.0（用户决定 41–43） | decision-queue, hub-loop, hub-view, crew-line-status, onboarding, transition-compat, rehearsal2-fixes |
| approval-display | 审批项原样展示（R12，取代 R8；用户决定 46、47）：按契约 v2.1 的「产物」「交审原文」「审查原文」取原文全文（路径＠提交用 git show 只读取出，取不到明说），不摘要不截断；前面补项目、能力图位置（spec-guard /map）、模块、节点、相关决定，后面补「批准会发生什么」和待你决定，推荐放最后；按 reviewCadence 一次一个模块；最终验收把「验收标准 ↔ 证据」放最前（R17）；协作规则段写明只在决策收件箱一处问、收回旧提问（R15） | review-nearby, hub-view, decision-queue, spec-guard-reader, onboarding |
| r20-fixes | 批 2 的 R20 小修（用户决定 51）：收件枢纽规则段写明主视图逐字照命令输出、卡片「回 N X」字母自检（O-hub-option-typo）；规则段写明多线事项适用线不发【已恢复】、结项只认发起方（O-multi-resume）；停止钩子只给 --group 时按目录找会话也排除已退出条目（O-who-left）；O-doctor-none 已在 review-nearby 修好 | approval-display, stop-hook, onboarding, hub-view |
| stall-and-patrol | 停滞与巡视（用户决定 49、50）：模块或线超过约定时间没产出、同一问题报批超过 N 次时主动生成待决事项，选项为挂起并先开可开工模块、换做法、继续等（R14）；join 时把常规授权写进宿主认可的规则文件并实测放行（R16）；巡视会话复用或跑完归档，侧边栏最多留一个（R18）；agent-relay 叫醒连续失败超过约定时间就改用桌面版会话消息叫醒，再不行在决策收件箱提醒去打开并附链接，Codex not-loaded 同样提醒（R19） | r20-fixes, patrol, line-health, onboarding, spec-guard-reader, crew-line-status |
| glossary-rename | 术语表 v1.1 统一用词（用户决定 48）：给用户看的文字、命令说明、协作规则段、README 按术语表换成新名称（收件枢纽→决策收件箱、总协调→跨线协调、负责人→审查者、短名→线名、事项→待决事项、适用会话→适用的线、等待单→等待记录并以 W 前缀显示、【已恢复】显示为已结项、负责人转交→审查者转交、约定块→协作规则段、用户答复→你的答复）；契约消息标签和代码标识符不改；新增术语表帮助页 | stall-and-patrol, hub-view, query-commands, onboarding, plugin-packaging |
| teardown-patrol-session | 卸载命令跟上巡视会话（stall-and-patrol 遗漏）：/decision-inbox:teardown 的说明、步骤和允许的工具按 onboard teardown 输出的后续步骤逐条做，先归档巡视会话、有旧定时任务再删；不再写「巡视定时任务」 | stall-and-patrol, onboarding, plugin-packaging |
| patrol-stop-fixes | 冻结后实测发现的两处小修：卸载前先让巡视会话用 CronDelete 停掉 /loop 循环任务再归档（巡视会话提示词约定收到「停止巡视」就删任务，卸载输出与 /decision-inbox:teardown 先发停止消息、等回复后再归档）；给人看的文字里单独的「身份」改为「邮箱名」，旧称扫描加上这个词 | teardown-patrol-session, glossary-rename, stall-and-patrol |
| glossary-v12 | 按术语表 v1.2（对齐 spec-guard 0.75.0）改给人看的叫法：/map 审查列标记照 spec-guard 写（待批准、改过待重审、标记无效、无标记），术语表副本更新到 v1.2（评审节奏→批准节奏、待审核→待批准、新增「审阅」），旧称扫描补上这些词；只改显示文字，不改契约标签、字段名和行为 | glossary-rename, map-view |
| crew-stall-facts | R14 接上 module-crew 0.4.0 的 sessions --json 停滞事实：模块协调那条线逐个模块看，未合入、未挂起、没在等你的模块，按 now −（commits.last.at，没有则 startedAt）超过停滞时长，或同一节点 asks.ats 在约定时间内报批超过 N 次，就让模块协调就这个模块抛【等待用户】（三个选项同 R14）；字段缺失（0.3.x）照旧，只给事实的字段由本插件定阈值 | stall-and-patrol, crew-line-status |
| doctor-skip-teardown | doctor 跳过已卸载的协作组的巡视检查：决策收件箱已退出（onboard teardown 记了 left）的组，不再报「巡视 N 分钟没跑」，改为一行说明已卸载、状态目录保留；协作规则段等其他检查不变 | doctor-and-observer, teardown-patrol-session |
| scope-authority-defaults | R21 授权按范围给（DI-1、DI-2 改法、DI-3）：接入时「检查点答复即授权」默认打开、可关，预览写明授权什么不授权什么（只放行 Plan 列出的依赖或允许范围、只走官方源、项目已有依赖规则照旧）；Claude 权限不再固定先问 npm install、pip install，改为放行按锁文件或清单装（npm ci、无参数 npm install、pip install -r），加新包仍先问；开发线规则段改为 Plan 没列的依赖才问、只问一次，已批范围内的小步骤不送审；推送、reset --hard、rm -rf 照旧先问 | onboarding, relay-checkpoint-authority, stall-and-patrol |
| go-to-session | R21 去会话操作（DI-7、DI-8）：契约钉到 session-protocol v2.2；收到【等待用户】「类型：去会话操作」时放进主视图最上面单独一栏，写清去哪个会话（Claude 由 local_ 编号拼链接，Codex 写邮箱名与 worktree 并提示在 Codex 应用里打开）、被拦的操作、点哪个按钮、为什么批不了，关联事项写「你在 #N 已同意，只差宿主这一下」；不给回复选项，用户回 A 当已读不转发；发起方发【已恢复】自动结项，30 分钟没结项主视图再提醒一次、不新建事项；Claude 线按 agent-relay 的 waiting-approval 兜底提醒；开发线规则段写明碰到宿主确认立刻按这个类型上报；接入预览先告诉用户会出现这类提醒 | approval-display, hub-view, patrol, scope-authority-defaults |
| host-permission-check | R21 宿主权限对照（DI-4）：接入预览与 doctor 只读宿主实际权限（Codex：沙箱模式、能否联网、项目是否受信、项目里的 .codex/config.toml；Claude：放行与先问的安装规则），与当前模块已批 Plan 的「需要的外部条件」对照；对不上就提醒并给两个选项：A 确切改法由用户自己改（Codex 在受信项目的 .codex/config.toml 写 [sandbox_workspace_write] network_access = true，不写 ~/.codex/config.toml），B 到时去开发会话点允许（按去会话操作提醒）；不改任何宿主配置 | onboarding, doctor-and-observer, scope-authority-defaults, go-to-session |
| proxied-session-note | 代开会话提醒（R21 DI-2 风险，接入协调人转来、用户 2026-10-19 同意按建议处理）：接入预览加一行说明先问规则只对用户亲手开的会话有效，别的会话代开的会话里可能不弹确认；开发线、审查者、跨线协调规则段加一句：被代开时碰到不可逆操作（推送、reset --hard、rm -rf、加新包）不直接执行，按去会话操作上报；只改文字，不做代开识别、不改 ask 为 deny | scope-authority-defaults, go-to-session |
| loop-detection | R21 打转判断与展示（DI-5、DI-6）：每次问用户的事项抬头带项目、模块、第 n 次问你（基准 = Spec + Plan + gates.total，超出第 k 次）、你答了 j 次进度没动、开工时长（扣掉等用户与等别的线）、进度 a/b；同模块历史折叠成一行，主视图每个在做的模块一行；用户答了 2 次进度没动，或出手累计满 12 小时没进展（阈值可配）判为打转，在该模块下一次来问的事项顶上加提示与三个选项（挂起先开可开工模块、换方案、继续等 12 小时内不再提示），主视图挂一行停滞提醒；去掉停滞判断里跳过等待用户与正在审查的模块；去会话操作不计入问询次数与基准 | spec-guard-reader, hub-view, crew-stall-facts, go-to-session |
| permission-closeout | R21 收尾（用户决定 62、64、66、67 与代开会话查证）：Claude 线接入写的放行规则照 module-crew 0.5.1 放宽装包（含加新包：npm install *、pnpm add *、yarn add *、uv add * 等，裸 pip install 不写规则交宿主默认确认），全局安装（-g、--global 任意位置、yarn global、uv --system）写禁止，推送、reset --hard、rm -rf 保持先问；有 dev 脚本的项目接入时放行开发服务命令；规则段与检查点授权去掉「Plan 没列的依赖问一次」，改为加新包直接做、最终验收列出新增依赖；宿主权限对照（DI-4）不再读 Plan「需要的外部条件」，改为项目有依赖清单而宿主不能联网时提醒，并对有 dev 脚本的前端项目查开发服务命令是否放行、Codex 能否下载浏览器；改正 proxied-session-note 与 E3 记录里「代开会话先问规则不弹」的说法（会话记录显示弹了、被点掉了） | onboarding, doctor-and-observer, scope-authority-defaults, host-permission-check, proxied-session-note |
| join-deny-label | 修 0.0.28 接入预览与写入回执的标签：禁止规则（全局安装、管道到 shell 共 16 条）被标成「先问」，实际写进 deny；标签按规则种类写放行／先问／禁止，加测试保证预览与回执的标签和写入的数组一致 | permission-closeout |
| decision-cards | 待决事项按定稿模板的 7 类出卡片（只给结论、要回答才给复制块、原文默认不展开），并修答复转达与巡视的阶段丙缺陷（I-1～I-13） | approval-display, hub-loop, go-to-session, loop-detection |
| wait-closed-item | 等待记录所等的待决事项已转达或结项时不再误报（I-11 收件箱这一侧）：等的对象写成「决策收件箱（邮箱名）」也认作等用户，答复发出即自动关掉；等待内容里写的 #N 已结项时标「可能已失效」、不再算全线停住（模块协调的也算） | wait-tickets, decision-cards |
| stage-c-fixes | 阶段丙补派（R22）：事项没带模块时按交审编号或发出会话名反查模块，判不出的以后重查（DI-10）；巡视停了由独立于收件箱和巡视会话的本机定时检查主动提醒用户（DI-11）；模块停滞计时从开工通知或最近一次答复送达起算，扣掉等用户、等批准（含答复没发出去的那段）、等其他线（DI-12） | loop-detection, crew-stall-facts, stall-and-patrol, decision-cards |
| launcher-own-code | 启动脚本 bin/decision-inbox 只加载自己插件目录里的 decision_inbox，不受调用者当前目录里同名包影响；各命令仍按调用者的当前目录读项目 | plugin-packaging |
| patrol-watch-runtime | 巡视提醒的 launchd 任务改跑复制到 ~/.decision-inbox 下的运行副本、用 3.10 及以上的 python，不落在 macOS 受保护目录；doctor 按上次退出码和日志判断它是否真在工作（DI-11 补修） | stage-c-fixes, plugin-packaging |
| my-waits | 只读查询 /waits：当前会话「我在等什么」（我开的等待记录、我抛出还没结的待决事项）与「谁在等我」（别人开的、等我的等待记录），各项带等了多久、对方离线、可能已失效标记（需求 3.3.5 查询，第二版） | wait-tickets, decision-queue, query-commands |

Build order: group-store → relay-reader → message-protocol → review-registry → decision-queue → wait-tickets → spec-guard-reader → line-health → hub-view → query-commands → map-view → stop-hook → patrol → hub-loop → onboarding → plugin-packaging → answer-handoff-gaps → e2e-round1-fixes → relay-checkpoint-authority → wait-honesty-and-briefs → doctor-and-observer → protocol-contract-v1 → relay-presence-and-doubt → protocol-contract-v1-3 → protocol-contract-v1-4 → p0-field-fixes → patrol-cadence → hub-patrol → crew-coordinator-seam → hub-cutover-settings → transition-compat → crew-line-status → rehearsal-fixes → rehearsal2-fixes → review-nearby → approval-display → r20-fixes → stall-and-patrol → glossary-rename → teardown-patrol-session → patrol-stop-fixes → glossary-v12 → crew-stall-facts → doctor-skip-teardown → scope-authority-defaults → go-to-session → host-permission-check → proxied-session-note → loop-detection → permission-closeout → join-deny-label → decision-cards → wait-closed-item → stage-c-fixes → launcher-own-code → patrol-watch-runtime → my-waits

<!-- Spec Guard 按严格串行推进。为兼容上游格式，逗号分组会按左到右顺序展开为单模块步骤，不代表并行授权。 -->

## 外部依赖（需求第 13 节）

能力图的「Depends on」列只填本插件的模块 id；用到的其他组件接口写在这里。缺的接口记为向对应组件提的需求，不在本插件里补。

| 模块 | 组件 | 接口 | 状态 |
|---|---|---|---|
| relay-reader | agent-relay | `bridge_agents`、`bridge_outbox`（MCP，经会话转交原文） | 已有（0.6.10） |
| relay-reader | agent-relay | 只读命令行入口（`agents`、`outbox`，后续可能加 `wake-status`） | 已提需求，用户已转交 |
| relay-reader | agent-relay | `bridge_wake_status`、`bridge_thread`（供 `/item`） | 已有；`bridge_thread` 带正文，纳入前先问用户 |
| spec-guard-reader | spec-guard | `/spec-guard:map --json`（map-view；`hooks/map_view.py --project <路径> --json`） | 已发布（0.62.0，契约定稿，见 spec-guard 仓库 `spec/map-view.md` 的 Contract） |
| spec-guard-reader | spec-guard | 状态查询：`lastTickAt`、`firstTickAt`、`tickCommits`、`suspendedAt`、顶层 `history`（stall-signals） | 已发布（0.63.0，见 spec-guard 仓库 `spec/stall-signals.md` 的 Contract；审查轮数已去掉；`tickCommits` 小于 2 的模块算不出平均间隔） |
| patrol | Claude 桌面版 | 会话消息工具（叫醒已停止的 Claude 会话） | 已验证可用；需求 13.2 的例外 |
| patrol | Claude 桌面版 | 定时任务 | 已验证可用；周期 5 分钟实测稳定、延迟约 38 秒；补跑未验证，设计上不依赖（2026-10-16） |
| protocol-contract-v1 | session-protocol（本地契约仓库 `~/Documents/haigeerlab/session-protocol`） | 契约样例与期望结果，副本在 `tests/fixtures/session-protocol/v2.1/`，由 `tests/test_contract.py` 跑通，跳过本插件不解析的【交审】【公共变更请求】【协调通知】【负责人转交】与 `user-reply/relay-*`；协议改动先改契约再改实现（v1.0→v1.3→v1.4→v1.5→v1.7 见各模块；review-nearby 2026-10-19 升到 v2.0.1，approval-display 升到 v2.1） | 已钉住 v2.1（契约提交 c251e94） |
| crew-line-status、review-nearby | module-crew | `sessions --json` 每行选填 `review`（`state` 为 reviewing／rework，`round` 为返工通知条数），schemaVersion 仍为 1 | module-crew 0.3.0 提供（2026-10-19 来信定稿）；旧版本没有这个字段，照旧显示 |
| crew-stall-facts | module-crew | `sessions --json` 每行选填 `startedAt`、`commits`（`ahead`、`last`、`error`）、`asks`（含 `ats`）、`returns`、`waitUser`，schemaVersion 仍为 1；`commits.last` 是开工以来 HEAD 第一父链上、不在集成分支第一父链上的最新提交，合入后仍有值 | module-crew 0.4.0 提供（2026-10-19 冻结知会，定义见其 `spec/crew-stall-signals.md`）；旧版本没有这些字段，不做按模块判断 |
| loop-detection | spec-guard | `/map --json` 每个模块 `gates: {"total", "done"}`（todo 里 gate 检查点总数与已勾数，没有 todo 为 null），interface 1.3 | spec-guard 0.77.0 提供（tag v0.77.0 → 3d02b7f）；旧版本没有这个键，基准写「未知」 |
| loop-detection | module-crew | `sessions --json` 每行选填 `answers: [{ref, at, commitsAfter, ticksAfter}]`，ref 与 `asks.refs`、`waitUser.ref` 同一套 C 编号；worktree 读不到时后两项为 null | module-crew 0.5.0 提供（冻结 v0.5.0 → f28e50f，定义见其 `spec/crew-stall-signals.md`）；旧版本没有，按模块的「进度没动」写「读不到」、不判 |
| stop-hook | Codex、Claude 桌面版 | `Stop` 钩子 | Codex 已验证；Claude 桌面版未验证（第 12 节第 5 项） |

## 范围对照（需求 11.1 → 模块）

| 需求 11.1 条目 | 落在 |
|---|---|
| 待答表与答复转达，含多线事项（缺各线范围在抛出时退回） | decision-queue（校验规则在 message-protocol） |
| 等待单与关单（四种理由） | wait-tickets |
| 停止钩子：两侧、开发线收工前自检、被挡住必须报阻塞 | stop-hook |
| 巡视：按信号检测、自动叫醒 Claude 会话、失败再通知、预警先负责人再用户 | line-health（检测）＋ patrol（处理与升级） |
| 审查者登记与审查状态行 | review-registry（解析在 message-protocol） |
| 用户的 4 个查询 `/lines`、`/map`、`/flow`、`/item` | query-commands、map-view（单项目模块表由 spec-guard 的 `map --json` 提供，见下方「分工调整」） |
| 收件枢纽显示格式（第 6 节） | hub-view |
| 收件枢纽的超时提醒 | wait-tickets（标记）＋ patrol（主动提醒） |
| 总协调收各线阻塞报告 | message-protocol（报告格式）＋ onboarding（约定块规则）＋ line-health（读入状态） |
| 负责人模式标签 | onboarding（约定块规则） |
| 一条命令接入 | onboarding |
| 把实验中【已有】的规则固化进约定块 | onboarding |

需求 11.2（第二版）与 11.3（不做）的条目不进本图。

## 分工调整（2026-10-16，用户确认）

单个项目的模块表与卡点信号改由 spec-guard 新增的 `/spec-guard:map`（`--json`）提供，decision-inbox 只读调用，不自己解析能力图和 todo，全系统只有一份解析逻辑。decision-inbox 负责跨线汇总（`/map all`）、每条线的负责人与跨线归属、外部等待（等某人交付）、收件箱、会话空闲或离线、定时巡检和唤醒。

- 受影响的模块：spec-guard-reader、map-view 的职责；line-health 的信号 3、6、8 改用 spec-guard 的数据；信号 7「反复返工」是架构审查在同一节点来回的轮数，审查结论走本插件的消息约定和审查者登记，由 review-registry 统计，不找 spec-guard 要。模块 id 不变。
- 2026-10-16 按需求第 13 节再调整（用户确认）：stop-hook 只管协作义务、去掉对 spec-guard-reader 的依赖；`/flow` 加源头诊断；hub-view 把「要你去原会话亲自确认」算进「等你决定」；patrol 加全线停住推送；新增「外部依赖」一节。
- 开发顺序：spec-guard-reader 挪到 wait-tickets 之后，给 spec-guard 定稿 JSON 留出时间。
- 在 spec-guard 的 JSON 契约定稿前，不写任何解析能力图或 todo 的代码。
- 2026-10-16 按需求第 7 节「按 spec-guard 实际接口调整」五条再修订（用户确认）：spec-guard-reader 改正命令名并按安装记录找脚本；map-view 分「Spec/Plan 评审」「架构审查」两列、不改模块状态、未推送显示在线表头；line-health 按已勾数快照对比判断进展；patrol 记快照。group-store 不受影响（新领域即可）。
- 2026-10-16 按 spec-guard-monitor 的核对意见再修订（用户确认）：信号 7 改由 review-registry 统计，line-health 增加对 review-registry 的依赖；map-view 明确叠加审查列；给 spec-guard 的状态查询需求去掉「审查轮数」。

---

## 评审记录

- [x] 模块边界确认（砍掉或替换一个模块，不需要重写其他模块的需求）
- [x] 依赖方向单向无环（互相依赖 = 它们本来就是一个模块）
- [x] module id 已定稿（kebab-case，之后绝不改名 —— 同一个 id 同时是
      `spec/<id>.md`、`tasks/<id>/`、`.agent/state.json` 的 `activeModule` 和 Proposal 中的模块名，
      已发布的 Proposal 改不动）
- [x] 构建顺序符合依赖拓扑

评审人：用户（对话中回复「批准」）
日期：2026-10-16
