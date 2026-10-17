# Todo: doctor-and-observer

测试命令：`python3 -m unittest discover -s tests -v`

- [ ] Task 1：deps.py 与 spec-guard 按接口说明读
  - 验收：Spec 验收 2（命令取自 interface.json；缺失、读不懂退回原入口；主版本不兼容不读能力图并写明原因；都不说成没装）
  - 验证：`python3 -m unittest discover -s tests -p test_specguard.py -v`
  - 文件：`decision_inbox/deps.py`、`specguard.py`、对应测试

- [ ] Task 2：delegate、agent-relay 接口读取与审查对照表
  - 验收：Spec 验收 3、4
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/deps.py`、`mapview.py`、对应测试

- [ ] Task 3：doctor 命令、`--json`、`--report`
  - 验收：Spec 验收 1
  - 验证：`python3 -m unittest discover -s tests -p test_doctor.py -v`
  - 文件：`decision_inbox/doctor.py`、`__main__.py`、对应测试

- [ ] Checkpoint 1（report）：全部测试全绿，记下命令与结果后继续

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
