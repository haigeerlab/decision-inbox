# Todo: stop-hook

测试命令：`python3 -m unittest discover -s tests -v`

- [x] Task 1：`decide`——认会话、四种放行、拦下与说明
  - 验收：
    - Spec 验收 1：拦下时 `reason` 格式一致，多张单按单号排序；
    - Spec 验收 2：`stop_hook_active` 为 true 时放行；
    - Spec 验收 3：本会话自己开着等待单、或有完全停住的待答事项时放行；
    - Spec 验收 4：没人在等、或等的是用户时放行；
    - Spec 验收 5：`--session` 优先；`cwd` 等于 `repo` 或在它下面；对不上、对上多个时放行，`note` 写原因；
    - 「已等」的写法挪到 hub-view 后，map-view 的原有测试全部通过。
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/stophook.py`、`decision_inbox/view.py`、`decision_inbox/mapview.py`、`tests/test_stophook.py`

- [ ] Task 2：命令行 `hook stop`
  - 验收：
    - Spec 验收 6：协作组不存在、输入不是 JSON、状态读不出时，退出码 0、stdout 为空、stderr 有一行原因；
    - Spec 验收 7：拦下时 stdout 是含 `decision`、`reason` 的 JSON 对象，放行时 stdout 为空，退出码都为 0；
    - Spec 验收 8：运行前后协作组文件的哈希一致；
    - 用子进程实跑，不只调用函数。
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/__main__.py`、`tests/test_stophook.py`

- [ ] Checkpoint 1（report）：全部测试全绿；记下一次子进程实跑的 stdout 和 stderr，然后继续

- [ ] Task 3：Claude 桌面版实测
  - 验收：Spec 验收 9（拦下后同一轮继续并收到 `reason`；第二次 `stop_hook_active` 为 true 时放行）。按 plan「实测方案」做，开会话前先问用户；结果写进 `spec/stop-hook.md` 的「实测记录」一节
  - 验证：实测日志和会话记录
  - 文件：`spec/stop-hook.md`（scratchpad 里的测试项目不提交）

- [ ] Checkpoint 2（gate）：模块最终验收——全部测试全绿、9 条验收标准逐条有测试或实测记录、列出实际改动文件、给出规格修订内容；停下等用户确认
