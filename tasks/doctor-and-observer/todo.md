# Todo: doctor-and-observer

测试命令：`python3 -m unittest discover -s tests -v`

- [x] Task 1：deps.py 与 spec-guard 按接口说明读
  - 验收：Spec 验收 2（命令取自 interface.json；缺失、读不懂退回原入口；主版本不兼容不读能力图并写明原因；都不说成没装）
  - 验证：`python3 -m unittest discover -s tests -p test_specguard.py -v`
  - 文件：`decision_inbox/deps.py`、`specguard.py`、对应测试
  - 记录（2026-10-17）：4 个新测试先失败（2 失败 2 报错）；实现后 Ran 516 tests, OK。和计划的差别：不兼容时 `locate` 返回新类型 `Incompatible`，`read_line` 给新状态 `incompatible`（显示走原因文字，调用方不用改）；interface.json 里 mapView 的 schemaVersion 不是 1 也按不兼容处理

- [x] Task 2：delegate、agent-relay 接口读取与审查对照表
  - 验收：Spec 验收 3、4
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/deps.py`、`mapview.py`、对应测试
  - 记录（2026-10-17）：新测试 5 个先报错；实现后 2 个原有整表测试按新对照表失败（✔／— 改为通过／不适用），改期望后 Ran 521 tests, OK。`ModuleFact` 多了 `external_review`（默认 none）；delegate 命令名不合 `/delegate:小写-连字符` 时用默认值

- [x] Task 3：doctor 命令、`--json`、`--report`
  - 验收：Spec 验收 1
  - 验证：`python3 -m unittest discover -s tests -p test_doctor.py -v`
  - 文件：`decision_inbox/doctor.py`、`__main__.py`、对应测试
  - 记录（2026-10-17）：测试先于实现写好（模块不存在时全部报错）；实现后两处变异检查（不比较约定块、总做 Codex 信任检查）都被测试抓到。在 di-e2e 上实跑发现 agent-relay 报成 0.6.1：Claude 对目录型插件市场直接读源目录，安装记录里的版本是旧的；`deps.find` 改为先看 `known_marketplaces.json`，目录型市场取源目录里的插件（补 2 个测试，先失败后通过）。Ran 538 tests, OK。实跑结果：约定块 4 份都是当前版本、两条 Codex 线能加载；巡视 350 分钟没跑（异常）；Codex 里没有 decision-inbox 钩子的信任记录（未知）；三个依赖插件都兼容（agent-relay 0.8.2 接口 2.5、spec-guard 0.67.0 接口 1.0、delegate 0.5.3 接口 1.0）

- [x] Checkpoint 1（report）：全部测试全绿，记下命令与结果后继续
  - 记录（2026-10-17）：`python3 -m unittest discover -s tests` → Ran 538 tests, OK

- [x] Task 4：`query stats` 与 `query events --json`
  - 验收：Spec 验收 5
  - 验证：`python3 -m unittest discover -s tests -p test_query.py -v`
  - 文件：`decision_inbox/query.py`、`__main__.py`、对应测试
  - 记录（2026-10-17）：新测试 `tests/test_stats.py` 5 个先失败（1 失败 4 报错）；实现后 Ran 543 tests, OK。「绕过收件枢纽」= 有 `items.closed` 却没有 `items.answered` 的事项；`--since` 按日期（含当天）筛。在 di-e2e 上实跑发现开发B 的追问（#4747）被退回却统计为 0：追问退回只记在收件枢纽状态里，补一项「追问被退回」（测试先失败后通过）

- [x] Task 5：hub-setup 一次性权限放行
  - 验收：Spec 验收 6（不带 --confirm 不写；带了只写收件枢纽目录的本地设置文件；已有条目保留、不重复）
  - 验证：`python3 -m unittest discover -s tests -p test_onboard.py -v`
  - 文件：`decision_inbox/onboard.py`、`__main__.py`、对应测试
  - 记录（2026-10-17）：4 个新测试先失败（1 失败 3 报错）；实现后 Ran 547 tests, OK。和计划的差别：做成单独的 `onboard allow <组> --project <收件枢纽目录> [--confirm]`，hub 的接入步骤里加一步提示运行它（老协作组也能单独补）；放行条目：转发脚本命令、7 个 agent-relay 工具、桌面版会话消息工具。在 di-e2e 收件枢纽目录上只跑了预览，没写入

- [x] Task 6：来源标注
  - 验收：Spec 验收 7
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/health.py`、`patrol.py`、`view.py`、对应测试
  - 记录（2026-10-17）：先把 7 处测试期望改成带来源（含 3 处新断言），7 个失败；实现后 Ran 547 tests, OK。标注的提示：巡视没跑与没跑完一轮、叫不醒（Claude 桌面版）、读不到 agent-relay 与巡视读不到（agent-relay）、Codex 没被加载（Codex 桌面版）、spec-guard 接口不兼容（spec-guard）。格式函数 `deps.sourced`；实际改的是 `hub.py` 而不是 `view.py`

- [x] Checkpoint 2（report）：全部测试全绿；scratchpad 临时协作组命令行实跑 doctor、stats、权限预览，记下输出；推送本分支
  - 记录（2026-10-17）：Ran 547 tests, OK。scratchpad 临时协作组 cp2（收件枢纽 + 一条 Codex 开发线），人为改旧开发线约定块、把转发脚本指向别处、巡视最后一轮设在 162 分钟前：
    1. `doctor --group cp2` 退出码 3，「共 9 项：异常 3，未知 1」：✘ 转发脚本（写明指向的目录和本次代码目录、改法）、✘ 约定块：开发「不是当前版本」并给出重跑接入命令、✘ 巡视「162 分钟没跑」（来源：Claude 桌面版）、？ Codex 钩子信任（本机 Codex 配置里没有 decision-inbox 钩子的信任记录）；收件枢纽约定块、Codex 能加载、三个依赖插件均 ✔；
    2. `doctor --report`：版本 4 行，只列 4 项异常与未知，没有消息正文；
    3. `query stats cp2`：空组各项为 0、两段耗时写「没有数据」；
    4. `onboard allow cp2 --project <hub>`：列出 9 条要加的放行，没有建出 `.claude/` 目录（只预览）。
    观察：本机 Codex 没有 decision-inbox 钩子的信任记录，S3（Codex 停止钩子）实测前要先处理

- [x] Task 7：宿主差异文档、README 使用注意事项、版本 0.0.7
  - 验收：Spec 验收 8、9
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`docs/host-differences.md`、`README.md`、两份 `plugin.json`
  - 记录（2026-10-17）：先改版本断言与 README 断言（加 doctor 子命令和 6 处新文字），2 个失败；改完 Ran 547 tests, OK。宿主差异：H3 改为 0.7.1 起有引导式恢复；H10 补「邮箱转来的任务」一行；新增 H18、H19、H20，另加 H21（目录型插件市场读源目录，Task 3 实跑发现）；约束汇总表加 4 行。README：接入第 1 步加 `onboard allow`；改掉「只说读收件箱时开发线不接邮箱派的活」这句过时说法（0.0.6 起约定块写明，Task 6 实测已验证）；查询命令后加体检与统计；新增「使用注意事项」表 11 行；排查表加 doctor 一行

- [x] Task 8：实测 S1、S3
  - 验收：Spec 验收 10
  - 说明：先问用户
  - 记录（2026-10-18）：用户决定跳过，S1、S3 未实测。原因：S1 要先在测试收件枢纽目录写放行文件、再在定时任务列表点一次立即运行；S3 要在 Codex 里安装 decision-inbox 并信任钩子（doctor 实跑显示本机 Codex 没装、没有信任记录），都要改用户配置。留待后续

- [x] Checkpoint 3（gate）：模块最终验收，等用户确认
  - 记录（2026-10-18）：用户验收通过，同时批准修订后的规格（规格只追加「实测记录」一节）。Ran 547 tests, OK
