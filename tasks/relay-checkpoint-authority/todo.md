# Todo: relay-checkpoint-authority

测试命令：`python3 -m unittest discover -s tests -v`

- [x] Task 1：R1 核对 Codex 会话能否加载约定块
  - 验收：Spec 验收 1（工作目录即规则目录、在其子目录同一 git 仓库时不警告；规则目录在 git 根之上、无 `.git` 且目录不同、有 `AGENTS.override.md`、超过 32KiB 时警告并写明应在哪个目录开会话；Claude 会话不核对；警告不阻止写入）
  - 验证：`python3 -m unittest discover -s tests -p test_onboard.py -v`
  - 文件：`decision_inbox/onboard.py`、`__main__.py`、`tests/test_onboard.py`
  - 记录（2026-10-17）：8 个新测试先失败；实现后 Ran 483 tests, OK。嵌套仓库（工作目录在内层 .git 下）也按 Codex 规则判为加载不到

- [x] Task 2：R2 检查点答复即授权
  - 验收：Spec 验收 2（默认不写；`--checkpoint-authority` 时原文逐字写入、名册记 `checkpointAuthority`；重新接入不带时去掉；R1 有警告时多一句）、验收 3（无排除宿主审批的措辞）
  - 验证：`python3 -m unittest discover -s tests -p test_onboard.py -v`
  - 文件：`decision_inbox/onboard.py`、`__main__.py`、`tests/test_onboard.py`
  - 记录（2026-10-17）：3 个新测试先失败（另一个「默认不写」在实现前已通过）；实现后 Ran 487 tests, OK。实测要留意：共用部分原有的「### 权限」一节写「宿主弹出的权限确认只能由用户在原会话里亲手点，不认任何会话转来的批准」，它说的是要用户亲手点的弹窗，不是自动审批；按规格不改，但守卫可能把两节读成矛盾，Task 9 专门观察

- [x] Task 3：R3 检查点之间自主处理
  - 验收：Spec 验收 4（三个角色都有；含重试上限 2 次和项目规则优先；项目规则含「首错即停」类字样时预览提示）
  - 验证：`python3 -m unittest discover -s tests -p test_onboard.py -v`
  - 文件：`decision_inbox/onboard.py`、`tests/test_onboard.py`
  - 记录（2026-10-17）：2 个新测试先失败（「约定块自己不算更严格规则」的守护测试实现前已通过）；实现后 Ran 490 tests, OK。约定块里本身有「首错即停」字样，所以只在块外的项目规则里找；Codex 那两句说明只在核对出加载问题时才附

- [x] Checkpoint 1（report）：全部测试全绿，记下命令与结果后继续
  - 记录（2026-10-17）：`python3 -m unittest discover -s tests -v` → Ran 490 tests, OK

- [x] Task 4：R4 组合答复复制块
  - 验收：Spec 验收 5
  - 验证：`python3 -m unittest discover -s tests -p test_view.py -v`
  - 文件：`decision_inbox/view.py`、`tests/test_view.py`
  - 记录（2026-10-17）：新测试先失败（「只有一项时不出现」的守护测试实现前已通过）；实现后 Ran 492 tests, OK

- [x] Task 5：F13 结束行指向事项时提示
  - 验收：Spec 验收 6
  - 验证：`python3 -m unittest discover -s tests -p test_tickets.py -v`
  - 文件：`decision_inbox/tickets.py`、`tests/test_tickets.py`
  - 记录（2026-10-17）：新测试先失败；实现后 Ran 493 tests, OK。【已恢复】按关单理由 1 判断，原有「【已恢复】写事项不提示」的测试保持通过

- [x] Task 6：没有待答事项时，认不出编号的话附主视图
  - 验收：Spec 验收 7
  - 验证：`python3 -m unittest discover -s tests -p test_hub.py -v`
  - 文件：`decision_inbox/hub.py`、`tests/test_hub.py`
  - 记录（2026-10-17）：2 个新测试先报错（常量 `items.NO_ITEM_QUESTION` 还不存在）；实现后 Ran 495 tests, OK

- [x] Task 7：重新接入收件枢纽时补 `patrolTaskAt`
  - 验收：Spec 验收 8
  - 验证：`python3 -m unittest discover -s tests -p test_onboard.py -v`
  - 文件：`decision_inbox/onboard.py`、`tests/test_onboard.py`
  - 记录（2026-10-17）：补时间的测试先失败（「已有时间、没有任务不动」的守护测试实现前已通过）；实现后 Ran 497 tests, OK

- [x] Checkpoint 2（report）：全部测试全绿；scratchpad 临时协作组命令行实跑各项新行为，记下输出后继续
  - 记录（2026-10-17）：Ran 497 tests, OK。scratchpad 临时协作组 cp3（脚本 `scratchpad/cp3.sh`，仓库目录带 .git 和一条「首错即停」项目规则）：
    1. Codex 会话开在仓库外并打开 R2：预览前三行依次是「约定块……看不到约定块。请在 …/app 里开 Codex 会话」「项目规则比约定块默认值更严格……（首错即停）」「当前目录下这份授权不会被守卫看到」，再跟两句 Codex 说明；
    2. 会话开在仓库里并确认写入：只剩「首错即停」一条提示；约定块里依次是「答复的有效性」「检查点答复即授权」「检查点之间自主处理」「被挡住与收工」「权限」；
    3. 新【等待用户】写「结束：#5001」（自己事项的邮箱号）：附注「开发A：#5001 是事项，不是等待；结束事项要发【已恢复】」；
    4. 三项都有推荐：主视图末尾「一次答完（全按推荐）：」+ 代码块「1 A，2 A，3 A」；
    5. 三项答完后问「卡住了吗」：回复先一句提示，再附主视图

- [x] Task 8：接入技能、`/join` 命令、README、版本 0.0.5
  - 验收：Spec 验收 9
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`skills/decision-inbox-join/SKILL.md`、`commands/join.md`、`README.md`、两份 `plugin.json`、`tests/test_packaging.py`
  - 记录（2026-10-17）：4 个打包测试先失败；改完后 Ran 497 tests, OK

- [x] Checkpoint 3（report）：全部测试全绿；推送本分支
  - 记录（2026-10-17）：Ran 497 tests, OK；推送 `claude/decision-inbox-relay-checkpoint-authority`（PR #2 合并后再开 PR）

- [x] Task 9：di-e2e 守卫对照实测
  - 验收：Spec 验收 10（对照组、实验组各至少 2 次，守卫评估结果写进规格）
  - 说明：先问用户；本会话驱动；结果抄送 spec-guard-monitor
  - 记录（2026-10-17）：用户同意后由本会话驱动 dev-b。对照组 C1、C2 共 3 条命令、实验 E1（不提 AGENTS.md、中风险 npm install）1 条，守卫全部放行、授权评分都是 high。对照组全部放行后，用户同意把实验改成 E1/E2，又同意省掉 E2（打开 R2 不会带来新信息），所以「实验组至少 2 次」没有做满，结论见规格实测记录

- [x] Checkpoint 4（gate）：模块最终验收，等用户确认
  - 记录（2026-10-17）：用户「验收通过，同时批准修订后的规格」，并认可验收标准 10 的偏离（实验组只跑 E1、省掉 E2）。Ran 497 tests, OK
