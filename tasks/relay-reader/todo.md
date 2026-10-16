# Todo: relay-reader

测试命令：`python3 -m unittest discover -s tests -v`

- [x] Task 1：`parse_agents` 基础解析
  - 验收：Spec 验收 4（8 种在线状态归类、原值保留）、5（正文字段不出现在输出与 repr）、6（缺 name 跳过并警告；坏 JSON、缺 agents 数组抛 RelayDataError）、8（退役身份）、9（不 import 网络与子进程模块）
  - 验证：`python3 -m unittest discover -s tests -p test_relay.py -v`
  - 文件：`decision_inbox/relay.py`、`tests/test_relay.py`、`tests/fixtures/relay/agents-0.6.10.json`、`tests/fixtures/relay/agents-edge.json`

- [x] Task 2：版本判定
  - 验收：Spec 验收 1、2（含新版里广播未读、无 waiting 不误报）、3（未定与显式版本）
  - 验证：`python3 -m unittest discover -s tests -p test_relay.py -v`
  - 文件：`decision_inbox/relay.py`、`tests/test_relay.py`、`tests/fixtures/relay/agents-empty.json`

- [x] Task 3：`parse_outbox`
  - 验收：Spec 验收 7；`preview` 内容不出现在输出；缺 entries 数组抛 RelayDataError；缺 id 的条目跳过并警告
  - 验证：`python3 -m unittest discover -s tests -p test_relay.py -v`
  - 文件：`decision_inbox/relay.py`、`tests/test_relay.py`、`tests/fixtures/relay/outbox-0.6.10.json`

- [x] Checkpoint 1（report）：全部测试全绿，记下命令与结果后继续
  - 记录：`python3 -m unittest discover -s tests -v` → Ran 46 tests, OK（2026-10-16）

- [ ] Checkpoint 2（gate）：停下请用户升级本机 agent-relay 到 0.6.10，并允许调用 bridge_agents 与 bridge_outbox 采集原文

- [ ] Task 4：真实原文核对
  - 验收：脱敏后的真实原文经用户过目后存为夹具；两个解析函数对它们无报错、字段与原文一致；夹具不含 `preview` 键与原始身份名；与构造夹具的差异已修正并记入 plan
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`tests/fixtures/relay/real-agents.json`、`tests/fixtures/relay/real-outbox.json`、`tests/test_relay.py`，可能 `decision_inbox/relay.py`

- [ ] Checkpoint 3（gate）：模块最终验收——全部测试全绿、9 条验收标准逐条对应测试、列出实际改动文件；停下等用户确认
