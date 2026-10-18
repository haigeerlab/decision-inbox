# Todo: hub-cutover-settings

测试命令：`python3 -m unittest discover -s tests -v`

- [x] Task 1：编号起点
  - 验收：Spec 验收 1–3
  - 文件：`decision_inbox/store.py`、`decision_inbox/onboard.py`、`decision_inbox/__main__.py`、`tests/test_store_group.py`、`tests/test_onboard.py`
  - 记录（2026-10-18）：
    - 先写用例：设了起点后从 #1001 开始编；还没编号时重设同一个值不报错；已经编过号后再设，报错且 `counter.json` 一字节都不变；0、负数、超过上限、字符串、小数、布尔值都报错；`onboard hub --start-number` 的预览会写明起点，重跑接入不报错，编过号后再设报 JoinError。先跑，9 个报错。
    - 实现：`counter.json` 里记下 `start`，用它判断「还没编号」，这样重跑接入也不会出错；新增 `Transaction.set_start_number`、`store.set_start_number`、`store.can_set_start_number`（只读，预览时用）、`onboard.hub(start_number=)`、命令参数 `--start-number`。
    - 实测：在临时目录跑 `onboard hub … --start-number 0`，退出码 2，提示「起始编号要是 1 到 1000000 的整数」。
    - 结果：Ran 615 tests, OK

- [x] Task 2：欠回复回归测试和文档
  - 验收：Spec 验收 4、5
  - 文件：`tests/test_relay.py`、`README.md`、`commands/hub-setup.md`、`tests/test_packaging.py`
  - 记录（2026-10-18）：
    - 回归测试放在 `relay.parse_agents` 这一层：主视图、巡视、doctor 都是读解析后的 agents 数据，所以只要证明带不带 `owesReplies`（152 条）解析结果完全一样、数据结构里也没有任何 owe 字段，就够了。这条测试一写就通过，是把现有行为固定下来；以后有人把欠回复读进来，它就会失败。
    - 文档：先在打包测试里加检查项，README 新增「### 替换已有的收件枢纽」一节（编号起点；切换前先处理完未读；历史欠回复本插件不读），`commands/hub-setup.md` 写明替换时先问用户起始编号、加 `--start-number`。
    - 全部测试：Ran 616 tests, OK

### Checkpoint（gate）：模块最终验收

- [x] 全部测试通过；验收标准逐条有证据；列出实际改动的文件
  - 记录（2026-10-18）：用户验收通过。616 个测试全部通过；Spec 验收第 6 条（实测）放到联合演练阶段，开始前另问用户。
