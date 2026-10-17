# Todo: e2e-round1-fixes

测试命令：`python3 -m unittest discover -s tests -v`

- [x] Task 1：答复、多线答复、告知写原消息号
  - 验收：Spec 验收 1（三种正文都带「原消息 #R」；`source_relay_id` 为空时正文不变；带括号的「事项」解析出的事项号不变）；F1 回归：开发A 抛 #4540，答「1 A」，答复正文含「你的原消息 #4540」
  - 验证：`python3 -m unittest discover -s tests -p "test_*.py" -v`
  - 文件：`decision_inbox/protocol.py`、`items.py`、`hub.py`、对应测试
  - 记录（2026-10-17）：4 个新测试先失败；实现后 Ran 451 tests, OK。【答复告知】本来不被 `protocol.parse` 识别（kind 为 unknown），测试改为只核对正文

- [x] Task 2：开发线追问自动退回
  - 验收：Spec 验收 3（标了要回复或填了 replyTo 的未知消息退回；replyTo 指向已发答复或告知时第三行带事项号和原消息号；主视图附注照旧；异常计数加一）、验收 4（回复退回消息、bridge 通知不退回；没标要回复的未知消息只记附注）；F2 回归：#4543 产生退回
  - 验证：`python3 -m unittest discover -s tests -p test_hub.py -v`
  - 文件：`decision_inbox/hub.py`、`view.py`（若需要）、`tests/test_hub.py`
  - 记录（2026-10-17）：5 个新测试先失败；实现后全量 Ran 456 tests, OK。变异检查：去掉「不退回对退回的回复」，被 `test_no_return_for_plain_notes_bridge_or_replies_to_a_return` 抓住。异常行经 `view.render(extra=…)` 进入主视图的异常段和计数

- [x] Checkpoint 1（report）：全部测试全绿，记下命令与结果后继续
  - 记录（2026-10-17）：`python3 -m unittest discover -s tests -v` → Ran 456 tests, OK

- [x] Task 3：`inbox reply --relayed-from`
  - 验收：Spec 验收 5（不改事项和等待单；记 `hub.relayed-input`，actor 为来源；提示含来源、原话和「请你在这里亲手回一遍」）
  - 验证：`python3 -m unittest discover -s tests -p "test_hub.py" -v` 和命令行测试
  - 文件：`decision_inbox/hub.py`、`__main__.py`、对应测试
  - 记录（2026-10-17）：3 个新测试先失败；实现后 Ran 459 tests, OK。转来的话（包括「以后 X 都这样」）都不进入任何解析分支

- [x] Task 4：巡视停摆报警
  - 验收：Spec 验收 7（从没跑完且登记超过 15 分钟、最近一轮超过 15 分钟都报警；15 分钟内不报；没登记巡视任务不报；老协作组没有 `patrolTaskAt` 时只按 `lastRunAt` 判断；主视图和 `query flow` 第一行都有）
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/hub.py`、`onboard.py`、`__main__.py`、对应测试
  - 记录（2026-10-17）：7 个新测试和断言先失败；实现后 Ran 465 tests, OK。判断函数 `hub.patrol_alarm` 由主视图和 `query flow` 共用，阈值常量 `PATROL_STALE_MINUTES = 15`

- [x] Task 5：「在等谁」认身份名
  - 验收：Spec 验收 9
  - 验证：`python3 -m unittest discover -s tests -p test_tickets.py -v`
  - 文件：`decision_inbox/tickets.py`、`tests/test_tickets.py`
  - 记录（2026-10-17）：新测试先失败；实现后 Ran 466 tests, OK

- [x] Task 6：卸载删掉空的新建规则文件
  - 验收：Spec 验收 10（新建且删块后为空才删；原有文件、另加了内容的新建文件都保留；预览写明会删；静态扫描只放行 `_drop_created_rules`）
  - 验证：`python3 -m unittest discover -s tests -p "test_onboard.py" -v`、`-p test_package.py`
  - 文件：`decision_inbox/onboard.py`、`tests/test_onboard.py`、`tests/test_package.py`
  - 记录（2026-10-17）：5 个新测试先失败；实现后 Ran 470 tests, OK。变异检查：在 hub.py 另加一处 `unlink`，被 `test_no_deletion_calls` 拦下。静态扫描同时要求放行的那一处确实存在，例外不会悄悄失效

- [x] Checkpoint 2（report）：全部测试全绿；scratchpad 临时协作组上命令行跑一遍 S0 和各项新行为，记下输出后继续
  - 记录（2026-10-17）：Ran 470 tests, OK。scratchpad 临时协作组 cp2（收件枢纽 cp2-hub、开发A cp2-dev，目录原本没有规则文件），脚本 `scratchpad/cp2.sh`：
    1. 开发A 的【等待用户】#4540 入表为 #1；
    2. `--relayed-from spec-guard-monitor` 的「1 A」：sends 为空，提示「这不是你在这里亲手输入的，没有转达给任何会话」；
    3. 亲手「1 A」：答复给 cp2-dev（replyTo 4540），正文「事项：#1（你的原消息 #4540）」；
    4. 开发A 回问 #4543（replyTo 4542）和【等待其他会话】#4544（在等谁：cp2-hub）：生成一条退回给 cp2-dev（replyTo 4543），第三行「你回的 #4542 是用户对事项 #1（你的原消息 #4540）的答复。」；附注里没有「不在会话名册里」；
    5. 主视图异常 1，行为「开发A：问了收件枢纽（#4543），已自动退回」；
    6. 巡视登记时间改到 20 分钟前：主视图第一行「⚠ 巡视还没跑完过一轮：去定时任务列表找 decision-inbox-patrol-cp2…」；
    7. 卸载开发A：预览写「确认后会删掉这个文件」，确认后 `dev/` 目录为空

- [x] Task 7：约定块、hub-setup、README、需求记录、版本 0.0.4
  - 验收：Spec 验收 2、6、8、11
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/onboard.py`、`hub.py`、`commands/hub-setup.md`、`README.md`、`docs/requirements-record.md`、两份 `plugin.json`、对应测试
  - 记录（2026-10-17）：约定块和版本的 3 个测试先失败；hub-setup 和 README 的断言与实现同一步加入，没有单独看到失败。实现后 Ran 470 tests, OK。共用约定另加一条「收件枢纽不答疑：有疑问抛【等待用户】，不要回问后干等」，与 F2 的退回说明一致

- [x] Checkpoint 3（report）：全部测试全绿；推送本分支、开 PR（不合并）；给 spec-guard-monitor 发会话消息说明可以重跑，附分支、版本和改动要点
  - 记录（2026-10-17）：Ran 470 tests, OK；推送 `claude/decision-inbox-e2e-round1-fixes`，开 PR haigeerlab/decision-inbox#2（不合并，仓库没有 CI 检查）；已给 spec-guard-monitor 发会话消息

- [x] Task 9：结束行认发送方自己的邮箱号（F10），README 记 F9
  - 验收：Spec 验收 13（自己的等待单和事项按邮箱号能关；别人的不关；对不上有 `end-unknown` 提示；约定块有这一句）、验收 14
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/tickets.py`、`items.py`、`onboard.py`、`README.md`、对应测试
  - 记录（2026-10-17）：6 个新测试先失败；实现后 Ran 475 tests, OK。另有一个守护测试（自己的事项邮箱号不报 `end-unknown`）在实现前就通过，用来防止误报

- [x] Task 10：卡片看得出该回什么（F12）
  - 验收：Spec 验收 15（「推荐回复」一行在复制块上方，全卡一个代码块；选项第一行完整；约定块写明不套代码块）
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/view.py`、`hub.py`、`tests/test_view.py`、`tests/test_hub.py`
  - 记录（2026-10-17）：3 个改后的测试先失败；实现后 hub-view 规格样例的逐字比对也失败（预期内，样例没有「推荐回复」一行），测试里给样例套上 F12 的改动，已验收的 hub-view 规格不改。Ran 475 tests, OK

- [x] Task 8：spec-guard-monitor 在 di-e2e 重跑 S0
  - 验收：Spec 验收 12；结果写进规格的实测记录
  - 说明：重跑由 spec-guard-monitor 主持，本会话不动测试环境
  - 记录（2026-10-17）：第一次重跑因转发脚本被改回 0.0.3 只验证了 F3；用户授权后本会话切换插件来源、重新接入，第二次重跑由本会话（di-e2e-driver）驱动 dev-a 的 S0、spec-guard-monitor 驱动 dev-b 的 S0b，F1、F2、F3、F4、F10 通过，F12 部分实测。详见规格的实测记录

- [ ] Checkpoint 4（gate）：模块最终验收，等用户确认
