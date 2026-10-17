<!-- spec-guard: review pending -->
# Spec: doctor-and-observer

> 能力图模块 `doctor-and-observer`（待用 add-module 插入，排在 wait-honesty-and-briefs 之后）。来源：`docs/requirements-record.md` 第 13 节「后续模块待办」与 13.5「依赖插件升级核对」；spec-guard-monitor 转来的审查清单 A4、A5、A6、A10、C、C1、D、E（经用户同意转来）。用户在本会话同意按「模块乙」拆分；agent-relay 0.8 的新字段（空闲／忙碌、送达存疑、合并答复）另开模块丙，不在本模块。

## 目标

让使用者和观察者不翻代码、不读状态文件，就能回答三个问题：

- **装对了吗**：各会话的约定块是不是当前版本、转发脚本指向哪里、钩子有没有被信任、巡视最近一次什么时候跑、Codex 会话能不能加载约定块、依赖插件的版本和接口是否兼容。实测中这些都靠人工翻文件查过（F11 转发脚本被改回旧版、约定块是旧版、巡视停在权限确认上）。
- **跑得怎么样**：多少事项绕过了收件枢纽、从抛出到答复到恢复用了多久、多少被取代或退回、有多少等待单挂着过期。现在只能逐条读事件日志。
- **出了问题找谁**：问题出在宿主、依赖插件还是本插件，提示里写明来源；根源在依赖插件的，交给那个插件的负责人修，本插件不打补丁绕过。

## 关键决策与取舍（请重点审）

1. **`decision-inbox doctor [--group <组>] [--json]`**（新命令，只读）。逐项输出「正常／异常／未知」、证据和修法；每项标来源（本插件／宿主／依赖插件名）。
   - 约定块：对名册里每个会话的工作目录，读出 BEGIN/END 之间的块，和当前代码按该角色生成的块逐字比较；不同就报「约定块不是当前版本，重跑接入命令」。约定块里不加版本号。
   - 转发脚本：`~/.decision-inbox/bin/decision-inbox` 指向哪个插件目录、那里的插件版本；和本次运行的代码不是同一个目录时报异常，并提示 F11（已装插件的 SessionStart 钩子会把它改回已装版本）。
   - 钩子信任：Claude 侧看插件是否已启用；Codex 侧看 `~/.codex/config.toml` 的钩子信任记录。读不到报「未知」。
   - 巡视：协作组记录的 `lastRunAt` 距今多久；超过 `PATROL_STALE_MINUTES`（15 分钟）报异常，提示多半停在权限确认上。
   - Codex 加载约定块：复用 relay-checkpoint-authority 的 `codex_loads` 判定。
   - 依赖插件：见第 2 条。
2. **按依赖插件发布的接口说明读数据**（返工 spec-guard-reader）。
   - spec-guard：从插件根目录读 `interface.json`，接口版本在 `>=1.0,<2.0` 内才用；map-view 的命令取 `mapView.command`（相对插件根目录，`<project-root>` 换成各线仓库），`mapView.schemaVersion` 必须是 1。插件根目录仍从 `installed_plugins.json` 找。`interface.json` 不存在或读不懂时，用现在写死的入口，doctor 报「接口说明读不到（spec-guard 可能早于 0.66.0）」，不报「没装」；主版本不在范围内时，不读能力图，各线写「spec-guard 接口版本不兼容（x.y）」。
   - delegate：读 `interface.json`，只用来让 doctor 报出版本和是否兼容，以及审查命令名（`review.command`）。是否「能用」以 `/delegate:doctor` 为准，doctor 只提示去跑它，不代跑。文件不存在（0.5.2 及更早）报「读不到接口」，不报没装。
   - agent-relay：doctor 报插件版本、运行时版本和接口版本（读得到时），按接口文档解释 `presence`／`lastSeen`：`running` 不代表信箱连接正常，`lastSeen` 不是心跳。
3. **审查状态对照表**（返工 map-view，由本插件维护）：spec-guard 的 `review` 取值显示为：approved→通过，pending→待审，revised→改后待复审，none→不适用，invalid→异常。`externalReview` 为 recorded 时，「Spec/Plan 评审」列后加「（有参考意见）」，declined 不显示；不解析参考意见的正文和条数，要看详情去 spec 或 todo 的「外部审查意见」小节。
4. **只读统计与导出**（新子命令）。
   - `query stats [--group] [--since <日期>]`：绕过收件枢纽结束的事项数（开发线自己写了结束行却没有用户答复记录）、抛出→答复、答复→恢复的耗时（中位数和最长）、被取代／自动取代／退回／拒收转述的次数、现在挂着的可能已失效等待单数。
   - `query events --json [--since]`：事件日志原样导出，字段固定为 `at`、`kind`、`actor`、`item`、`data`，格式写进 README。
   - `doctor --report`：可以直接转发给插件负责人的异常报告：现象、证据（事件编号、邮箱号）、各组件版本、来源判定。不含消息正文。
5. **一次性权限放行**（返工 onboarding 的 hub-setup，A4、A5）。hub-setup 最后列出收件枢纽和巡视要用到的命令（`decision-inbox` 各子命令）和 agent-relay 工具，生成一段要加进收件枢纽目录 `.claude/settings.local.json` 的 `permissions.allow`，先预览差异；用户明确确认后才写，只写这一个文件，不动全局设置和其他项目。不确认就只打印，不写。
6. **问题标来源**（C1）：主视图、doctor、巡视通知里，根源在依赖插件或宿主的提示，句末加「（来源：agent-relay）」「（来源：Claude 桌面版）」这类标注；本插件不为依赖插件的缺陷加绕过逻辑，需求记录里记一条转给对方负责人。
7. **宿主差异文档**（`docs/host-differences.md`）：修订 H10（守卫信任会话加载的 AGENTS.md 和用户说过的「按收到的任务做」）；新增 H18（Codex 会话目录决定加载哪份 AGENTS.md）、H19（Claude 自动模式会拦部分命令，`--relayed-from` 被拦过两次）、H20（Claude 定时任务不继承创建者会话的权限，遇到新工具就停）；H3 改为「agent-relay 0.7.1 起有引导式恢复，完全自动不可行」。F11 只写进开发说明，不进使用文档。
8. **README「使用注意事项」**：一张表，每行写现象、原因与来源（宿主／依赖插件／本插件设计）、使用者怎么做、出了问题找谁。
9. **实测补缺口**（A10，先问用户）：S1 负责人离线时自动叫醒；S3 Codex 桌面版的停止钩子。

## 范围

做：`decision_inbox/__main__.py`（doctor、query stats、query events）、新文件 `decision_inbox/doctor.py`、`specguard.py`（按接口说明读）、`mapview.py`（审查对照表）、`onboard.py`（权限放行）、`query.py`、`health.py`／`patrol.py`／`view.py`（来源标注）、`docs/host-differences.md`、`README.md`、两份 `plugin.json`（升到 0.0.7），以及对应测试。

不做：

- agent-relay 0.8 的新字段（`presence.activity`、送达存疑、`alsoAnswers`／`withdraws`）：模块丙。
- 代跑 `/delegate:doctor` 或任何依赖插件的命令：doctor 只读文件、只提示。
- 改用户的全局 Claude 设置或 Codex 配置：只在用户确认后写收件枢纽目录下的一个本地设置文件。
- 修依赖插件的问题：只标来源、记需求。

## 接口约定

```python
doctor.run(groups, now) -> list[Check]       # Check: name, state("ok"|"bad"|"unknown"), source, evidence, fix
doctor.report(checks, versions) -> str       # 可转发的异常报告
specguard.locate(project) -> Located | Missing   # Located 多 interface: str | None、command: list[str]
specguard.interface_status() -> ("ok"|"absent"|"unreadable"|"incompatible", detail)
query.stats(g, since) -> Stats
query.events(g, since) -> list[dict]          # 字段 at, kind, actor, item, data
onboard.permission_preview(hub_dir) -> (path, diff)   # 只预览；写入要 --confirm
```

## 测试策略

- 单元测试：
  - doctor：约定块一致／不一致／缺失；转发脚本指向别处；巡视超时；三个依赖插件各自的接口说明存在、缺失、读不懂、主版本不兼容。
  - spec-guard 接口：命令取自 `interface.json`；文件缺失时退回现在的入口；主版本 2 时不读能力图且写明原因。
  - 审查对照表五个取值和 `externalReview` 三个取值的显示。
  - stats：用固定事件日志算出各项数字；events 导出的字段和顺序。
  - 权限放行：不带 `--confirm` 不写文件；带了只改一个文件；已有的 allow 保留不重复。
  - 来源标注：依赖插件和宿主来源的提示带标注。
- 命令行实跑：在 scratchpad 建临时协作组，人为制造旧约定块、转发脚本指向别处、巡视超时，看 doctor 输出。
- 实测（先问用户）：S1、S3。

## 边界

- 始终：doctor 和统计只读；读不到就说读不到，不猜。
- 先问：写权限放行文件；实测。
- 绝不：改全局设置或其他项目的设置；替依赖插件绕过缺陷；把消息正文放进报告。

## 验收标准

1. `doctor` 能逐项报出约定块、转发脚本、钩子信任、巡视、Codex 加载、三个依赖插件的状态，每项有来源和修法；`--json` 字段固定；`--report` 不含消息正文。
2. 读 spec-guard 按 `interface.json` 选命令，缺失、读不懂、不兼容三种情况的行为和措辞不同，都不说成「没装」。
3. 读 delegate、agent-relay 的接口说明只用于报版本和兼容性，读不到时报「读不到接口」。
4. map-view 按对照表显示评审状态，有参考意见时标出。
5. `query stats`、`query events --json` 输出与固定事件日志算出的结果一致。
6. hub-setup 预览权限放行，确认后只写收件枢纽目录的本地设置文件。
7. 依赖插件或宿主来源的提示带来源标注。
8. 宿主差异文档与 README 使用注意事项按第 7、8 条更新。
9. 两份清单 0.0.7；原有测试全部通过。
10. 实测：S1、S3 的结果写进本规格。

## 假设

1. spec-guard 的 `interface.json` 在插件根目录，0.66.0 起提供，接口 1.0；`mapView.command` 是相对插件根目录的数组。（已核对 0.67.0）
2. delegate 0.5.3 起在插件目录提供 `interface.json`，接口 1.0。（已核对 Claude 侧 0.5.3；Codex 侧缓存仍是 0.5.0）
3. Codex 的钩子信任记录在 `~/.codex/config.toml`；字段名以实读为准，读不到时报「未知」。
4. 巡视每轮在协作组状态里写 `lastRunAt`（patrol 已在写）。

## 未决问题

1. 权限放行写收件枢纽目录的 `.claude/settings.local.json`，还是只打印让用户自己贴？推荐写本地文件（确认后），理由是实测里用户被权限确认打断了三次，而这个文件只影响收件枢纽目录。
2. `query stats` 里「绕过收件枢纽」怎么判：推荐按「开发线写了结束行，指向的事项没有用户答复记录」算；另一种是按「agent-relay 里有开发线发给负责人的请求却没进收件枢纽」算，要读别人的邮箱，不推荐。

## 文档建议

README 加「使用注意事项」表、`doctor` 与 `query stats`／`query events` 的用法；`docs/host-differences.md` 按第 7 条修订。
