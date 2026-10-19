# Todo: my-waits

- [x] Task 1：渲染「我在等什么／谁在等我」（Spec 要做的 1；验收 1～4）
  - 验证：`tests/test_query.py` 新用例在 11384b3 上失败、改后通过
  - 结果：WaitsTest 5 项改前全部报错（没有 render_waits）、改后通过；名字不在名册时抛 ValueError
- [x] Task 2：命令行 `query waits` 与 `/decision-inbox:waits`（要做的 2、3；验收 5）
  - 验证：同上；状态目录前后一致
  - 结果：命令行用例与打包测试改前 2 项失败、改后通过；带／不带 --agents 运行前后状态目录逐字节一致；名字不在名册退出 2
- [x] Task 3：README 与版本 0.0.33（要做的 4）
  - 验证：全量 `PYTHONPATH=tests:. python3 -m unittest discover -s tests` 通过
  - 结果：README「查询命令」加 /waits、0.0.33 升级说明；两份 plugin.json 升到 0.0.33；全量通过

## 检查点

- [ ] Checkpoint（gate）：模块最终验收——全部测试通过；列出实际改动的文件；本机对 di-p0 实跑一次；批准后开 PR
