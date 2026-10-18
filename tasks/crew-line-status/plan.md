<!-- spec-guard: review approved -->
# Implementation Plan: crew-line-status

> 依据：`spec/crew-line-status.md`（用户 2026-10-18 批准，doctor 实际运行出口命令）。任务清单：`tasks/crew-line-status/todo.md`。分支 `claude/crew-line-status`。

## Overview

五个任务：读出口 → 线状态判定 → 接到主视图、`/lines`、巡视 → doctor → 文档版本。每个任务先写失败的测试再改。所有测试用临时目录里的假 module-crew 插件（interface.json 加一个 Python 小脚本，按参数输出 JSON、退出码或睡眠），用 `DECISION_INBOX_PLUGINS_FILE` 指向假的安装记录，不依赖本机装的版本。

## Architecture Decisions

- **`decision_inbox/crew.py`**（新）：
  - `Module(module, relay_name, stage, suspended)`；`CrewRead(status: "ok"|"unknown", modules: tuple, reason: str)`。
  - `read_modules(repo, timeout=3.0) -> CrewRead`：`deps.find("module-crew", project=repo)` 找根目录；`deps.read_interface(root, 1)`；核对 `sessions.schemaVersion == 1`；核对命令第一项是根目录下的相对路径（`resolve()` 后仍在根目录内）；`subprocess.run(argv, cwd=repo, capture_output=True, text=True, timeout=timeout)`，不经 shell。
  - 输出核对：顶层 `schemaVersion == 1`，每条有 `module`、`relayName`、`stage`、`suspended` 四个字段且类型对；`stage` 不在已知枚举时照样列出、显示原文（出口只增不改，新档位不算读不懂）。
  - `crews(g) -> dict[relayName, CrewRead]`：名册里 `crewCoordinator`、有 `repo`、不在 `left` 里的条目各读一次。
- **线状态**（`health.py`）：
  - `assess(..., crews: dict | None = None)`，默认 None，和现在完全一样（Spec 验收 7）。`_Facts` 加 `crew: CrewRead | None`。
  - 新的 `_module_states(f, relay)`：对每个未合入的模块给出（id、会话状态词、档位中文、挂起原因）；会话状态：agent-relay 有 activity 时 busy→在忙、否则停着；没有 activity 时用现有 10 分钟窗口；presence 是 offline/unreachable→掉线；agent-relay 里没有→无记录；本次没读到 agent-relay→不写会话状态，只写档位。
  - `_state` 在「等你确认」之后、等待单判断之前插一步：协调会话线有一个**没挂起**的模块在忙 → `working`。
  - 协调会话线跳过「停住」（`_has_open_work` 对它返回 False），信号 3 随之不报。
  - 括号文字在 `assess` 末尾统一拼到 `LineState.text` 后面，`LineState` 不加字段；「还在等」列出全部未失效的等待单（目标短名 + #单号），只在线判为干活中时写。
  - 信号 1：任何一条协调会话线 `crew.status == "unknown"` 时不报。
- **接线**：`__main__.py` 里 `_assess`、巡视、`hub reply`、主视图四处把 `crew.crews(g)` 传下去；`hub.main_view`、`hub.reply`、`hub._close`、`patrol.plan` 加 `crews=None` 参数原样透传。`view`、`query` 不用改（直接显示 `state.text`），如测试发现截断问题再动。
- **doctor**：
  - `deps.MAJORS["module-crew"] = 1`；`deps.describe` 在接口 ok 且有 `contract` 字段时追加「契约 X」。
  - `doctor._dependency("module-crew")`：没装时，有协调会话条目→bad，否则 ok（可选）；契约主版本不是 1→bad；次版本不是 7→ok，说明里写「本插件按 1.7」。本插件钉的契约版本加一个常量 `protocol.CONTRACT_VERSION = "1.7"`（契约测试改用它，免得两处不一致）。
  - 每个协调会话条目一项「module-crew 出口：<短名>」，调 `crew.read_modules`，来源 module-crew。
  - doctor 模块说明里写明这一处破例（Spec 关键决策 5）。
- 版本 0.0.18；约定块不变。

## Task List

- [x] Task 1：`crew.py` 读出口（Spec 验收 1）
- [x] Task 2：协调会话线的状态判定与括号文字、信号 1、不判停住（Spec 验收 2–6）
- [ ] Task 3：接到主视图、`/lines`、巡视、收件枢纽答复；没有协调会话的协作组输出不变（Spec 验收 7）
- [ ] Task 4：doctor 与依赖检查（Spec 验收 8）
- [ ] Task 5：README 与版本 0.0.18（Spec 验收 9）

### Checkpoint（gate）：模块最终验收

- [ ] 全部测试通过；每条验收标准都有证据；列出实际改动的文件
- [ ] 授权：Task 1–5 的代码、测试和文档；每个任务做完都提交，并推送 `claude/crew-line-status`
- [ ] 不授权：改用户配置或已装插件、开 PR 或合并 PR、碰 LIVE-SAAS、改 module-crew 或契约仓库
- [ ] 实测（Spec 验收 10）放到联合演练，开始前另问用户

## Risks

| 风险 | 预防 |
|---|---|
| 每次主视图多跑一个命令，出口卡住拖慢收件枢纽 | 超时 3 秒；超时算「未知」；只对协调会话条目读 |
| interface.json 被改坏，让本插件跑别的程序 | 命令第一项必须解析到插件根目录里面，否则「未知」；不经 shell |
| 改 `assess` 签名牵连巡视、收件枢纽的现有调用 | 新参数默认 None；验收 7 用现有测试全部通过来证明不变 |
| 「在忙」盖过「阻塞」后，真阻塞被藏住 | 等待单在括号里全部列出；所有模块都停着时照常阻塞、照常参与全线互等（验收 3 的测试） |
| 测试依赖本机装的 module-crew | 全部用假插件目录和假安装记录 |
