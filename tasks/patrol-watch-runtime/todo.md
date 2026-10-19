# Todo: patrol-watch-runtime

- [x] Task 1：运行副本的复制与刷新（Spec 要做的 1、4）
  - 验证：`tests/test_watch.py` 新用例在 c4d97ca 上失败、改后通过
  - 结果：RuntimeTest 3 项改前全部报错（没有 runtime_dir/write_runtime）、改后通过
- [x] Task 2：plist 跑运行副本、带 PATH，受保护目录拒绝（要做的 2、4）
  - 验证：同上
  - 结果：新用例与改过的旧用例改前 3 失败 4 报错、改后 test_watch 20 项通过；plist 改用 plistlib 生成
- [x] Task 3：doctor 看旧任务、运行副本、上次退出码和日志（要做的 3、4）
  - 验证：同上
  - 结果：DoctorRunsTest 新增 4 项改前失败、改后通过；「不删除」静态扫描放行 write_runtime 删自己的临时目录和被替换的旧副本；全量 1091 项通过
- [ ] Task 4：README 排查表与升级说明，版本 0.0.32（要做的 5）
  - 验证：全量 `PYTHONPATH=tests:. python3 -m unittest discover -s tests` 通过

## 检查点

- [ ] Checkpoint（gate）：本机实机验收——你批准后装 di-p0 的巡视提醒，核对退出 0、通知、doctor ok，复现 126 时 doctor bad
- [ ] Checkpoint（gate）：模块最终验收——全部测试通过；列出实际改动的文件；批准后开 PR

