# Todo: launcher-own-code

- [x] Task 1：启动脚本只跑自己的代码（Spec 要做的 1、2；验收 1、2、3）
  - 验证：`tests/test_packaging.py` 新用例在 85debcf 上失败、改后通过；全量测试通过；3.10 手工复核
  - 结果：新用例在 85debcf 上失败（当前目录的 runpy.py 劫持了 `-m`）、改后通过；只放假包时改前跑出 FAKE-PACKAGE；全量 1073 项通过；3.10.7 下临时目录里 `whoami` 报的是调用者目录

## 检查点

- [x] Checkpoint（gate）：模块最终验收——全部测试通过；列出实际改动的文件；批准后开 PR（用户 2026-10-20 批准；1073 项测试通过）

## 外部审查意见

<!-- spec-guard: external-review declined -->
