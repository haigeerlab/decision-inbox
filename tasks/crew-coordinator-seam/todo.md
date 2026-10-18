# Todo: crew-coordinator-seam

测试命令：`python3 -m unittest discover -s tests -v`

- [x] Task 1：停止钩子跳过已挂起的模块，并给协调会话开例外
  - 验收：Spec 验收 4
  - 文件：`decision_inbox/stophook.py`、`decision_inbox/store.py`、`tests/test_stophook.py`、`tests/test_store_roster.py`
  - 记录（2026-10-18）：先写用例。新增的用例有：挂起的模块放行；协调会话有没勾完的 todo 时放行；协调会话有人在等时照常拦；协调会话有已答复、没发【已恢复】的事项时照常拦；普通开发线照常拦；两个字段只认布尔值，crewCoordinator 只能用于 dev，localRules 只能用于 Claude。先跑，2 个失败；实现 `_silent_stop` 的两个例外和名册校验后通过。Ran 599 tests, OK

- [x] Task 2：`--crew-coordinator` 标记和约定块里的新一节
  - 验收：Spec 验收 3
  - 文件：`decision_inbox/onboard.py`、`decision_inbox/doctor.py`、`decision_inbox/__main__.py`、`commands/join.md`、`tests/test_onboard.py`、`tests/test_doctor.py`
  - 记录（2026-10-18）：
    - 先写用例：预览阶段不写名册；确认后标记写进名册，约定块里在「开发线」一节之后多出「### 并行开发协调会话」，8 条要点都在；去掉参数重跑后，标记和这一节都消失；负责人、总协调带这个标记会报错，名册不变；其他角色的约定块里没有这一节；doctor 核对为 ok，修复命令保留 `--crew-coordinator`。先跑，4 个报错。
    - 实现：`_CREW_COORDINATOR`、`block(crew_coordinator=)`、`join(crew_coordinator=)`、doctor 的期望约定块和修复命令（修复命令同时保留 `--checkpoint-authority`，以前漏掉了，照着重跑会把它关掉）、命令参数、`commands/join.md`。Codex 的接入 skill 不改：module-crew 第一版的协调会话只在 Claude 上跑。
    - 结果：Ran 603 tests, OK

- [ ] Task 3：`--local-rules`：写进 CLAUDE.local.md，处理忽略规则，加 AGENTS.md 警告
  - 验收：Spec 验收 1、2
  - 文件：`decision_inbox/onboard.py`、`decision_inbox/doctor.py`、`decision_inbox/__main__.py`、`tests/test_onboard.py`、`tests/test_doctor.py`

- [ ] Task 4：文档和版本 0.0.16
  - 验收：Spec 验收 5
  - 文件：`README.md`、`docs/host-differences.md`、两份 `plugin.json`、`tests/test_packaging.py`

### Checkpoint（gate）：模块最终验收

- [ ] 全部测试通过；验收标准逐条有证据；列出实际改动的文件
