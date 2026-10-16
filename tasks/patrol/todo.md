# Todo: patrol

测试命令：`python3 -m unittest discover -s tests -v`

- [x] Task 1：group-store 返工——`desktopSession` 可选字段
  - 验收：Spec 验收 12（不是 `local_` 开头的字符串时拒绝登记；不填照常）；group-store 原有测试不改动、全部通过
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/store.py`、`tests/test_store_roster.py`

- [ ] Task 2：`plan`、`record`、去重记录与叫醒
  - 验收：
    - Spec 验收 1：叫醒 → 叫不醒通知 → 不再重复 → 上线后清记录；
    - Spec 验收 2：没登记 `desktopSession` 直接通知；Codex 不出动作；
    - Spec 验收 7：收件枢纽停着且有通知时一并叫醒；
    - Spec 验收 10：同一 `now` 连跑两轮，第二轮没有动作；
    - Spec 验收 11：`plan` 前后文件哈希一致；`record` 只改领域 `patrol`，并写 `patrol.run` 事件。
  - 验证：`python3 -m unittest discover -s tests -p test_patrol.py -v`
  - 文件：`decision_inbox/patrol.py`、`tests/test_patrol.py`

- [ ] Checkpoint 1（report）：全部测试全绿，记下命令与结果后继续

- [ ] Task 3：进度预警与 30 分钟升级
  - 验收：
    - Spec 验收 3：信号 3、6、7、8、9 各出一次预警；30 分钟内不重复；30 分钟后升级一次；信号消失后清记录，再出现时重新开始；
    - Spec 验收 4：没有负责人、负责人离线、预警记为失败时，改为通知用户；
    - 预警文字按规格：说明加 hub-view 的建议句。
  - 验证：`python3 -m unittest discover -s tests -p test_patrol.py -v`
  - 文件：`decision_inbox/patrol.py`、`decision_inbox/view.py`、`tests/test_patrol.py`

- [ ] Task 4：给用户的通知
  - 验收：
    - Spec 验收 5：信号 1 只通知一次，消失后再出现再通知；信号 2、5、10 不出动作；
    - Spec 验收 6：挡住线的事项 30 分钟时提醒，29 分钟时不提醒；答复后清记录；
    - Spec 验收 8：每轮最多 3 条，其余合并为「还有 N 件事」；
    - Spec 验收 9：读不到 agent-relay 时其余照常检查，通知一次，恢复后清掉；
    - 通知文字以「decision-inbox：」开头、以「详见收件枢纽」结尾，不含 agent-relay 消息编号。
  - 验证：`python3 -m unittest discover -s tests -p test_patrol.py -v`
  - 文件：`decision_inbox/patrol.py`、`tests/test_patrol.py`

- [ ] Task 5：命令行 `patrol plan`、`record`、`prompt`
  - 验收：Spec 验收 13（plan 写出计划文件、退出码 0；record 按计划文件和结果记账；prompt 含三步和三种动作的工具名；协作组不存在时退出码 2；agent-relay 文件读不出时，plan 仍然写出计划并含「读不到 agent-relay」通知）；原有子命令不受影响
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/__main__.py`、`tests/test_patrol.py`

- [ ] Checkpoint 2（report）：全部测试全绿；在 scratchpad 的临时协作组上用命令行实跑一轮 plan 和 record，记下计划文件和状态变化，然后继续

- [ ] Task 6：实测桌面通知与 `bridge_send`
  - 验收：Spec 验收 14。先问用户：建一个一次性任务，发一条测试桌面通知，并给专门的测试身份发一条预警样例消息；结果写进 `spec/patrol.md` 的实测记录
  - 验证：任务运行记录、你是否看到通知、测试身份的收件箱
  - 文件：`spec/patrol.md`

- [ ] Checkpoint 3（gate）：模块最终验收——全部测试全绿、14 条验收标准逐条有测试或实测记录、列出实际改动文件、原样附上规格差异；停下等用户确认
