<!-- spec-guard: review approved 1ede07f3dd49 -->
# Spec: crew-line-status

> 能力图模块 `crew-line-status`（2026-10-18 预览插入，排在 transition-compat 之后）。来源：LIVE-SAAS 联合接入「插件补改」阶段，接入方案 D5、D6；接缝分析 JOINT-SEAM-CHECK 的 S6、S7、S10、S11 与第六节；联合测试 T3a、T7、T10、T12。用户 2026-10-18 在本会话直接同意插入。module-crew 的只读出口已由它的 crew-hub-bridge 模块发布（10-18 验收）。

## 目标

一条线由 module-crew 的协调会话带着多个模块并行开发时，主视图要说实话：

- 模块在干活、协调会话空闲时，这条线算「干活中」，不再误报「阻塞」和「全线互等」；
- 这一行列出各模块的状态；读不到就写「模块状态未知」，不瞎猜；
- doctor 看得到 module-crew：装没装、版本、契约、只读出口能不能读到。

只读 module-crew 在 interface.json 里发布的出口，不读它的状态库（协调人定的接缝原则）。

## 现状（已核对代码与本机实际输出）

- **module-crew 的出口**（已装 0.0.1，user 范围，`~/.claude/plugins/cache/module-crew-local/module-crew/0.0.1`）：
  - 插件根目录 `interface.json`：`{"interface": "1.0", "plugin": "module-crew", "version": "0.0.1", "contract": "1.7", "sessions": {"command": ["bin/module-crew", "sessions", "--json"], "schemaVersion": 1, "contract": "spec/crew-hub-bridge.md"}}`。
  - 在协调会话的仓库里运行 `bin/module-crew sessions --json`，得到 `{"schemaVersion": 1, "sessions": [...]}`。每条的契约字段：`module`、`relayName`（agent-relay 身份名）、`worktree`、`stage`（`spec-plan`／`build`／`returned`／`wait-merge`／`merged`）、`stageText`、`suspended`（挂起原因，没挂起为 null）、`lastActivity`。`ago` 等字段不是契约，不能依赖。
  - 读不到时退出码 2、stdout 为空、stderr 一行原因（在非仓库目录实测：退出码 2，用时约 0.09 秒）。
- **线状态**（`health.py`）：
  - 名册里只有协调会话，模块会话不在名册里。`_state` 按协调会话自己的事实判断：它开着等待单就是「阻塞：等 X」，而且只显示第一张单。
  - 信号 1「全线互等」：名册里所有会话都不在干活，并且还有没关的等待单。协调会话空闲、模块在干活时会误报。
  - 「停住 N 分钟」和信号 3 看的是协调会话仓库的 spec-guard activeModule（`_has_open_work`）。并行时这个 activeModule 不代表进度；停止钩子已经对协调会话跳过这项检查（crew-coordinator-seam）。
  - agent-relay 的事实（`relay.agents`）包含本机所有已登记的身份，模块会话的 presence、activity 本来就读得到，只是没人去查。
- **主视图**（`view._lines_row`）、`/lines`（`query.render_lines`）都直接显示 `LineState.text`。
- **doctor**（`doctor.py`、`deps.py`）：依赖只认 agent-relay、spec-guard、delegate（`deps.MAJORS`）。doctor 只读文件，不运行依赖的命令。
- 运行外部只读命令有先例：spec-guard-reader 运行 spec-guard 的 `map_view.py --json`。

## 要做的

1. **读出口**（新文件 `decision_inbox/crew.py`）：
   - `read_modules(repo) -> CrewRead`，结果是「读到了」（模块列表）或「未知」（附原因）。
   - 找插件：用 `deps.find("module-crew", project=repo)`，目录型市场按源目录（与现有依赖一样）。
   - 按版本范围读：`interface` 主版本为 1；`sessions.schemaVersion` 为 1；否则「未知」，原因写明版本。
   - 运行 `sessions.command`：第一项必须是插件根目录下的相对路径（不许 `..`、不许绝对路径），不经 shell，cwd 为协调会话名册条目的 `repo`，超时 3 秒。
   - 退出码不是 0、超时、JSON 读不懂、缺契约字段，都算「未知」，原因取 stderr 首行或具体问题。不读 module-crew 的任何状态文件。
   - 只对名册里带 `crewCoordinator`、有 `repo`、没退出的条目读，每次组装主视图、`/lines`、巡视时读一次。
2. **线状态**（`health.py`，只对协调会话那条线）：
   - 出口读到了：每个模块的状态 = 档位 + 它的 agent-relay 状态（按 `relayName` 查）。`merged` 的模块不列。
   - 判定顺序（前面的先命中）：
     1. 协调会话掉线 → 「掉线」；
     2. 协调会话要用户确认 → 「等你确认」；
     3. **有一个没挂起的模块在忙**（activity 为 busy；没有 activity 字段的旧版 agent-relay 按现有的 10 分钟窗口）→ 「干活中」；
     4. 其余照现在的规则（阻塞、等你决定、协调会话自己在干活、已结项、空闲）。
   - 协调会话那条线**不再判「停住」**（不看集成 checkout 的 activeModule），信号 3 也就不报。这与停止钩子的做法一致，模块进度归 module-crew。
   - 状态文字后面加括号列出各模块，例如：
     - `干活中（模块 a 在忙·构建、b 停着·等合并、c 挂起：等接口；还在等 API #1203、#1204）`
     - `阻塞：等 API（模块 a 停着·构建、b 掉线·写 Spec）`
     - 读不到：`阻塞：等 API（模块状态未知：<原因>）`
   - 档位的中文：`spec-plan` 写 Spec／Plan、`build` 构建、`returned` 被退回、`wait-merge` 等合并。会话状态：在忙、停着、掉线、无记录（agent-relay 里没有这个身份）。挂起原因超过 20 字截断。
   - 线是「干活中」而协调会话开着等待单时，括号里写「还在等」和单号，**列出全部**而不只第一张（S6 的 DI 确认）。
3. **全线互等**（信号 1）：
   - 协调会话那条线判为「干活中」，就算在干活，不报全线互等。
   - **有一条协调会话线的模块状态未知时，不报信号 1**：判断不了就不下结论，和「本次没读到 agent-relay 就不判」是同一条原则。
   - 没有模块在忙时，照常判阻塞、照常参与全线互等（T7：这时报是对的）。
4. **主视图、`/lines`**：显示带模块括号的状态文字；主视图里这一行太长时，各模块之间用「、」连，挂起原因按第 2 条截断，不另起一行。
5. **doctor**（D6）：
   - `deps.MAJORS` 加 `"module-crew": 1`；doctor 多一项「依赖：module-crew」，没装时为可选（ok）；**有协调会话条目却没装**时为异常。
   - 接口说明里多显示契约版本：与本插件钉的 v1.7 主版本相同为 ok，次版本不同在说明里写出；主版本不同为异常。
   - 每个协调会话条目多一项「module-crew 出口：<短名>」：用第 1 条的 `read_modules` 实际读一次，读到写「N 个模块会话」，读不到写原因、来源 module-crew。
   - 协调会话在不在线不归 doctor（doctor 不读 agent-relay），由主视图显示「掉线」。T12 的「协调会话不在线」按主视图核对。
6. **文档与版本**：README 写「并行开发线在主视图里怎么显示」和 doctor 的新项；版本 0.0.18。约定块不变，已接入的会话不用重跑。

## 关键决策与取舍（请重点审）

1. **忙闲由本插件从 agent-relay 判断，不要 module-crew 提供**：按第六节和 crew-hub-bridge 的约定。module-crew 只告诉我们模块的身份名和档位。
2. **一个模块在忙，整条线就算「干活中」，盖过「阻塞」**：协调会话开着等待单只说明某个模块在等别人，别的模块还在推进。等待单不丢，在括号里列出。代价是这条线的阻塞不会出现在「阻塞」状态词里，但仍在 `/flow` 和停住提示里。
3. **协调会话那条线不判「停住」**：集成 checkout 的 activeModule 在并行时不代表进度，判了就是误报。代价是模块长时间不动，本插件不报信号 3，要靠 module-crew 自己和协调会话；第一波后如需要，可以按模块的 `lastActivity` 另做。
4. **读不到出口时不报全线互等**：宁可漏报一次，不误报。读不到的原因会显示在这一行，doctor 也会报。
5. **doctor 实际运行一次出口命令**：doctor 原则是只读文件、不运行依赖的命令。这里破例，因为「出口能不能读到」只有运行才知道，而这个命令按 module-crew 的契约是只读的、1 秒内返回。破例只限这一个已发布的只读出口。
   - 另一种做法是只核对命令文件存在、可执行。用户 2026-10-18 选定实际运行。
6. **命令只从插件根目录下取**：interface.json 是文件，被改坏也不会让本插件去跑插件目录以外的程序。
7. **不改约定块，不碰巡视叫醒**：模块会话不在名册里，巡视叫不醒它们，由协调会话负责叫醒（S7 的协调会话规则）。

## 范围

做：
- 代码：新增 `decision_inbox/crew.py`；`health.py`（协调会话线的判定、信号 1）、`view.py`／`query.py`（显示，按需要）、`deps.py`（MAJORS、契约版本）、`doctor.py`（两项新检查）、`__main__.py`（组装时读出口，与 `_dev_maps` 同处）、`patrol.py`（如需传入）；
- 测试：新的 `tests/test_crew.py`，以及线状态、主视图、doctor 的测试；测试用假的 module-crew 插件目录（interface.json 加一个脚本），不依赖本机装的版本；
- 文档与清单：README、两份 `plugin.json`。

不做：
- 读 module-crew 的状态库或任何内部文件；
- 叫醒模块会话，或把模块会话加进名册；
- 按模块报「停住」「进展慢」等新信号；
- 显示「模块在等谁」（module-crew 出口没有这个字段，用户决定 27：第一波不做）；
- 改契约、改约定块；
- 碰 LIVE-SAAS。

## 验收标准

1. 出口读取：正常输出读成模块列表；`interface` 主版本不是 1、`schemaVersion` 不是 1、退出码 2、超时、JSON 坏、缺契约字段、命令路径跑出插件根目录、没装 module-crew，各得到「未知」和对应原因。有测试。
2. 协调会话空闲、开着一张等待单、有一个模块在忙：这条线是「干活中」，括号里列出各模块和「还在等」的全部单号；不报全线互等（T3a 的预期）。有测试。
3. 所有模块都停着、协调会话开着单：照常「阻塞：等 X」，括号里列出模块状态；其余线也都不在干活时，照常报全线互等（T7）。有测试。
4. 出口读不到：这一行写「模块状态未知：<原因>」，不报全线互等。有测试。
5. 挂起的模块即使在忙也不算；`merged` 的模块不列；agent-relay 里没有的模块写「无记录」。有测试。
6. 协调会话那条线不判「停住」、不报信号 3；普通开发线照旧。有测试。
7. 没有协调会话条目的协作组，主视图、`/lines`、巡视的输出和现在逐字相同（现有测试全部通过）。
8. doctor：没装 module-crew 且没有协调会话 → 可选；有协调会话却没装 → 异常；接口主版本不对 → 异常；契约次版本不同 → ok 并写明；每个协调会话条目报出口读到几个模块或读不到的原因。有测试。
9. 版本 0.0.18，两份清单一致；原有测试全部通过。
10. **实测（开始前另问用户）**：放到联合演练阶段，按 T3a、T7、T10、T12 跑，主视图样例交用户看。

## 假设

1. module-crew 出口在集成 checkout 里运行，名册里协调会话条目的 `repo` 就是这个 checkout（接入方案选项 B）。
2. 模块会话都在 agent-relay 登记了，`relayName` 与登记名一致（crew-hub-bridge 的约定）。
3. 一个协作组里协调会话条目不多（LIVE-SAAS 只有前端线一个），每次组装主视图多跑一次约 0.1 秒的命令可以接受。

## 未决问题

- 无（关键决策 5：用户 2026-10-18 选定 doctor 实际运行出口命令）。

## 文档建议

README：新增「并行开发线在主视图里怎么显示」（干活中的判定、括号里的模块状态、模块状态未知的含义），doctor 一节加 module-crew 两项。docs/stage6-field-acceptance.md：无。
