<!-- spec-guard: review approved -->
# Implementation Plan: doctor-and-observer

> 依据：`spec/doctor-and-observer.md`（已批准）。任务清单：`tasks/doctor-and-observer/todo.md`。

## Overview

先把「读依赖插件」改成按接口说明读（spec-guard、delegate、agent-relay），再在此之上做 doctor；然后是只读统计、权限放行、来源标注，最后是文档、版本和实测。每个任务先写失败的测试，再实现到全绿，单独提交并推送。

## Architecture Decisions

- **接口说明读取放在新文件 `decision_inbox/deps.py`**：一个通用函数 `read_interface(plugin_root, accept) -> Interface`，返回 `state`（ok／absent／unreadable／incompatible）、接口版本、原始字段。三个插件的版本范围：spec-guard 与 delegate `>=1.0,<2.0`，agent-relay 主版本 2（本机实读为 2.5；本插件用到的 `bridge_agents`、`bridge_outbox` 字段在 2.x 内只增不改）。插件根目录都从 `installed_plugins.json` 找，沿用 `specguard.locate` 的选择规则（本项目安装优先，其次 user）。
- **spec-guard**：`specguard.locate` 改为先读 `interface.json`：ok 时命令取 `mapView.command`，把 `<project-root>` 换成仓库路径、相对路径按插件根目录解析；absent／unreadable 时退回现在的 `hooks/map_view.py`；incompatible 时返回 `Missing("spec-guard 接口版本不兼容（x.y）")`，各线照现有「无能力图」路径显示原因。
- **doctor**：新文件 `decision_inbox/doctor.py`，每项检查一个小函数，返回 `Check(name, state, source, evidence, fix)`；`run()` 汇总，`render()` 出文字，`--json` 出固定字段，`report()` 出可转发报告（只含检查结果、版本、事件编号，不含消息正文）。约定块比较复用 `onboard` 生成约定块的函数；Codex 加载复用 `onboard.codex_loads`；巡视用协作组状态里的 `lastRunAt` 和 `hub.PATROL_STALE_MINUTES`；Codex 钩子信任读 `~/.codex/config.toml` 的 `[hooks.state."decision-inbox@…"]` 是否有 `trusted_hash` 且 `enabled`，读不到报「未知」。
- **审查对照表**：`mapview.py` 加一个常量表，五个 `review` 取值和 `externalReview` 的显示都走这张表。
- **统计**：`query.py` 加 `stats()` 与 `events()`，只读事件日志与待答表、等待单；「绕过收件枢纽」按规格定的口径。
- **权限放行**：`onboard.permission_preview(hub_dir)` 计算要加的 `permissions.allow` 条目（本插件命令 `Bash(decision-inbox:*)` 一类，加上收件枢纽和巡视用到的 `mcp__agent-relay__bridge_*` 工具），读出现有文件后合并、去重、给出差异；`onboard hub ... --allow --confirm` 才写；只写 `<收件枢纽目录>/.claude/settings.local.json`。
- **来源标注**：在 `health.py`、`patrol.py`、`view.py` 里已经能判定来自依赖插件或宿主的几处提示（读不到 agent-relay、spec-guard 不兼容、巡视停在权限确认、Codex 没加载）末尾加「（来源：X）」，用一个小函数统一格式。
- **版本**：两份 `plugin.json` 升到 0.0.7。

## 影响面

- 新增：`decision_inbox/deps.py`、`decision_inbox/doctor.py`、对应测试。
- 修改：`specguard.py`、`mapview.py`、`query.py`、`onboard.py`、`health.py`、`patrol.py`、`view.py`、`__main__.py`、`docs/host-differences.md`、`README.md`、两份 `plugin.json`。
- 用户可见界面：doctor 输出、`query stats` 输出、map-view 的评审列、hub-setup 的权限预览、几处提示的来源标注。都由测试逐字核对。
- 风险最大的一步：Task 1 改了读 spec-guard 的入口，影响各线状态和 map-view；退回路径保证 `interface.json` 读不到时行为不变，由现有 map-view 与 line-health 测试兜住。

## Task List

- [ ] Task 1：deps.py 与 spec-guard 按接口说明读（Spec 验收 2）
- [ ] Task 2：delegate、agent-relay 接口读取与审查对照表（Spec 验收 3、4）
- [ ] Task 3：doctor 命令、`--json`、`--report`（Spec 验收 1）

### Checkpoint 1（report）

- [ ] 全部测试全绿

- [ ] Task 4：`query stats` 与 `query events --json`（Spec 验收 5）
- [ ] Task 5：hub-setup 一次性权限放行（Spec 验收 6）
- [ ] Task 6：来源标注（Spec 验收 7）

### Checkpoint 2（report）

- [ ] 全部测试全绿；scratchpad 临时协作组命令行跑 doctor（旧约定块、转发脚本指向别处、巡视超时）、stats、权限预览，记下输出；推送本分支

- [ ] Task 7：宿主差异文档、README 使用注意事项、版本 0.0.7（Spec 验收 8、9）
- [ ] Task 8：实测 S1、S3（Spec 验收 10）。先问用户

### Checkpoint 3（gate）：模块最终验收

- [ ] 全部测试全绿；10 条验收标准逐条有测试或实测记录；列出实际改动的文件；规格有改动时原样附上差异
- [ ] 本 Plan 获批即授权：新增 deps.py、doctor.py；返工 spec-guard-reader、map-view、query-commands、onboarding、line-health、patrol、hub-view 的代码；改 `docs/host-differences.md` 与 README；版本升到 0.0.7；每个任务完成后本地提交并推送本分支；在 scratchpad 里建临时协作组
- [ ] 不授权：Task 8 的实测（到时另外问你）；写任何真实的设置文件（权限放行只在测试里写临时目录）；开或合并 PR
