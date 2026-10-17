# Todo: doctor-and-observer

测试命令：`python3 -m unittest discover -s tests -v`

- [x] Task 1：deps.py 与 spec-guard 按接口说明读
  - 验收：Spec 验收 2（命令取自 interface.json；缺失、读不懂退回原入口；主版本不兼容不读能力图并写明原因；都不说成没装）
  - 验证：`python3 -m unittest discover -s tests -p test_specguard.py -v`
  - 文件：`decision_inbox/deps.py`、`specguard.py`、对应测试
  - 记录（2026-10-17）：4 个新测试先失败（2 失败 2 报错）；实现后 Ran 516 tests, OK。和计划的差别：不兼容时 `locate` 返回新类型 `Incompatible`，`read_line` 给新状态 `incompatible`（显示走原因文字，调用方不用改）；interface.json 里 mapView 的 schemaVersion 不是 1 也按不兼容处理

- [x] Task 2：delegate、agent-relay 接口读取与审查对照表
  - 验收：Spec 验收 3、4
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/deps.py`、`mapview.py`、对应测试
  - 记录（2026-10-17）：新测试 5 个先报错；实现后 2 个原有整表测试按新对照表失败（✔／— 改为通过／不适用），改期望后 Ran 521 tests, OK。`ModuleFact` 多了 `external_review`（默认 none）；delegate 命令名不合 `/delegate:小写-连字符` 时用默认值

- [x] Task 3：doctor 命令、`--json`、`--report`
  - 验收：Spec 验收 1
  - 验证：`python3 -m unittest discover -s tests -p test_doctor.py -v`
  - 文件：`decision_inbox/doctor.py`、`__main__.py`、对应测试
  - 记录（2026-10-17）：测试先于实现写好（模块不存在时全部报错）；实现后两处变异检查（不比较约定块、总做 Codex 信任检查）都被测试抓到。在 di-e2e 上实跑发现 agent-relay 报成 0.6.1：Claude 对目录型插件市场直接读源目录，安装记录里的版本是旧的；`deps.find` 改为先看 `known_marketplaces.json`，目录型市场取源目录里的插件（补 2 个测试，先失败后通过）。Ran 534 tests, OK。实跑结果：约定块 4 份都是当前版本、两条 Codex 线能加载；巡视 350 分钟没跑（异常）；Codex 里没有 decision-inbox 钩子的信任记录（未知）；三个依赖插件都兼容（agent-relay 0.8.2 接口 2.5、spec-guard 0.67.0 接口 1.0、delegate 0.5.3 接口 1.0）

- [x] Checkpoint 1（report）：全部测试全绿，记下命令与结果后继续
  - 记录（2026-10-17）：`python3 -m unittest discover -s tests` → Ran 534 tests, OK

- [ ] Task 4：`query stats` 与 `query events --json`
  - 验收：Spec 验收 5
  - 验证：`python3 -m unittest discover -s tests -p test_query.py -v`
  - 文件：`decision_inbox/query.py`、`__main__.py`、对应测试

- [ ] Task 5：hub-setup 一次性权限放行
  - 验收：Spec 验收 6（不带 --confirm 不写；带了只写收件枢纽目录的本地设置文件；已有条目保留、不重复）
  - 验证：`python3 -m unittest discover -s tests -p test_onboard.py -v`
  - 文件：`decision_inbox/onboard.py`、`__main__.py`、对应测试

- [ ] Task 6：来源标注
  - 验收：Spec 验收 7
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/health.py`、`patrol.py`、`view.py`、对应测试

- [ ] Checkpoint 2（report）：全部测试全绿；scratchpad 临时协作组命令行实跑 doctor、stats、权限预览，记下输出；推送本分支

- [ ] Task 7：宿主差异文档、README 使用注意事项、版本 0.0.7
  - 验收：Spec 验收 8、9
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`docs/host-differences.md`、`README.md`、两份 `plugin.json`

- [ ] Task 8：实测 S1、S3
  - 验收：Spec 验收 10
  - 说明：先问用户

- [ ] Checkpoint 3（gate）：模块最终验收，等用户确认
