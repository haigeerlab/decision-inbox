# Todo: permission-closeout

- [x] Task 1：接入写的权限与规则段文字（Spec 第 1、2 节；验收 1–4）
  - 验证：新用例先失败后通过；原有接入用例改到新清单后通过
- [x] Task 2：宿主权限对照（Spec 第 3 节；验收 5、6）
  - 验证：新用例先失败后通过；配置读前读后逐字相同；本机 di-p0 只读实跑 doctor，结果记在这里
  - 实跑（2026-10-19，本分支代码，di-p0 状态文件前后 md5 相同）：
    - ✔ 宿主权限：dev——Codex 可写工作区、不能联网、项目已信任；仓库根目录没有依赖清单，不用装依赖。
    - ✘ 宿主权限：并行协调2——Claude 没有放行加新包的规则，还留着旧版写的先问规则 `npm install *`、`pip install *`，仓库有依赖清单；A 重跑接入、B 到时去会话点。与用户给 rh2-coord 选的 A（0.0.28 发版后重跑接入）一致。
- [x] Task 3：改正说法与文档（Spec 第 4、5 节；验收 7）
  - 验证：新用例先失败后通过；旧称扫描、全量测试通过
  - 注意：`spec/stall-and-patrol.md`、`spec/proxied-session-note.md` 各加一行更正后，spec-guard 把这两个已完成模块的 Spec 标成「改过待重审」；最终验收时把这两处 diff 交用户，批准后用 review-mark 重新记为已批准。

## 检查点

- [ ] Checkpoint（gate）：模块最终验收——全部测试通过；每条验收标准有证据；列出实际改动的文件

## 外部审查意见

<!-- spec-guard: external-review declined -->
用户 2026-10-19：不做外部审查（Spec 批准时一并说明）。
