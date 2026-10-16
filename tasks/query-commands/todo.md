# Todo: query-commands

测试命令：`python3 -m unittest discover -s tests -v`

- [ ] Task 1：relay-reader 返工——`parse_message_status`、`parse_wake_jobs`
  - 验收：Spec 验收 10。合成样例覆盖各字段和缺字段的情况；实采样例（不带参数一次、带一个消息编号一次）脱敏后能解析；结构不对抛 `RelayDataError`；解析结果和夹具里都没有 `preview`；relay-reader 原有测试不改动、全部通过
  - 验证：`python3 -m unittest discover -s tests -p test_relay.py -v`
  - 文件：`decision_inbox/relay.py`、`tests/test_relay.py`、`tests/fixtures/relay/`

- [ ] Task 2：等待图与 `/lines`
  - 验收：Spec 验收 1（按名册顺序、跳过收件枢纽；状态、当前模块与已勾数、最后产出、未读、在等；spec-guard 读不出写原因；未读未知；「你（#N）」；没有在等写「—」）
  - 验证：`python3 -m unittest discover -s tests -p test_query.py -v`
  - 文件：`decision_inbox/query.py`、`tests/test_query.py`

- [ ] Checkpoint 1（report）：全部测试全绿；记下实采样例与源码字段的差异（没有差异也记一句），然后继续

- [ ] Task 3：`/flow` 的源头选择、10 类归类与结论段
  - 验收：Spec 验收 2（环）、3（挡住最多、并列取最早、被它挡住含间接）、4（10 类各一个场景，另加两类同时满足时的顺序用例）、5（流畅）；「（HH:MM 起）」三种取法
  - 验证：`python3 -m unittest discover -s tests -p test_query.py -v`
  - 文件：`decision_inbox/query.py`、`tests/test_query.py`

- [ ] Task 4：`/flow` 的 5 项检查明细
  - 验收：Spec 验收 6（5 行都在；积压 10 分钟门槛的边界；叫醒没成功按 held、refused、unknown、expired 计数；漏抛的正例和两个反例；长期外部阻塞 60 分钟边界，并写「负责人跟进：第一版不记录」）
  - 验证：`python3 -m unittest discover -s tests -p test_query.py -v`
  - 文件：`decision_inbox/query.py`、`tests/test_query.py`

- [ ] Task 5：`/item`——`item_message_ids` 与时间线
  - 验收：Spec 验收 7（按时间排序；抛出、答复、转发、投递、确认、唤醒、恢复；缺状态写「agent-relay 查不到 #编号」；扫描输出无正文和 preview）、8（等待单的开单和关单；两边都没有）、9（去重、按先后排序）
  - 验证：`python3 -m unittest discover -s tests -p test_query.py -v`
  - 文件：`decision_inbox/query.py`、`tests/test_query.py`

- [ ] Task 6：命令行 `query` 的 4 个子命令与只读校验
  - 验收：Spec 验收 11（4 个子命令在临时文件上退出码 0；协作组不存在为 2；agent-relay 文件不是 JSON 为 3）、12（查询前后协作组目录里的文件哈希一致）；原有 `store` 子命令不受影响
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/__main__.py`、`tests/test_query.py`

- [ ] Checkpoint 2（gate）：模块最终验收——全部测试全绿、12 条验收标准逐条对应测试、贴出三个查询的样例输出、列出实际改动文件、给出 relay-reader 规格的修订内容；停下等用户确认
