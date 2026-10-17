# Todo: protocol-contract-v1

测试命令：`python3 -m unittest discover -s tests -v`

- [x] Task 1：复制契约 v1.0 样例与一致性测试
  - 验收：Spec 验收 1、2、3（副本与来源说明、指纹核对；27 份解析、5 份生成全过，改坏即失败；原有 5 份与副本一致）
  - 验证：`python3 -m unittest discover -s tests -p test_contract.py -v`
  - 文件：`tests/fixtures/session-protocol/v1.0/`、`tests/test_contract.py`
  - 记录（2026-10-18）：样例从契约仓库标签 v1.0（7585be8）`git archive` 取出，`shasum -c` 通过；一致性测试 6 个全过（27 份解析逐项、5 份生成逐字、原有 5 份与副本一致）。Ran 553 tests, OK。变异检查：改坏期望结果、改坏样例原文都被指纹和逐项比较抓到；改坏生成代码（答复告知的说明）被抓到；改坏解析代码第一次没被抓到——从过简词里去掉「详见」，而契约的 brief-thin 样例要点只有 1 行，本来就按「少于 2 行」触发，**契约样例缺一份「要点够 2 行但含详见」的样例**，记为契约后续补充；换成放宽「是否完全停住」的取值后被抓到（valid、fullyStopped、problems 三处）。全部还原，产品代码无改动

- [x] Task 2：能力图外部依赖、README「消息协议」、版本 0.0.8
  - 验收：Spec 验收 4、5
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`spec/CAPABILITY-MAP.md`、`README.md`、两份 `plugin.json`、`tests/test_packaging.py`
  - 记录（2026-10-18）：先改版本断言和 README 断言，2 个失败；改完 Ran 553 tests, OK。能力图外部依赖表加一行 session-protocol v1.0（已钉住，提交 7585be8）；README 在「使用注意事项」前加「消息协议」一小节

- [x] Checkpoint（gate）：模块最终验收，等用户确认
  - 记录（2026-10-18）：用户验收通过。契约缺的「要点够 2 行但含详见」样例并进契约 v1.1 补。Ran 553 tests, OK
