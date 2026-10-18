# Todo: crew-line-status

- [x] Task 1：`crew.py` 读出口（Spec 验收 1）
  - 验证：`python3 -m unittest tests.test_crew`；正常、接口主版本不对、schemaVersion 不对、退出码 2、超时、JSON 坏、缺字段、路径跑出根目录、没装，各有用例
- [x] Task 2：协调会话线的状态判定与括号文字、信号 1、不判停住（Spec 验收 2–6）
  - 验证：`tests/test_health.py` 新用例：一个模块在忙盖过阻塞并列出全部等待单；全停着照常阻塞与全线互等；未知不报信号 1；挂起的忙不算；merged 不列；无记录；协调会话线不判停住
- [x] Task 3：接到主视图、`/lines`、巡视、收件枢纽答复（Spec 验收 7）
  - 验证：主视图与 `/lines` 显示带括号的状态；现有测试全部通过
- [x] Task 4：doctor 与依赖检查（Spec 验收 8）
  - 验证：`tests/test_doctor.py`、`tests/test_deps.py` 新用例：可选、有协调会话却没装、主版本不对、契约次版本不同、出口读到几个模块或读不到的原因
- [x] Task 5：README 与版本 0.0.18（Spec 验收 9）
  - 验证：`python3 -m unittest discover -s tests` 全部通过；两份清单 0.0.18

## Checkpoint（gate）：模块最终验收

- [x] 全部测试通过；每条验收标准都有证据；列出实际改动的文件（用户 2026-10-18 验收通过）
- [x] 实测（Spec 验收 10）放到联合演练，开始前另问用户（记录：2026-10-18 用户验收通过，659 个测试通过；实测未做，待联合演练）

## 修订 1

- [ ] Task 6：同一会话的多张等待单不互判失效；协调会话不做失效推断、不报信号 9（Spec 验收 11–15）
  - 验证：`tests/test_hub.py` 的 StaleTicketTest 新用例：同一发件人经收件枢纽开两张【等待其他会话】都不失效、都计入阻塞与「还在等」、关一张另一张照旧开着；协调会话开单后发【等待用户】、【已恢复】不失效；`tests/test_health.py`：协调会话两张单不报信号 9、普通会话照旧报；A2 原有测试全部通过

## Checkpoint（gate）：修订 1 验收

- [ ] 全部测试通过；验收 11–14 各有测试证据；列出 Task 6 实际改动的文件
- [ ] 实测（验收 15，T4）放到联合演练，开始前另问用户
