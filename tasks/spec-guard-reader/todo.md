# Todo: spec-guard-reader

测试命令：`python3 -m unittest discover -s tests -v`

- [x] Task 1：按安装记录找脚本
  - 验收：Spec 验收 1（用户级；项目级优先）、2（记录文件不存在、没有 spec-guard 条目、脚本不存在各给不同原因）
  - 验证：`python3 -m unittest discover -s tests -p test_specguard.py -v`
  - 文件：`decision_inbox/specguard.py`、`tests/test_specguard.py`

- [ ] Task 2：解析 JSON 为 LineMap
  - 验收：Spec 验收 3（字段一致、按 position 排序、忽略未知字段）、7（0.62 形状）、8（unmerged／unpushed 为 null 时记 None）；schemaVersion 为 2 与非 JSON 的解析结果
  - 验证：`python3 -m unittest discover -s tests -p test_specguard.py -v`
  - 文件：`decision_inbox/specguard.py`、`tests/test_specguard.py`、`tests/fixtures/specguard/map-0.63.json`、`tests/fixtures/specguard/map-0.62.json`

- [ ] Checkpoint 1（report）：全部测试全绿，记下命令与结果后继续

- [ ] Task 3：子进程调用与结果分类
  - 验收：Spec 验收 4（退出码 2／3／4／1）、5（非 JSON、版本 2）、6（超时）、9（路径不对不启动子进程）、11（无 shell=True）
  - 验证：`python3 -m unittest discover -s tests -p test_specguard.py -v`
  - 文件：`decision_inbox/specguard.py`、`tests/test_specguard.py`

- [ ] Task 4：本机 spec-guard 集成测试
  - 验收：Spec 验收 10（读本仓库得 ok、版本与安装记录一致；没装时跳过）
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`tests/test_specguard.py`

- [ ] Checkpoint 2（gate）：模块最终验收——全部测试全绿、11 条验收标准逐条对应测试、列出实际改动文件；停下等用户确认
