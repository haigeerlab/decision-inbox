# Todo: onboarding

测试命令：`python3 -m unittest discover -s tests -v`

- [x] Task 1：`place`、`strip` 与 `BlockConflict`
  - 验收：Spec 验收 1（空文件、已有其他内容、同角色整块替换；别的角色或只有 BEGIN 时抛错、文本不变）、Spec 验收 2（只删本插件的块，没有块时原样返回）；块在开头、中间、结尾，有没有结尾换行，块外内容都逐字节不变
  - 验证：`python3 -m unittest discover -s tests -p test_onboard.py -v`
  - 文件：`decision_inbox/onboard.py`、`tests/test_onboard.py`

- [x] Task 2：三个角色的约定块文本
  - 验收：Spec 验收 3（关键决策 8 的要点逐条出现在对应角色；不该有的不出现，例如开发线没有多线事项写法；模板能被 `protocol.parse` 认出且没有问题）；收件枢纽块直接用 hub-loop 的 `convention`
  - 验证：`python3 -m unittest discover -s tests -p test_onboard.py -v`
  - 文件：`decision_inbox/onboard.py`、`tests/test_onboard.py`

- [x] Checkpoint 1（report）：全部测试全绿，记下命令与结果后继续
  - 记录（2026-10-17）：`python3 -m unittest discover -s tests -v` → Ran 375 tests, OK。Task 1、2 的测试都先失败（模块或函数不存在）；变异检查：去掉「末尾块连同前面空行删除」被 2 个测试抓住，审查结论模板改成不合规写法被 1 个测试抓住

- [x] Task 3：`hub`
  - 验收：Spec 验收 4（预览不建组、不写文件；`--confirm` 建组、登记收件枢纽含 `desktopSession`、写 `CLAUDE.md`、步骤含巡视提示词、`*/5 * * * *`、建议任务编号、手动立即运行一次）；Spec 验收 10 中适用于收件枢纽的提示
  - 验证：`python3 -m unittest discover -s tests -p test_onboard.py -v`
  - 文件：`decision_inbox/onboard.py`、`tests/test_onboard.py`

- [x] Task 4：`join`，含名册与审查者登记
  - 验收：Spec 验收 5（预览不改；按宿主写 `CLAUDE.md` 或 `AGENTS.md`；`repo` 为项目目录；重复接入替换）、Spec 验收 6（审查者登记成功或退出码 2 且什么都不改）、Spec 验收 7（名册规则不合时什么都不写）、Spec 验收 10（提示含 `bridge_register` 的 `wake: "auto"`、信任钩子两边各一次、Claude 会话用 `get_session` 取编号）
  - 验证：`python3 -m unittest discover -s tests -p test_onboard.py -v`
  - 文件：`decision_inbox/onboard.py`、`tests/test_onboard.py`

- [x] Task 5：`task`、`leave`、`teardown` 与命令行 `onboard`
  - 验收：Spec 验收 8（记编号；teardown 打印编号和 `delete_scheduled_task`；没记过时给建议编号并提示 `list_scheduled_tasks`）、Spec 验收 9（不改名册、不删状态文件）、Spec 验收 11（领域 `onboarding` 只由 `onboard.py` 写；原有子命令不受影响）；命令行每个子命令的退出码按规格
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/onboard.py`、`decision_inbox/__main__.py`、`tests/test_onboard.py`

- [x] Checkpoint 2（report）：全部测试全绿；在 scratchpad 的临时项目目录里用命令行跑一遍预览与 `--confirm`，记下输出和文件变化后继续
  - 记录（2026-10-17）：`python3 -m unittest discover -s tests -v` → Ran 398 tests, OK。scratchpad 临时目录 cp-ob 实跑：hub 预览退出码 0、协作组目录未建；hub --confirm 写入 CLAUDE.md（原有一行保留在前），后续步骤 6 条含 create_scheduled_task、*/5 * * * *、onboard task、立即运行；join 写入 AGENTS.md，repo 为项目目录；task 记下编号；leave 后前端 AGENTS.md 与接入前逐字节一致（cmp）；teardown 后枢纽 CLAUDE.md 只剩原有一行，并打印 delete_scheduled_task 与任务编号；store show 一致性正常。实跑发现提示里「Claude Code 在 /hooks 里确认」未经核实，改为不指定位置的写法，留到 plugin-packaging 实测钩子时补准确做法。Task 4 中另补了「负责人不能带审查者」的预检（原先会在写完后才报错），Task 5 中发现卸载事件没同时写快照导致 store show 报滞后，已改并加断言

- [x] Task 6：实测
  - 验收：Spec 验收 12（已改）：在 scratchpad 临时项目目录里，本会话用真实会话编号接入收件枢纽、负责人和开发线，再卸载；建巡视任务的实测挪到 plugin-packaging（用户 2026-10-17 确认）；结果写进 `spec/onboarding.md` 的实测记录
  - 验证：命令输出、规则文件内容、定时任务列表与运行记录
  - 文件：`spec/onboarding.md`
  - 记录（2026-10-17 00:24）：三个角色接入、重复接入、卸载全部按预期；卸载后两个原有规则文件与接入前逐字节一致；详见规格实测记录
  - 补记：准备验收、核对约定块全文时发现负责人、总协调块漏了规格关键决策 8 的「有审查者时写『架构审查』行」，先补测试（失败）再补文字

- [x] Checkpoint 3（gate）：模块最终验收——全部测试全绿、12 条验收标准逐条有测试或实测记录、列出实际改动文件、原样附上三个角色约定块全文与规格差异；停下等用户确认
  - 记录：398 个测试全绿（连跑 2 次），本模块 40 个；用户 2026-10-17 验收通过，并批准修订后的规格（实测范围改为接入与卸载，建巡视任务的实测挪到 plugin-packaging）
