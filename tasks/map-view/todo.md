# Todo: map-view

测试命令：`python3 -m unittest discover -s tests -v`

- [x] Task 1：返工——【审查结论】的「模块」字段、review-registry 记模块与 `module_reviews`
  - 验收：Spec 验收 11（写了「模块」时解析出来，没写为 None；模块取最近一次写了模块的那一轮；旧记录缺 `module` 读作 None；`module_reviews` 按模块分组、未标模块的单列）；message-protocol、review-registry 原有测试不改动、全部通过
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/protocol.py`、`decision_inbox/reviews.py`、`tests/test_protocol.py`、`tests/test_reviews.py`

- [x] Task 2：状态、Spec/Plan 评审、架构审查三列的写法
  - 验收：Spec 验收 2（6 种状态，in_progress 的 spec、plan、build 三种 step；挂起没原因写「未记原因」）、3（5 种评审标记）、4 的列内部分（两个节点用「 · 」连接；有须修改项写轮数；附建议写条数；没结论写「—」）
  - 验证：`python3 -m unittest discover -s tests -p test_mapview.py -v`
  - 文件：`decision_inbox/mapview.py`、`tests/test_mapview.py`

- [x] Checkpoint 1（report）：全部测试全绿，记下命令与结果后继续
  - 记录：`python3 -m unittest discover -s tests -v` → Ran 266 tests, OK（2026-10-16）

- [x] Task 3：表头 3～4 行与备注
  - 验收：Spec 验收 4 的表头部分（本线无审查者、未标模块计数）、6（外部等待写进当前模块备注，没有当前模块时写表头，等用户的单不算）、7（本线发起的与多线事项都列，没有就不出现）；关键卡点多个用「；」连接，没有写「无」；未合入、未推送为 null 时写「判断不了」
  - 验证：`python3 -m unittest discover -s tests -p test_mapview.py -v`
  - 文件：`decision_inbox/mapview.py`、`tests/test_mapview.py`

- [ ] Task 4：折叠与整表
  - 验收：Spec 验收 1（完整期望文本逐字一致）、5（最近完成取 `lastTickAt` 最晚的，没有时取位次最大的；合并行的位次范围，只有一个模块时写一个数；`全部` 时没有合并行）；作用列超过 40 字截断；`map-0.63.json` 夹具能排出整表
  - 验证：`python3 -m unittest discover -s tests -p test_mapview.py -v`
  - 文件：`decision_inbox/mapview.py`、`tests/test_mapview.py`

- [ ] Task 5：`/map all`、选线、读不出能力图
  - 验收：Spec 验收 8（每条开发线一行、读不出写原因、按名册顺序）、9（短名和身份名都能选，对不上时列出现有的线）、10（一行原因，加上这条线的待答事项和外部等待）
  - 验证：`python3 -m unittest discover -s tests -p test_mapview.py -v`
  - 文件：`decision_inbox/mapview.py`、`tests/test_mapview.py`

- [ ] Task 6：命令行 `map` 子命令与只读校验
  - 验收：Spec 验收 12（三种调用退出码 0；协作组不存在为 2；参数错为 2；运行前后协作组文件哈希一致）；原有 `store`、`query` 子命令不受影响
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/__main__.py`、`tests/test_mapview.py`

- [ ] Checkpoint 2（gate）：模块最终验收——全部测试全绿、12 条验收标准逐条对应测试、贴出三种样例输出、列出实际改动文件、给出两份上游规格的修订内容；停下等用户确认
