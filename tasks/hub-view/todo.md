# Todo: hub-view

测试命令：`python3 -m unittest discover -s tests -v`

- [x] Task 1：返工——补 detail、mentions、两个读取函数
  - 验收：`AgentFact.presence_detail` 取 `presence.detail`，没有或空串为 None；收单后事项的 `review.mentions` 与 `display_label` 给的一致，旧记录缺字段时读作空；`items.get` 取到事项（带 `no`），编号不存在返回 None；`items.by_status(g, "superseded", "withdrawn")` 只列这两种状态、按编号排序；relay-reader 和 decision-queue 原有测试不改动、全部通过
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/relay.py`、`decision_inbox/items.py`、`tests/test_relay.py`、`tests/test_items.py`

- [x] Task 2：零件——时间写法、截断、复制块、第一行推送、「各线」、总览、最后一行计数
  - 验收：Spec 验收 1（空状态只有三部分）、3（全线停住与「卡在哪见 /flow」，含并列时）、7（刚转达 10 分钟内列、11 分钟不列；多个用「、」，多收件人用「＋」）、8（59 分钟 / 60 分钟 / 25 小时）；复制块三种写法（已定事项 8）；「阻塞：等 X」去空格
  - 验证：`python3 -m unittest discover -s tests -p test_view.py -v`
  - 文件：`decision_inbox/view.py`、`tests/test_view.py`

- [x] Checkpoint 1（report）：全部测试全绿，记下命令与结果后继续
  - 记录：`python3 -m unittest discover -s tests -v` → Ran 200 tests, OK（2026-10-16）

- [x] Task 3：两种卡片与审查行
  - 验收：Spec 验收 4（等你确认卡片计数、排最前、无 detail 不写括号）、5（推荐排第一、单一代码块、无推荐无代码块无「推荐」、30 字截断、缺后果、多线来源、挡住 0 条省略、标题主题 20 字截断）、6（审查中加粗、未标审查列「正文提到：」）
  - 验证：`python3 -m unittest discover -s tests -p test_view.py -v`
  - 文件：`decision_inbox/view.py`、`tests/test_view.py`

- [x] Task 4：异常区与完整主视图
  - 验收：Spec 验收 2（与规格样例逐字一致）、9（信号 2～10 各一行按建议表；信号 1 不进异常区、不计入「异常 N」）、11（扫描主视图：不含 agent-relay 消息编号、文件路径）
  - 验证：`python3 -m unittest discover -s tests -p test_view.py -v`
  - 文件：`decision_inbox/view.py`、`tests/test_view.py`

- [x] Task 5：4 种展开视图
  - 验收：Spec 验收 10。每行格式：
    - 「编号 详情」：标题 `#12 详情 · 来源 · 收到于 HH:MM`；`agent-relay 消息编号：N`（已转达的再列答复的发送编号）；多线事项逐行列「各线范围：短名：范围」；最后是原文全文
    - 「看等待」：`#31 前端 等 API：等什么 · 已等 N 分钟`，后接 wait-tickets 给的提醒标记原文；没有开着的单时写「没有开着的等待单」
    - 「看已关闭」：`#31 前端 等 API：等什么 · <理由名> · 依据：<依据> · HH:MM 关`；理由名按 wait-tickets 的四种（对方明说结束 / 被取代 / 所等的事已发生 / 用户关闭）
    - 「看失效」：`#7 已取代（被 #12 取代）· 来源 · 主题` 或 `#8 已撤回（原因）· 来源 · 主题`；原因取 decision-queue 的事件记录
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/view.py`、`tests/test_view.py`

- [ ] Checkpoint 2（gate）：模块最终验收——全部测试全绿、11 条验收标准逐条对应测试、贴出完整样例输出、列出实际改动文件、给出两份上游规格的修订内容；停下等用户确认
