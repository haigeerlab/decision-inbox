<!-- spec-guard: review approved -->
# Implementation Plan: plugin-packaging

> 依据：`spec/plugin-packaging.md`（已批准）。任务清单：`tasks/plugin-packaging/todo.md`。

## Overview

先做命令入口：`bin/decision-inbox`、`shim`，以及把默认命令路径改成固定路径。再做按工作目录查找：`whoami`，以及 `hook stop` 不带 `--group` 也能工作。然后写钩子配置、清单和 `marketplace.json`，接着写 8 个斜杠命令、Codex 技能和 README，最后在本机实测安装。

每个代码任务都先写失败的测试，再实现到全绿，然后单独提交。命令文件、技能和 README 是文档类产物，用打包测试核对它们的结构和引用。

## Architecture Decisions

- **`decision_inbox/install.py`** 放两样东西：
  - 转发脚本：`shim_path()`、`write_shim(plugin_root, if_installed)`；
  - 按目录查找：`locate(cwd) -> list[(group, entry)]`。
  
  查找时遍历 `store.root_dir()` 下每个有 `group.json` 的目录，只读名册和领域 `onboarding`。路径比较用 `os.path.realpath` 两边都解析，避免 `/var` 和 `/private/var` 这类差别。
- **插件目录怎么定**：`bin/decision-inbox` 用 `$(cd "$(dirname "$0")/.." && pwd -P)` 求出插件根目录，导出为 `DECISION_INBOX_PLUGIN_ROOT`，再运行 Python。`shim` 子命令从这个变量读插件根目录；没有这个变量（直接用 `python3 -m` 跑）时，用包所在目录的上一级。
- **默认命令路径**：新增 `install.cli()`，返回固定路径展开后的绝对路径字符串。`hub.convention`、`patrol.prompt`、`onboard` 的 `CLI` 都改为调用它；测试里它跟着 `DECISION_INBOX_HOME` 变。
- **`hooks.json`**：命令写成一行 shell，做法和 spec-guard 一样：先定 `ROOT`，`bin/decision-inbox` 不存在就 `exit 0`；Stop 钩子把 stdin 原样交给 `hook stop`；出错时 `|| true`，保证退出码 0。
- **打包测试**：在临时目录里复制一份插件（`bin/`、`decision_inbox/`、`hooks/`），设好 `PLUGIN_ROOT` 后，用 `subprocess` 跑 `hooks.json` 里的两条命令字符串，核对 stdout 和退出码。

## 影响面

- 新增：
  - `bin/decision-inbox`、`decision_inbox/install.py`；
  - `hooks/hooks.json`、`.claude-plugin/marketplace.json`；
  - `commands/` 下 8 个命令文件、`skills/decision-inbox-join/SKILL.md`、`README.md`；
  - `tests/test_install.py`、`tests/test_packaging.py`。
- 修改：
  - `.claude-plugin/plugin.json`、`.codex-plugin/plugin.json`；
  - `decision_inbox/__main__.py`、`hub.py`、`patrol.py`、`onboard.py`；
  - `tests/test_package.py`（版本一致性检查顺带核对 marketplace）、`tests/test_hub.py`、`tests/test_patrol.py`、`tests/test_onboard.py`（默认命令路径的断言）；
  - `spec/plugin-packaging.md`：实测记录；
  - `tasks/plugin-packaging/todo.md`；
  - `.agent/state.json`。
- 用户可见界面：斜杠命令的提示和输出、README、约定块里的命令路径。由 Task 7 实测时，在真实安装的插件里打开命令、看输出并记录。

## Task List

### Phase 1：命令入口与查找

- [ ] Task 1：`bin/decision-inbox`、`shim`、固定命令路径（Spec 验收 1、4）
- [ ] Task 2：`whoami` 与 `hook stop` 不带 `--group`（Spec 验收 2、3）

### Checkpoint 1（report）

- [ ] 全部测试全绿

### Phase 2：打包产物

- [ ] Task 3：`hooks.json`、两份清单、`marketplace.json`（Spec 验收 5、6）
- [ ] Task 4：8 个斜杠命令与 Codex 技能（Spec 验收 7）
- [ ] Task 5：README（Spec 验收 8）

### Checkpoint 2（report）

- [ ] 全部测试全绿（Spec 验收 9）；在 scratchpad 里用复制出来的插件，按 `hooks.json` 的命令手动跑一次放行和拦截，记下输出

### Phase 3：实测

- [ ] Task 6：本机安装与实测（Spec 验收 10）。先问用户：会改本机的 Claude Code 插件配置、开新会话、建定时任务。结果写进规格的实测记录

### Checkpoint 3（gate）：模块最终验收

- [ ] 全部测试全绿；10 条验收标准逐条有测试或实测记录；列出实际改动的文件；原样附上规格的改动差异；同时做能力图完成时的文档建议
- [ ] 本 Plan 获批即授权：
  - 返工 hub-loop、patrol、onboarding 的默认命令路径；
  - 每个任务完成后在当前分支做一次本地提交；
  - 在 scratchpad 里建临时目录和临时协作组。
- [ ] 不授权：Task 6 的实测（安装插件、开会话、建任务，到时另外问你）、推送、开 PR、发布

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| 钩子在真实安装下取不到插件目录，或报错卡住会话 | 高 | 命令里先判断，取不到就 `exit 0`；打包测试在两个变量都没有时核对退出码 0、没有输出；实测再验一次 |
| 按目录查找认错协作组 | 中 | 对上多个就放行并说明，不猜；测试覆盖子目录、符号链接路径、多个协作组 |
| 默认命令路径改了，原有测试里写死的 `python3 -m decision_inbox` 断言失败 | 低 | 同一个任务里一起改这些断言；全量测试把关 |
| 实测安装影响你本机已有的插件 | 中 | 只用新的 marketplace 名 `decision-inbox-marketplace`，不碰其他插件；实测最后卸载插件和 marketplace，并核对 `claude plugin list` |

## Open Questions

无。
