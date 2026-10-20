# Todo: rules-dir-guard

- [x] Task 1：目录核对与 hub 拦下／提示（Spec 要做的 1；验收 1、2）
  - 验证：`tests/test_onboard.py` 新用例在 0714203 上失败、改后通过
  - 结果：HubDirGuardTest 6 项改前 5 项失败（没拦下、命令行退出 0）、改后通过；全量 1110 项通过，现有用例的目录布局没有要改的
- [x] Task 2：join 拦下／提示（要做的 1；验收 3）
  - 验证：同上
  - 结果：JoinDirGuardTest 3 项改前 2 项失败（没拦下、没提示）、改后通过；全量 1113 项通过
- [x] Task 3：`--drop-old`（hub 与 join；要做的 2；验收 4）
  - 验证：同上；旧文件除规则段外逐字不变
  - 结果：DropOldTest 7 项改前全部失败（没有 drop_old 参数、没有旧段提示、命令行不认 --drop-old）、改后通过；全量 1120 项通过
- [x] Task 4：doctor「上级目录的协作规则段」（要做的 3；验收 5）
  - 验证：`tests/test_doctor.py` 新用例在 0714203 上失败、改后通过
  - 结果：StrayBlockTest 4 项改前全部失败（没有这项检查）、改后通过；全量 1124 项通过
- [ ] Task 5：文档与版本 0.0.34（要做的 4）
  - 验证：全量 `PYTHONPATH=tests:. python3 -m unittest discover -s tests` 通过

## 检查点

- [ ] Checkpoint（gate）：模块最终验收——全部测试通过；列出实际改动的文件；临时目录复现实测场景；批准后开 PR
