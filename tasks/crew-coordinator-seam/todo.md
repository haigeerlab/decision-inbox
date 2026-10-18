# Todo: crew-coordinator-seam

测试命令：`python3 -m unittest discover -s tests -v`

- [ ] Task 1：停止钩子跳过已挂起的模块，并给协调会话开例外
  - 验收：Spec 验收 4
  - 文件：`decision_inbox/stophook.py`、`decision_inbox/store.py`、`tests/test_stophook.py`、`tests/test_store_roster.py`

- [ ] Task 2：`--crew-coordinator` 标记和约定块里的新一节
  - 验收：Spec 验收 3
  - 文件：`decision_inbox/onboard.py`、`decision_inbox/doctor.py`、`decision_inbox/__main__.py`、`commands/join.md`、`skills/decision-inbox-join/`、`tests/test_onboard.py`、`tests/test_doctor.py`

- [ ] Task 3：`--local-rules`：写进 CLAUDE.local.md，处理忽略规则，加 AGENTS.md 警告
  - 验收：Spec 验收 1、2
  - 文件：`decision_inbox/onboard.py`、`decision_inbox/doctor.py`、`decision_inbox/__main__.py`、`tests/test_onboard.py`、`tests/test_doctor.py`

- [ ] Task 4：文档和版本 0.0.16
  - 验收：Spec 验收 5
  - 文件：`README.md`、`docs/host-differences.md`、两份 `plugin.json`、`tests/test_packaging.py`

### Checkpoint（gate）：模块最终验收

- [ ] 全部测试通过；验收标准逐条有证据；列出实际改动的文件
