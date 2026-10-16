# Todo: hub-loop

测试命令：`python3 -m unittest discover -s tests -v`

- [x] Task 1：relay-reader 返工——`parse_inbox`
  - 验收：按 agent-relay 0.7.0 源码字段解析 `agent`、`messages`、`hasMore`；没读全的消息标 `truncated` 并带 `nextOffset`；缺 `id` 或 `fromAgent` 的记警告并跳过；不是 JSON 或没有 `messages` 时抛 `RelayDataError`；原有 relay 测试不改动、全部通过
  - 验证：`python3 -m unittest discover -s tests -p test_relay.py -v`
  - 文件：`decision_inbox/relay.py`、`tests/test_relay.py`、`tests/fixtures/relay/inbox.json`、`tests/fixtures/relay/inbox-truncated.json`

- [x] Task 2：`hub.receive` 分发、去重、没读全与 `bridge` 通知
  - 验收：
    - Spec 验收 1：七类消息各一条，分别入表、退回、开单、关单并结束事项、记一轮、告诉用户；`ack` 列出全部 7 条；
    - Spec 验收 2：同一批再交一次，没有新编号、没有要发的消息，`ack` 照列；
    - Spec 验收 3：没读全的不处理、不进 `ack`，说明怎样读全；`hasMore` 时提示再读一页；
    - Spec 验收 4：「结束：#旧编号」的【等待用户】入表，旧等待单按理由 2 关掉；
    - Spec 验收 5：【等待其他会话】缺「等什么」时退回，不开单；
    - 时间按消息的 `createdAt` 记。
  - 验证：`python3 -m unittest discover -s tests -p test_hub.py -v`
  - 文件：`decision_inbox/hub.py`、`tests/test_hub.py`

- [x] Checkpoint 1（report）：全部测试全绿，记下命令与结果后继续
  - 记录（2026-10-16）：`python3 -m unittest discover -s tests -v` → Ran 332 tests in 6.772s, OK。Task 2 的测试先因模块不存在而失败（只是导入失败）；补做两处变异检查（去掉去重、不跳过没读全的消息），各被 1 个测试抓住

- [x] Task 3：要发的消息留存与 `hub.sent`
  - 验收：
    - Spec 验收 8：答复发成后事项记下发送编号；等用户答复的等待单按理由 3 关掉；正文文件保留（规格已改，待复审）；
    - Spec 验收 9（状态部分）：失败的、没记结果的消息留着，`outgoing` 列出它们；不存在的编号抛错。
  - 验证：`python3 -m unittest discover -s tests -p test_hub.py -v`
  - 文件：`decision_inbox/hub.py`、`tests/test_hub.py`

- [x] Task 4：`hub.reply` 的识别与答复
  - 验收：
    - Spec 验收 6：「12 B」生成答复、`replyTo` 为原事项编号；多线事项另给各适用会话一条；对不上的回复返回问题、不发消息、事项仍在待答；
    - Spec 验收 7：「12 详情」「看等待」「看已关闭」「看已关闭 2026-10-15」「看失效」「关掉 #5 已经不需要」「关掉 #12」（事项）各得对应显示或问题；「N 原文」显示认不出类型的那条全文；
    - Spec 验收 9（重发部分）：「重发」再列出没发出去的消息；
    - 用户原话含换行、全角标点、引号时，答复正文一字不差。
  - 验证：`python3 -m unittest discover -s tests -p test_hub.py -v`
  - 文件：`decision_inbox/hub.py`、`tests/test_hub.py`

- [x] Task 5：约定块 `hub.convention`
  - 验收：Spec 验收 11（BEGIN/END 标记、协作组名、两个流程的命令、需求 4.6 的边界、改规则发前确认收件人）
  - 验证：`python3 -m unittest discover -s tests -p test_hub.py -v`
  - 文件：`decision_inbox/hub.py`、`tests/test_hub.py`

- [x] Task 6：命令行 `inbox receive|reply|sent|convention` 与 `view`
  - 验收：
    - 每个子命令打印 JSON 或文字、退出码按规格（0／2／3）；
    - Spec 验收 9：`view` 第一行提示没发出去的消息；`sent` 里不存在的编号退出码 2；
    - Spec 验收 10：`view --outbox` 推进投递状态；`--agents` 读不出时仍显示，第一行写读不到；
    - Spec 验收 12：原有子命令和测试不受影响。
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/__main__.py`、`tests/test_hub.py`

- [x] Checkpoint 2（report）：全部测试全绿；在 scratchpad 的临时协作组上用样例文件跑一遍命令行，记下输出后继续
  - 记录（2026-10-17）：`python3 -m unittest discover -s tests -v` → Ran 357 tests in 8.072s, OK。scratchpad 临时协作组 cp2 实跑：receive 收下 #1 事项和 #2 等待单（等用户答复 #1），退出码 0；reply「1 A」生成 out:1，replyTo 5001，正文文件是【用户答复】；sent out:1=9001 关掉等待单 #2（理由 3）；view 第一行写读不到 agent-relay，总览「刚转达：1 → 前端」；store show 一致性正常。实跑发现同一条格式提示报了两次（待答表和等待单都带回了消息层面的提示），补测试后在 hub.receive 去重
  - 补记 Task 3：`3d21019` 提交时全量测试有 1 个失败（静态扫描禁止删除调用，规格写了「删掉正文文件」，和协作组文件永久保留的规定冲突），是检查与提交串在一条命令里没拦住；`2437d60` 改为保留正文文件，规格和计划同步修订，待最终验收复审

- [x] Task 7：实测一轮
  - 验收：Spec 验收 13。先问用户：本会话扮演收件枢纽，给专门的测试身份发一条【等待用户】，跑一遍收件 → 答复 → 发送 → 记账 → 主视图；用真实的 `bridge_inbox` 返回核对 `parse_inbox`；结果写进 `spec/hub-loop.md` 的实测记录
  - 验证：命令输出、测试身份的收件箱、主视图
  - 文件：`spec/hub-loop.md`
  - 记录（2026-10-17 00:04–00:06）：经用户同意，用测试身份 di-hub-probe、di-dev-probe 跑通一轮（消息 3982、3983），正文逐字一致、replyTo 正确、状态推进到 acknowledged。发现 bridge_outbox 默认不列已确认消息，约定块改为带 includeAcknowledged: true（先补测试再改）；真实返回存为 real-inbox.json 样例。详见规格实测记录

- [ ] Checkpoint 3（gate）：模块最终验收——全部测试全绿、13 条验收标准逐条有测试或实测记录、列出实际改动文件、原样附上规格差异；停下等用户确认
