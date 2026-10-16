# Todo: group-store

测试命令：`python3 -m unittest discover -s tests -v`

- [ ] Task 1：插件骨架与包级静态检查
  - 验收：两份清单是合法 JSON，`name` 都是 `decision-inbox`、版本一致；`decision_inbox/` 只 import 标准库；代码里对状态文件没有 `unlink`／`rmtree`／`truncate`（Spec 验收 11、12）
  - 验证：`python3 -m unittest tests.test_package -v`
  - 文件：`.claude-plugin/plugin.json`、`.codex-plugin/plugin.json`、`decision_inbox/__init__.py`、`decision_inbox/__main__.py`、`tests/helpers.py`、`tests/test_package.py`

- [ ] Checkpoint 1（report）：全部测试全绿，记下命令与结果后继续

- [ ] Task 2：根目录、协作组名校验、`store init`
  - 验收：Spec 验收 1、2、10（含权限位、重复 init 不改内容与修改时间、非法组名退出码 2 且不建目录）
  - 验证：`python3 -m unittest tests.test_store_group -v`
  - 文件：`decision_inbox/store.py`、`decision_inbox/__main__.py`、`tests/test_store_group.py`

- [ ] Task 3：快照读写、版本与损坏检测、事务回滚
  - 验收：Spec 验收 4、5（`show` 部分除外）、6
  - 验证：`python3 -m unittest tests.test_store_state -v`
  - 文件：`decision_inbox/store.py`、`tests/test_store_state.py`

- [ ] Task 4：编号分配、事件日志与多进程并发
  - 验收：Spec 验收 3、7；`read_events(ref=...)` 按 seq 排序返回
  - 验证：`python3 -m unittest tests.test_store_events -v`，并发用例连续跑 5 次
  - 文件：`decision_inbox/store.py`、`tests/test_store_events.py`

- [ ] Checkpoint 2（report）：全部测试全绿，并发测试连续 5 次通过，记下命令与结果后继续

- [ ] Task 5：一致性检查与 `store show`
  - 验收：Spec 验收 8；验收 5 中 `store show` 退出码 3 并点名损坏文件
  - 验证：`python3 -m unittest tests.test_store_group tests.test_store_state -v`
  - 文件：`decision_inbox/store.py`、`decision_inbox/__main__.py`、`tests/test_store_group.py`、`tests/test_store_state.py`

- [ ] Task 6：会话名册
  - 验收：Spec 验收 9；`roster(g)` 返回条目列表，可按 `relayName`、`shortName` 查找
  - 验证：`python3 -m unittest tests.test_store_roster -v`
  - 文件：`decision_inbox/store.py`、`tests/test_store_roster.py`

- [ ] Checkpoint 3（gate）：模块最终验收——全部测试全绿、12 条验收标准逐条对应测试、列出实际改动文件；停下等用户确认
