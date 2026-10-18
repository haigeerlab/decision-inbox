# Todo: transition-compat

测试命令：`python3 -m unittest discover -s tests -v`

- [x] Task 1：契约升到 v1.7
  - 验收：Spec 验收 6
  - 文件：`tests/fixtures/session-protocol/v1.7/`（删掉 v1.5）、`tests/test_contract.py`、`tests/test_packaging.py`、`README.md`
  - 记录（2026-10-18）：
    - 样例从契约仓库复制。仓库 HEAD 是 ddbd448，比契约负责人给的 1e14a49 多一个提交，但那个提交只改了 conformance 登记，样例没变，这一点已核对。SOURCE 写 1e14a49。
    - 测试：`VERSION` 改为 v1.7；`NOT_PARSED` 加入 `owner-handoff`；按前缀跳过 `user-reply/relay-*`。计数断言改为解析 63、生成 6、跳过 26，结果和契约负责人给的一致。
    - README「消息协议」一节和打包测试同步改为 v1.7。
    - 全部测试：Ran 616 tests, OK

- [x] Task 2：`legacyFormat` 字段、`onboard enroll`、leave 只登记的条目
  - 验收：Spec 验收 1；验收 5 里 leave 的部分
  - 文件：`decision_inbox/store.py`、`decision_inbox/onboard.py`、`decision_inbox/__main__.py`、`tests/test_store_roster.py`、`tests/test_onboard.py`
  - 记录（2026-10-18）：
    - 先写用例：预览什么都不写；确认后只改协作组目录，`projects/` 下的文件一个都不碰，名册条目带 `legacyFormat`；负责人和总协调用 enroll 会报错；之后正式 join 时标记消失；leave 只登记的条目不报错，只记 `left`；字段只认布尔值，并且只能用于开发线。先跑，2 个失败、5 个报错。
    - 实现时多改了一处名册校验：开发线原本必须填 repo，旧格式条目例外。因为填了 repo，停止钩子就会按工作目录把它认出来，再用它不认识的约定去拦它。这一点 Plan 里没写到，已核对过：所有读 repo 的地方都先判断 `e.get("repo")`。
    - 新增：`onboard.enroll`、`_leave_enrolled`、`Outcome.file` 允许为 None、命令行 `onboard enroll`；命令行输出写「规则文件：无（只登记进名册，不写约定块）」。
    - 实测：在临时目录跑 `onboard enroll` 预览，退出码 0，输出和预期一致。
    - 全部测试：Ran 621 tests, OK

- [x] Task 3：输出旧写法；答复告知、多线事项跳过旧格式和已退出的会话
  - 验收：Spec 验收 2、3、5
  - 文件：`decision_inbox/protocol.py`、`decision_inbox/items.py`、`decision_inbox/hub.py`、`decision_inbox/store.py`、`tests/test_items.py`、`tests/test_hub.py`
  - 记录（2026-10-18）：
    - 先写用例：
      - 旧格式线的普通答复，首行是「事项：#5990（hub 编号 N）」；
      - 正式线的写法不变；
      - 多线答复：旧格式线收到「事项：#5948（多线事项，发起方 coord；hub 编号 N）」，正式线照旧；
      - 已退出的会话收不到多线答复；
      - 「适用会话」里写了已退出的会话，按 `scope-session-unknown` 退回；
      - 答复告知不发给旧格式线，也不发给已退出的会话。
    - 先跑：5 个失败。
    - 实现：
      - `store.left_relays`、`store.legacy_relays`；
      - `protocol.legacy_head`：只替换「事项：」这一行，其他字段沿用正式写法；
      - `items.answer` 按收件人选择写法；
      - 多线事项的范围核对把已退出的会话也算进去；
      - `hub._notices` 过滤旧格式线和已退出的会话。
    - 结果：Ran 627 tests, OK

- [x] Task 4：认旧编号；退回说明写双编号
  - 验收：Spec 验收 4
  - 文件：`decision_inbox/items.py`、`tests/test_items.py`
  - 记录（2026-10-18）：
    - 先写用例：
      - 旧格式线用自己的邮箱号写【取代 #5990】、【撤回】事项：#6000，都能生效；
      - 用别人的邮箱号写，照常按 not-owner 退回；
      - 正式线用邮箱号写，照旧退回并给出提示（按 v1.7）；
      - 旧格式线收到的自动取代提示写「#5990（hub 编号 N）」，并行标记写邮箱号。
    - 先跑：2 个失败。
    - 实现：
      - `_resolve_own`：先按 hub 编号找；是旧格式线时，再在本人还没结束的事项里按 relayId 找；
      - `_label`：双编号写法；
      - 取代、撤回、自动取代提示都走这两个函数。
    - 结果：Ran 631 tests, OK

- [ ] Task 5：约定块写明【负责人转交】
  - 验收：Spec 验收 7
  - 文件：`decision_inbox/onboard.py`、`tests/test_onboard.py`

- [ ] Task 6：文档和版本 0.0.17
  - 验收：Spec 验收 8
  - 文件：`README.md`、`commands/leave.md`、两份 `plugin.json`、`tests/test_packaging.py`

### Checkpoint（gate）：模块最终验收

- [ ] 全部测试通过；每条验收标准都有证据；列出实际改动的文件
