<!-- spec-guard: review approved -->

# Implementation Plan: permission-closeout

> 依据：`spec/permission-closeout.md`（用户 2026-10-19 批准，不做外部审查）。任务清单：`tasks/permission-closeout/todo.md`。分支 `claude/permission-closeout`（从 main 0e7206e 开出，main 已含 R21 前三个模块与 loop-detection）。

## Overview

三个任务，各自先写失败的测试再改：接入写的权限与规则段文字 → 宿主权限对照 → 改正代开会话的说法与文档。最后做一次最终验收。不升版本号。

## Architecture Decisions

- **`onboard.py`**：
  - `ROUTINE_ALLOW` 换成 Spec 第 1 节的放行清单；新增 `ALWAYS_DENY`（全局安装 11 条 + 管道到 shell 5 条）；`ALWAYS_ASK`、`RETIRED_ASK` 不变。
  - 新函数 `dev_server_rule(repo)`：读仓库根 `package.json` 的 `scripts.dev`，按锁文件给出一条 `Bash(pnpm dev)`／`Bash(yarn dev)`／`Bash(npm run dev)`，没有就 None；读不懂 JSON 当没有。
  - `join` 预览与写入：`wanted` 加上 deny 与开发服务一条；写入沿用现有的「缺什么补什么」（`_missing_rules` 认 `deny`）。
  - 规则段常规授权一条、`_AUTHORITY` 两段、预览里授权那一行按 Spec 第 2 节改字。
- **`hostperm.py`**：删 `plan_needs`；新 `project_needs(repo)` → `ProjectNeeds(installs: bool, dev: str | None)`；`claude_facts` 判断「新装包放行在不在」改看 `Bash(npm install *)` 等新规则，另报开发服务放行在不在；`compare` 的第三个参数换成 `ProjectNeeds`，UI 自验文字加在结果里。
- **`doctor.py`**：`_host_permission` 改调 `project_needs`，`_active_module` 不再需要时删掉它的调用（函数若无人用就删）。
- 测试沿用 `tests/test_onboard.py`、`tests/test_hostperm.py`、`tests/test_doctor.py` 的造数方式（临时仓库、临时 `DECISION_INBOX_CODEX_CONFIG`）。

## Task List

- **Task 1 接入写的权限与规则段文字**（Spec 第 1、2 节；验收 1–4）：先写测试：Claude 开发线接入确认后放行、禁止、先问三类规则齐全且裸 `pip install *` 不在任何一边；Codex 线不写；有 `dev` 脚本时按锁文件写一条开发服务放行，没有不写、`package.json` 坏了不写；已有旧先问规则时预览提议删除、确认后删掉且 `npm install *` 在放行里；规则段与授权文字不含「Plan 列出的依赖」「Plan 没列的依赖」，含「加新包」「最终验收时列出」「全局安装」「直接交给 shell」。再改 `onboard.py`。验证：先失败后通过；原有接入用例改到新清单后通过。
- **Task 2 宿主权限对照**（Spec 第 3 节；验收 5、6）：先写测试：Codex 有清单不能联网 ✘ 含 A、B；没有清单 ✔；仓库里有没有 Plan 不影响结果；Claude 没有新放行或留着旧先问 ✘；有 `dev` 脚本时 Claude 开发服务没放行有提醒、Codex 不能联网有「可能下载不了浏览器」。再改 `hostperm.py`、`doctor.py`、接入预览那一行。验证：先失败后通过；配置文件读前读后逐字相同。实跑：本分支代码对本机 di-p0 只读跑一次 doctor，看「宿主权限」各项，结果记进 todo。
- **Task 3 改正说法与文档**（Spec 第 4、5 节；验收 7）：先写测试：接入预览没有「先问规则只对你亲手开的会话可靠」；三种角色的规则段没有「被别的会话开出来的」那一条。再改 `onboard.py`；改 README（接入、doctor、使用注意事项、升级四处）；`spec/stall-and-patrol.md`、`spec/proxied-session-note.md` 各加一行带日期的更正；`docs/host-differences.md` 的 H12 补证据。验证：旧称扫描、全量测试通过。

## 检查点

- Checkpoint（gate）：模块最终验收——列出改动的文件、每条验收标准的证据和测试数，然后开 PR（base main）。

## 影响面

- 重跑接入后，Claude 线设置里多出约 20 条放行、16 条禁止；旧的两条先问提议删除。
- 规则段文字变化：已接入的线要重跑接入才拿到；与 R21 其他模块一起，在 0.0.28 发版后重跑。
- doctor「宿主权限」的判断依据变了：以前 Plan 没写就「没法对照」，以后有依赖清单就对照。

## 风险

| 风险 | 对策 |
|---|---|
| 禁止规则误伤正常命令（如 `sh 脚本.sh`） | 只用实测过的精确写法；测试覆盖 `sh x.sh` 不在禁止里 |
| 与 module-crew 给同一仓库写的规则重复或冲突 | 清单照抄 module-crew 0.5.1；`_missing_rules` 只补缺的，不重复写 |
| 开发服务放行让会话长时间占着进程 | 只放行一条命令；README 写明；没实测，最终验收时说明 |
| 删掉读 Plan 后，没有清单但要联网的项目漏报 | 接受（宁可只按清单判断）；Spec 假设 1 已写明 |
