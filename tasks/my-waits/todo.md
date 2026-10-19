# Todo: my-waits

- [ ] Task 1：渲染「我在等什么／谁在等我」（Spec 要做的 1；验收 1～4）
  - 验证：`tests/test_query.py` 新用例在 11384b3 上失败、改后通过
- [ ] Task 2：命令行 `query waits` 与 `/decision-inbox:waits`（要做的 2、3；验收 5）
  - 验证：同上；状态目录前后一致
- [ ] Task 3：README 与版本 0.0.33（要做的 4）
  - 验证：全量 `PYTHONPATH=tests:. python3 -m unittest discover -s tests` 通过

## 检查点

- [ ] Checkpoint（gate）：模块最终验收——全部测试通过；列出实际改动的文件；本机对 di-p0 实跑一次；批准后开 PR
