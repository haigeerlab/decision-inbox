<!-- spec-guard: review pending -->
# Implementation Plan: rehearsal-fixes

> 依据：`spec/rehearsal-fixes.md`（用户 2026-10-18 批准）。任务清单：`tasks/rehearsal-fixes/todo.md`。分支 `claude/rehearsal-fixes`。

## Overview

五个任务，从小到大：撤回提示 → doctor 只登记条目 → leave 预览 → doctor 两边版本 → 文档版本与 .gitignore。每个任务先写失败的测试再改。冻结步骤（标签、固定副本、改安装）不在本 Plan 内，合并后另请用户批准。

## Architecture Decisions

- **撤回提示**（`items.py`）：`_not_owner(no, doc=None, sender=None, kind="supersede")`；`kind="withdraw"` 时提示「#N 是邮箱号，对应事项 #M；改写「事项：#M」重发【撤回】」。`_receive_withdraw` 传 `doc`、`sender`、`kind="withdraw"`。【取代】调用不变，原测试断言的文字不变。
- **只登记条目**（`doctor._conventions`）：条目带 `legacyFormat` 时直接 `Check(name, "ok", "本插件", "只登记，不写约定块（迁移期旧格式会话）")`，放在查规则文件之前。
- **leave 预览**（`onboard.py`）：新函数 `_unfinished(g, relay_name) -> list[str]`：
  - 事项：`items.pending(g)` 里 `sender == relay_name` 的，写「事项 #N：<要你决定首行>」；
  - 等待单：tickets 状态里 `status == "open"` 且 `waiter == relay_name` 的，写「等待单 #N：在等 <target>」；
  - 有内容时，`_leave` 和 `_leave_enrolled` 都把它们放进 `out.warnings`（预览最前面显示），并附两句：「leave 后这些事项继续留在主视图，收件枢纽不再给它发消息」「事项请在 leave 前由它自己发【撤回】；等待单你可以在收件枢纽说「关掉 #编号」」。
  - 确认时照常执行，不拦。只读，不改任何状态。
- **两边版本**（`doctor.py`，必要时 `deps.py`）：
  - 新函数 `_codex_install() -> tuple[str, list[str]] | str`：读 `codex_config()`，用正则找 `[plugins."decision-inbox@<市场>"]` 段，看 `enabled` 不为 false；缓存目录取 `codex_config().parent / "plugins" / "cache" / <市场> / "decision-inbox"`，列出其中带 `.codex-plugin/plugin.json` 或 `.claude-plugin/plugin.json` 的子目录版本。缓存目录跟着配置文件位置走，测试用已有的 `DECISION_INBOX_CODEX_CONFIG` 指到临时目录即可，不新加环境变量。
  - Claude 侧：`deps.find("decision-inbox")` 的版本，目录型市场取源目录的版本（已有逻辑）。
  - 新 `Check("Claude、Codex 两边的版本", …)`，按 Spec 第 4 条判定；修复命令写 `codex plugin remove decision-inbox@<市场>` 后 `codex plugin add decision-inbox@<市场>`，Claude 侧写「在 Claude 里更新 decision-inbox 插件（/plugin），或按 README「固定副本安装」重装」。
  - `run()` 里加在依赖检查之前，每次都跑，不依赖协作组。
- **`.gitignore`**：新增，内容 `__pycache__/`。
- README 三处改动；两份 `plugin.json` 和 `tests/test_packaging.py` 的版本改为 0.0.19。

## Task List

- [ ] Task 1：【撤回】写成自己邮箱号时点明事项号（Spec 验收 3）
- [ ] Task 2：doctor 对只登记条目报 ok（Spec 验收 1）
- [ ] Task 3：leave 预览列出没了结的事项和等待单（Spec 验收 2）
- [ ] Task 4：doctor 核对 Claude、Codex 两边的版本（Spec 验收 4）
- [ ] Task 5：`.gitignore`、README、版本 0.0.19（Spec 验收 5、6）

### Checkpoint（gate）：模块最终验收

- [ ] 全部测试通过；每条验收标准都有证据；列出实际改动的文件
- [ ] 授权：Task 1–5 的代码、测试和文档；每个任务做完都提交，并推送 `claude/rehearsal-fixes`
- [ ] 不授权：开 PR 或合并 PR、打标签、建固定副本、改用户的插件安装或配置、碰 LIVE-SAAS
- [ ] 实测（Spec 验收 7）放到冻结之后，开始前另问用户

## Risks

| 风险 | 预防 |
|---|---|
| Codex 配置或缓存目录结构和假设不一样 | 读不到或看不懂时报「未知」并写明读的是哪个路径，不报一致；测试覆盖配置缺失、没启用、缓存空、多个版本 |
| 版本一项在没装 Codex 的机器上误报 | 没启用或没配置时报 ok 并写明「Codex 没装」 |
| leave 预览多写了内容，影响现有 leave 测试 | 没有未了结的事时输出和现在逐字相同（现有测试全过来证明） |
| 撤回提示改动连带影响【取代】 | 用 kind 参数区分，【取代】现有断言不改 |
