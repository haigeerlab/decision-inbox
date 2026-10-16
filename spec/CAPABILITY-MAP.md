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
| relay-reader | 只读适配 agent-relay：邮箱消息、投递与已读、presence、waiting，转成统一的只读数据 | — |
| spec-guard-reader | 只读各线仓库的 spec-guard 产物：能力图、依赖、模块状态、todo 勾选数；未装 spec-guard 时如实降级为「无能力图」 | — |
| message-protocol | 第 4 节消息约定的解析与校验：消息类型、结束写法、选项写法、多线事项字段、架构审查状态行、「阻塞：等谁交付」报告 | — |
| review-registry | 审查者登记（哪个会话有审查者、审哪类节点、经用户批准才增改）与审查状态行的显示规则 | group-store, message-protocol |
| decision-queue | 待答表：收单校验与退回（含多线事项缺各线范围）、有效性标记、排序、用户回复解析、答复转达（含多线分发） | group-store, message-protocol, review-registry |
| wait-tickets | 等待单：登记、四种理由关单、今天已关闭区、等待时长与对方离线标记 | group-store, message-protocol, relay-reader, decision-queue |
| line-health | 各线状态判定（统一状态词）与需求 8.1 的 10 个卡住信号检测，纯只读 | relay-reader, spec-guard-reader, decision-queue, wait-tickets |
| hub-view | 收件枢纽主视图（需求第 6 节固定顺序与卡片）及「详情 / 看等待 / 看已关闭 / 看失效」展开 | review-registry, decision-queue, wait-tickets, line-health |
| query-commands | 只读查询 `/lines`、`/flow`、`/item` | decision-queue, wait-tickets, line-health |
| map-view | 只读查询 `/map <线>`、`/map all`、`/map <线> 全部`：状态词表、审查列、按依赖链全算「挡住 N 个」、折叠规则 | spec-guard-reader, review-registry, decision-queue, line-health |
| stop-hook | 停止钩子：交付方和等待方两侧拦截、开发线收工前自检、被挡住必须报「阻塞：等谁交付」；Codex 与 Claude 桌面版工作会话 | message-protocol, relay-reader, spec-guard-reader, wait-tickets |
| patrol | 巡视：定时任务跑信号检测，自动叫醒 Claude 会话，叫不醒再通知；进度预警先给负责人、未处理再给用户；收件枢纽超时提醒 | group-store, line-health |
| onboarding | 一条命令接入与卸载：写约定块（第 4、5 节规则、负责人模式标签、阻塞报告），装停止钩子并提示 Codex 信任，录入审查者登记 | group-store, message-protocol, review-registry, stop-hook |

Build order: group-store → relay-reader → spec-guard-reader → message-protocol → review-registry → decision-queue → wait-tickets → line-health → hub-view → query-commands → map-view → stop-hook → patrol → onboarding

<!-- Spec Guard 按严格串行推进。为兼容上游格式，逗号分组会按左到右顺序展开为单模块步骤，不代表并行授权。 -->

## 范围对照（需求 11.1 → 模块）

| 需求 11.1 条目 | 落在 |
|---|---|
| 待答表与答复转达，含多线事项（缺各线范围在抛出时退回） | decision-queue（校验规则在 message-protocol） |
| 等待单与关单（四种理由） | wait-tickets |
| 停止钩子：两侧、开发线收工前自检、被挡住必须报阻塞 | stop-hook |
| 巡视：按信号检测、自动叫醒 Claude 会话、失败再通知、预警先负责人再用户 | line-health（检测）＋ patrol（处理与升级） |
| 审查者登记与审查状态行 | review-registry（解析在 message-protocol） |
| 用户的 4 个查询 `/lines`、`/map`、`/flow`、`/item` | query-commands、map-view |
| 收件枢纽显示格式（第 6 节） | hub-view |
| 收件枢纽的超时提醒 | wait-tickets（标记）＋ patrol（主动提醒） |
| 总协调收各线阻塞报告 | message-protocol（报告格式）＋ onboarding（约定块规则）＋ line-health（读入状态） |
| 负责人模式标签 | onboarding（约定块规则） |
| 一条命令接入 | onboarding |
| 把实验中【已有】的规则固化进约定块 | onboarding |

需求 11.2（第二版）与 11.3（不做）的条目不进本图。

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
