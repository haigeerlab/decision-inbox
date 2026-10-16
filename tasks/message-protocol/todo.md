# Todo: message-protocol

测试命令：`python3 -m unittest discover -s tests -v`

- [x] Task 1：解析骨架与简单消息
  - 验收：类型识别与 `unknown-kind`；开头三种行顺序不限、字段之后的「结束：」不算；【已恢复】多编号与「无编号（原因）」、缺结束行 `missing-end`；【撤回】与【取代 #N】【与 #N 并行】标记；【等待其他会话】必填；全角半角冒号与跨行字段值（Spec 验收 6、7、8、12、11 部分）
  - 验证：`python3 -m unittest discover -s tests -p test_protocol.py -v`
  - 文件：`decision_inbox/protocol.py`、`tests/test_protocol.py`、`tests/fixtures/protocol/wait-session.txt`、`tests/fixtures/protocol/resumed.txt`

- [ ] Task 2：【等待用户】必填字段与选项解析
  - 验收：Spec 验收 1、2、3；选项字母 `A：` `A.` `A、` `A)` 都能解析；正文里出现「来自：」不被误切
  - 验证：`python3 -m unittest discover -s tests -p test_protocol.py -v`
  - 文件：`decision_inbox/protocol.py`、`tests/test_protocol.py`、`tests/fixtures/protocol/wait-user.txt`

- [ ] Task 3：多线事项的适用会话与各线范围
  - 验收：Spec 验收 4（`scope-missing`、`scope-unknown`、`missing-field:各线范围`，写齐时原样保留）
  - 验证：`python3 -m unittest discover -s tests -p test_protocol.py -v`
  - 文件：`decision_inbox/protocol.py`、`tests/test_protocol.py`、`tests/fixtures/protocol/wait-user-multiline.txt`

- [ ] Task 4：架构审查状态行
  - 验收：Spec 验收 5（五种写法、审查编号、建议条数、`unrecognized` 保留原文、`absent`，都不产生问题）
  - 验证：`python3 -m unittest discover -s tests -p test_protocol.py -v`
  - 文件：`decision_inbox/protocol.py`、`tests/test_protocol.py`

- [ ] Checkpoint 1（report）：全部测试全绿，记下命令与结果后继续

- [ ] Task 5：生成【用户答复】与多线版本
  - 验收：Spec 验收 9、10；往返后用户原话逐字相同（含换行、全角标点、#）
  - 验证：`python3 -m unittest discover -s tests -p test_protocol.py -v`
  - 文件：`decision_inbox/protocol.py`、`tests/test_protocol.py`

- [ ] Checkpoint 2（gate）：模块最终验收——全部测试全绿、12 条验收标准逐条对应测试、问题代码表与 Spec 一致、列出实际改动文件；停下等用户确认
