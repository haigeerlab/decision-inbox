# Todo: hub-patrol

测试命令：`python3 -m unittest discover -s tests -v`

- [x] Task 1：`patrolDue` 与 `--from-hub`
  - 验收：Spec 验收 1、2
  - 文件：`decision_inbox/hub.py`、`decision_inbox/patrol.py`、`decision_inbox/__main__.py`、`tests/test_hub.py`、`tests/test_patrol.py`、`tests/test_consume.py`
  - 记录（2026-10-18）：先写用例（登记 11 分钟没跑、最近一轮 11 分钟前为真，9 分钟内为假，没登记为假；`--from-hub` 不叫醒收件枢纽、计划记 `by`；receive／reply 输出 `patrolDue`），先报错；实现 `hub.patrol_due`、`HUB_PATROL_MINUTES = 10`、`patrol.plan(from_hub=)`、`Plan.by`、命令参数与输出。Ran 591 tests, OK

- [x] Task 2：巡视记录来源与按来源统计
  - 验收：Spec 验收 3
  - 文件：`decision_inbox/patrol.py`、`decision_inbox/query.py`、`tests/test_patrol.py`、`tests/test_stats.py`
  - 记录（2026-10-18）：先写用例（`patrol.run` 事件带 `by`，旧计划缺省 schedule；统计分出定时任务 4 轮、收件枢纽 1 轮，文本与 JSON），1 失败 3 报错；实现后通过。只有收件枢纽顺带过时，文本才写来源细分。Ran 592 tests, OK

- [x] Task 3：约定块加「顺带巡视」
  - 验收：Spec 验收 4
  - 文件：`decision_inbox/hub.py`、`tests/test_hub.py`
  - 记录（2026-10-18）：先加断言（「### 顺带巡视」「`patrolDue` 为真」、`--from-hub` 的 plan 命令、record 命令、「notify 不发桌面通知」「先把用户的事处理完」），1 失败；约定块在「先判断是不是用户亲手输入」前加一节三步。Ran 592 tests, OK

- [x] Task 4：文档与版本 0.0.14
  - 验收：Spec 验收 5
  - 文件：`README.md`、`docs/host-differences.md`、两份 `plugin.json`、`tests/test_packaging.py`
  - 记录（2026-10-18）：先改打包测试（0.0.14、「收件枢纽会顺带巡视」「重跑一次 `/decision-inbox:hub-setup`」），2 失败；README 巡视介绍与升级一节、H24 补「已采用对策 B」后通过。Ran 592 tests, OK

- [x] Task 5：顺带巡视用单独的输入文件，`--from-hub` 缺文件时报错不误报
  - 来源：实测（2026-10-18 11:18）发现：收件枢纽把 `view` 和 `patrol plan` 写在同一条命令里共用 `{io}/agents.json`，`view` 读完即删，`patrol plan` 找不到文件，按「读不到 agent-relay」给用户发了误报。
  - 做法：约定块的顺带巡视改用 `{io}/patrol-agents.json`；`patrol plan --from-hub` 输入文件不存在时退出码 2、提示先写入，不生成 relay-unreadable 通知（文件在但读不懂才算读不到）。
  - 文件：`decision_inbox/hub.py`、`decision_inbox/__main__.py`、`tests/test_hub.py`、`tests/test_consume.py`、两份 `plugin.json`、`tests/test_packaging.py`、`README.md`
  - 记录（2026-10-18）：先写用例（约定块用 patrol-agents.json；`--from-hub` 缺文件退出码 2、提示 bridge_agents、不写计划；定时巡视缺文件仍照旧通知），2 失败；实现后通过。版本 0.0.15（约定块改了，收件枢纽要重跑接入）。Ran 593 tests, OK

- [x] Checkpoint（gate）：实测，开始前另问用户
  - 记录（2026-10-18）：用户同意后升级插件（0.0.14，再 0.0.15）、在 di-p0 开新收件枢纽会话重跑接入并接管身份名。
    - 第一轮（0.0.14，11:18）：收件枢纽读信后 `patrolDue` 为真，顺带巡视并记 `by: hub`；但把 `view` 与 `patrol plan` 写在同一条命令里共用 agents.json，被 view 读完即删，误报「读不到 agent-relay」→ 修为 Task 5（PR #11，0.0.15）。
    - 第二轮（0.0.15，11:29）：`patrolDue` 为假——距上一轮 10 分 41 秒，分钟数向下取整为 10，未「超过 10 分钟」；实际门槛相当于满 11 分钟。
    - 第三轮（0.0.15，11:34 读信，11:36:25 记账）：顺带巡视 `by: hub`，没有误报，没有要做的动作；patrol-agents.json 与 plan.json 读完已删。通过。
  - 另见：空闲的 Claude 收件枢纽会被桌面版停掉，agent-relay 叫不醒停掉的会话（消息排队到会话被打开）；收件枢纽要先被叫醒（巡视的 send_message 或用户打开）才谈得上顺带巡视。全组都没动静、定时任务又不触发时，没人兜底。

- [x] Checkpoint（gate）：模块最终验收，等用户确认
  - 记录（2026-10-18）：用户验收通过；实测记录另开小 PR。第 ⑥ 阶段 P0 由用户判定通过，P1 开始前另问用户。
