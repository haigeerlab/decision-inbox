# Todo: stage-c-fixes

- [x] Task 1：协议升到 v2.4（验收 2 样例部分）
  - 验证：v2.4 样例一致性与三份新样例先失败后通过
  - 结果：样例目录 git mv 为 v2.4，用契约 495b475 的 git archive 覆盖（已有样例零改动，新增 6 个文件）；先跑出 7 处失败（「模块」并进了上一个字段），解析器把「模块」列为【等待用户】字段后通过；事项新增 `module` 键（ModuleFieldTest 3 条先失败后通过）；`test_cards`、`test_go_to_session` 原来写死 v2.3 路径，改为跟随 CONTRACT_VERSION；全量 1044 项通过
- [x] Task 2：模块反查与重判（DI-10；验收 1、2、3）
  - 验证：反查各步单测与阶段丙重放先失败后通过
  - 结果：`ReverseLookupTest` 5 条、`StageCReplayTest` 3 条在 1c2d3c9 的 loops/view 上 4 失败 2 报错，改后通过。阶段丙重放是按 #59–#63 的形状手写的夹具（模块协调 co、模块 zeta、C166/C184/C186 三次答复后都没动），不是 di-p0 原始数据；原始数据在 Task 6 的副本上实跑。普通开发线的「模块未知」不按当前模块重判（已有 TagTest 不改）
- [x] Task 3：停滞起点与扣除（DI-12；验收 6、7）
  - 验证：epsilon 重放与三种扣除用例先失败后通过
  - 结果：`StallClockTest` 5 条在 1c2d3c9 上全部失败，改后通过。起点取最后提交、startedAt、最近一次答复送达（module-crew answers 与收件箱发送记录）三者最晚，停滞说明对应写「你的答复 … 送达后 N 小时没有新提交」；等待算到答复发送成功；几个模块的交审编号同在一项里的不归任何模块（不猜），对涉及的每个模块都扣；模块协调的等待记录点名的只扣那个模块，不点名的扣全部
  - 改写的旧测试：`test_loops` 的 `LoopsCase.item` 给已答事项补一条发送记录（口径改为「等到发送成功」，不改被测行为）
- [x] Task 4：patrol-watch 命令（DI-11；验收 4）
  - 验证：通知节奏四种情况用例先失败后通过
  - 结果：新 `watch.py` 与 `decision-inbox patrol-watch <组>`；判据直接用 `hub.patrol_alarm`；通知标题「决策收件箱：巡视停了」，正文去掉「⚠ 」和来源尾巴，含巡视会话链接与修法；30 分钟内不重发，发送失败下一轮再试，恢复后清掉记录；命令总是退出 0（组不存在只写 stderr），避免 launchd 停掉任务。`tests/test_watch.py` 4 条（在 1c2d3c9 上没有这个模块，全失败），改后通过；状态放在 `state/patrol-watch.json`
- [x] Task 5：装、卸与体检（DI-11；验收 5）
  - 验证：假 launchctl 用例先失败后通过
  - 结果：新命令 `onboard watch <组> [--confirm]`：预览打印 plist 全文，确认后写 `~/Library/LaunchAgents/com.haigeerlab.decision-inbox.patrol-watch.<组>.plist`（每 300 秒、登录即跑，日志在组目录 patrol-watch.log），先 bootout 再 bootstrap；`onboard hub` 后续步骤加这一步；`onboard teardown` 预览列出、确认后卸掉；doctor 新增「巡视提醒」（没装／没加载 bad，附装的命令）。`InstallTest` 4 条、`WatchOnboardCommandTest` 1 条先失败后通过；hub-setup、teardown 命令说明跟上
  - 改写的旧测试：`test_package` 的删除扫描白名单加 `watch.py` 的 `uninstall`（只删本插件自己写的 plist）
- [x] Task 6：文档、版本 0.0.31 与实跑（验收 8）
  - 验证：全量测试；副本主视图；临时组真通知；真实状态目录 md5 不变
  - 文档：README「模块打转」（模块来源与停滞口径）、「消息协议」（v2.4）、「升级」（0.0.31 段）、「卸载」、「排查」（系统通知一行）；`docs/glossary.md` 加「巡视提醒」；命令用法加 `patrol-watch`、`onboard watch`；两个插件清单 0.0.31
  - 真实数据（2026-10-20，di-p0 复制到 scratchpad，module-crew 事实用 `sessions --json` 现读 crew-rehearsal）：#61、#62、#63、#64 由「模块未知」改归 zeta，#34 归 summary，#55 归 epsilon，#29～#58 的去会话操作归各自模块；#35（gamma、summary 两个 worktree）、#44（delta C121、epsilon C119 合问）仍不归任何模块。「看模块 zeta」列出 #57～#65，#63 显示「答了 63 继续等」
  - 实跑时发现并修正：#36 的「要你决定」写了 gamma、summary 两个模块，要点里先出现 rh2-gamma，被认成 gamma；改为「要你决定」点名两个以上模块、或出现两个以上模块会话名时算合问，不猜（`test_two_modules_named_anywhere_is_joint` 先失败后通过）；合问扣除也认会话名
  - 真实 `~/.decision-inbox/di-p0/state` 前后 md5 都是 712959e9b6600a8b1c0ac6bf7c9b03c5
  - 真通知：scratchpad 临时组 watch-demo（巡视 62 分钟没跑）手动跑 `patrol-watch`，弹出「决策收件箱：巡视停了」，正文含巡视会话链接与修法；紧接着再跑不重弹。没有装 launchd。演示前单独测 osascript 时多弹过一条「测试正文」
  - 没做到：epsilon 场景只在单测里重放（module-crew 当时的 `sessions --json` 已无法还原，现在读到的是全部合入后的事实）

<!-- spec-guard: external-review declined -->

## 检查点

- [x] Checkpoint（gate）：模块最终验收——全部测试通过；每条验收标准有证据；列出实际改动的文件；批准后开 PR（用户 2026-10-20 回「批准；I-15 A」：I-15 这次不修，以后再说）

## 交审期间收到的知会（2026-10-20）

- spec-guard SG-4（PR #392，未合并未发版）：中文检查点也计入 `gates.total`，interface 升 1.6。本插件 `deps.read_interface` 只查主版本（1.x 都接受），`specguard._gates` 只读数字，不用改；新版装上后基准自然变准（crew-rehearsal 五个模块应为 3、3、3、3、4）。
- I-15（O-patrol-left-tracked，低）：`patrol.json` 的 `snapshot.sessions` 仍存着已退出的 rh-coord；叫醒和计数早已排除已退出的会话，只是快照多存一份。来源：spec-guard 负责人转出，记在接入方 DECISION-INBOX-ISSUES 的 I-15。不在本模块范围；用户 2026-10-20 定 A：这次不修，以后再说。
