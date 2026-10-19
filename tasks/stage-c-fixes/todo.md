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
- [ ] Task 5：装、卸与体检（DI-11；验收 5）
  - 验证：假 launchctl 用例先失败后通过
- [ ] Task 6：文档、版本 0.0.31 与实跑（验收 8）
  - 验证：全量测试；副本主视图；临时组真通知；真实状态目录 md5 不变

## 检查点

- [ ] Checkpoint（gate）：模块最终验收——全部测试通过；每条验收标准有证据；列出实际改动的文件；批准后开 PR
