# Todo: wait-tickets

测试命令：`python3 -m unittest discover -s tests -v`

- [x] Task 1：登记与理由 1、2
  - 验收：Spec 验收 1（登记、不合格不登记）、2（理由 1、别人的【已恢复】给 `not-own-ticket`）、3（理由 2，含【等待用户】的结束行；「结束：无」不关）、8（`unknown-target`）；结束行写事项编号时不动事项也不报错
  - 验证：`python3 -m unittest discover -s tests -p test_tickets.py -v`
  - 文件：`decision_inbox/tickets.py`、`tests/test_tickets.py`

- [x] Task 2：理由 3、4
  - 验收：Spec 验收 4（转达并记下发送编号后才关，依据「已转发 #编号」）、5（用户关闭、带原因、不存在或已关时 ValueError）
  - 验证：`python3 -m unittest discover -s tests -p test_tickets.py -v`
  - 文件：`decision_inbox/tickets.py`、`tests/test_tickets.py`

- [x] Checkpoint 1（report）：全部测试全绿，记下命令与结果后继续
  - 记录：`python3 -m unittest discover -s tests -v` → Ran 139 tests, OK（2026-10-16）

- [ ] Task 3：提醒标记
  - 验收：Spec 验收 6（14／15／60 分钟，按发出时间算）、7（离线立即标、提示含条数与 HH:MM；不传 relay 不判断离线）
  - 验证：`python3 -m unittest discover -s tests -p test_tickets.py -v`
  - 文件：`decision_inbox/tickets.py`、`tests/test_tickets.py`

- [ ] Task 4：今天已关闭与计数
  - 验收：Spec 验收 9（按本机时区的日期、计数、已关闭仍保留）、10（快照与事件一致）
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/tickets.py`、`tests/test_tickets.py`

- [ ] Checkpoint 2（gate）：模块最终验收——全部测试全绿、10 条验收标准逐条对应测试、列出实际改动文件；停下等用户确认
