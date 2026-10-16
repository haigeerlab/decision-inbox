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

Build order: group-store → relay-reader → message-protocol → review-registry → decision-queue → wait-tickets → spec-guard-reader → line-health → hub-view → query-commands → map-view → stop-hook → patrol → hub-loop → onboarding → plugin-packaging

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
