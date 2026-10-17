# Todo: p0-field-fixes

测试命令：`python3 -m unittest discover -s tests -v`

- [x] Task 1：契约升到 v1.5
  - 验收：Spec 验收 5
  - 验证：`python3 -m unittest discover -s tests -p test_contract.py -v`
  - 文件：`tests/fixtures/session-protocol/`、`tests/test_contract.py`
  - 记录（2026-10-18）：先改测试（v1.5、246e138、解析 55、跳过 18），在 v1.4 副本上 1 失败 7 报错；从契约 246e138 `git archive` 取出样例替换后 `shasum -c` 通过；e33c077→246e138 样例目录只有新增。Ran 568 tests, OK

- [ ] Task 2：命令读完输入文件即删除（F-P0-5）
  - 验收：Spec 验收 4
  - 验证：新增 `tests/test_consume.py`；全量测试
  - 文件：`decision_inbox/__main__.py`、`tests/test_consume.py`

- [ ] Task 3：巡视叫醒空闲积压的会话与收件枢纽（F-P0-2、F-P0-3）
  - 验收：Spec 验收 2
  - 验证：`tests/test_patrol.py`、`tests/test_view.py`
  - 文件：`decision_inbox/patrol.py`、`decision_inbox/view.py`

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
