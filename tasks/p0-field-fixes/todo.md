# Todo: p0-field-fixes

测试命令：`python3 -m unittest discover -s tests -v`

- [x] Task 1：契约升到 v1.5
  - 验收：Spec 验收 5
  - 验证：`python3 -m unittest discover -s tests -p test_contract.py -v`
  - 文件：`tests/fixtures/session-protocol/`、`tests/test_contract.py`
  - 记录（2026-10-18）：先改测试（v1.5、246e138、解析 55、跳过 18），在 v1.4 副本上 1 失败 7 报错；从契约 246e138 `git archive` 取出样例替换后 `shasum -c` 通过；e33c077→246e138 样例目录只有新增。Ran 568 tests, OK

- [x] Task 2：命令读完输入文件即删除（F-P0-5）
  - 验收：Spec 验收 4
  - 验证：新增 `tests/test_consume.py`；全量测试
  - 文件：`decision_inbox/__main__.py`、`tests/test_consume.py`、`tests/test_package.py`
  - 记录（2026-10-18）：先写 `test_consume.py`（9 项：只删临时目录与协作组 io/ 下的文件；patrol plan／record、inbox receive／reply、view 读完即删；读不出的 agents 与动作对不上的计划保留；计划文件不在时 record 返回 2；只读 query 不删），导入失败；实现 `_consume` 并接到各命令后 9 项通过。静态检查「不删除任何文件」的白名单加入 `_consume`（规格批准的删除）。Ran 577 tests, OK

- [x] Task 3：巡视叫醒空闲积压的会话与收件枢纽（F-P0-2、F-P0-3）
  - 验收：Spec 验收 2
  - 验证：`tests/test_patrol.py`、`tests/test_view.py`
  - 文件：`decision_inbox/patrol.py`、`decision_inbox/view.py`
  - 记录（2026-10-18）：先加 6 个用例（空闲且最早未读 ≥5 分钟才叫、<5 分钟不叫、同一积压只叫一次后通知用户且措辞为「消息还没读」、空闲无信或忙碌不叫、收件枢纽空闲积压被叫醒、停着的收件枢纽同轮只叫一次；主视图建议按宿主分），3 失败 1 报错；实现 `IDLE_WAKE_MINUTES`、`_idle_backlog`，`_wakes` 纳入收件枢纽，`_wake_hub` 同轮不重复，`view.advice` 对 Codex 写「打开 X 的任务」。Ran 583 tests, OK

- [ ] Task 4：取代写邮箱号的退回说明与约定块（F-P0-1）
  - 验收：Spec 验收 1
  - 验证：`tests/test_items.py`、`tests/test_onboard.py`
  - 文件：`decision_inbox/items.py`、`decision_inbox/onboard.py`

- [ ] Task 5：文档与版本 0.0.12（F-P0-4）
  - 验收：Spec 验收 3、6
  - 验证：全量测试
  - 文件：`README.md`、`commands/hub-setup.md`、`docs/host-differences.md`、`docs/stage6-field-acceptance.md`、两份 `plugin.json`、`tests/test_packaging.py`

- [ ] Checkpoint（gate）：S1 重测，开始前另问用户

- [ ] Checkpoint（gate）：模块最终验收，等用户确认
