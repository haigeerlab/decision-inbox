<!-- spec-guard: review pending -->

# Spec: teardown-patrol-session

> 能力图模块 `teardown-patrol-session`（2026-10-19 用户确认插入，显式插队；stall-and-patrol 只剩冻结后实测）。来源：0.0.22 冻结后核对未完成项时发现的 stall-and-patrol 遗漏；插入时的假设 1–5 用户 2026-10-19 确认。

## 目标

用 `/decision-inbox:teardown` 卸载决策收件箱时，巡视会话会被归档，不会留在侧边栏里继续每 5 分钟跑一次。

## 现状（已核对代码）

- stall-and-patrol 把巡视从桌面定时任务改成巡视会话。`onboard teardown` 的输出已跟上：登记过巡视会话时，后续步骤第一条是「用会话管理工具 archive_session 停掉并归档巡视会话 <编号>」；登记过旧定时任务时再加「用 delete_scheduled_task 删除」（`decision_inbox/onboard.py` 的 `teardown`）。
- 命令文件 `commands/teardown.md` 没跟上：
  - 说明写「删协作规则段和巡视定时任务」；
  - 第 3 步只说「用 `delete_scheduled_task` 删除巡视任务」，不提归档巡视会话；
  - 允许的工具只有 `Bash`、`list_scheduled_tasks`、`delete_scheduled_task`，没有 `archive_session`。
- README「卸载」一节第 2 条写「删掉它的协作规则段和巡视定时任务」。
- 结果：新组卸载时，会话照命令文件做，巡视会话留着继续跑，而且没有工具去归档它。

## 要做的

1. `commands/teardown.md`：
   - 说明改成「决策收件箱卸载：删协作规则段、归档巡视会话（有旧的巡视定时任务也删掉），状态目录保留」。
   - 第 3 步改成：按输出的「后续步骤」逐条做——归档巡视会话用 `archive_session`，删旧定时任务用 `delete_scheduled_task`；输出说没记下编号时，先用 `list_scheduled_tasks` 核对再删。
   - 允许的工具加上 `mcp__ccd_session_mgmt__archive_session`，原有两个定时任务工具保留（照顾还在用旧定时任务的组）。
2. README「卸载」第 2 条改成「删掉它的协作规则段、归档巡视会话（以前建过巡视定时任务的也删掉）」。
3. 打包测试补断言。

## 关键决策与取舍

1. **只改命令说明，不改 CLI**：CLI 输出已经对，问题只在给会话看的命令文件；让命令照输出的步骤逐条做，以后 CLI 再变也不用改命令文件。
2. **保留定时任务工具**：0.0.22 之前建的组可能还有定时任务，卸载时仍要能删。

## 范围

做：`commands/teardown.md`、README 卸载一节、`tests/test_packaging.py`。

不做：CLI 逻辑（`onboard teardown` 已正确）；其他命令；版本号（修完另开版本号 PR，冻结与安装切换另请用户批准）。

## 验收标准

1. `commands/teardown.md` 的允许工具里有 `mcp__ccd_session_mgmt__archive_session`，正文提到 `archive_session` 和「后续步骤」逐条做；说明和正文都不再写「巡视定时任务」作为唯一对象。
2. README 卸载一节写明归档巡视会话。
3. `onboard teardown` 原有测试照旧通过（登记了巡视会话时输出归档步骤、登记了旧任务时输出删除步骤）。
4. 全量测试通过。

## 假设

1. 宿主的会话管理工具名是 `mcp__ccd_session_mgmt__archive_session`（与 hub-setup 用的 `mcp__ccd_session__start_session` 同属桌面版会话工具；stall-and-patrol 的 onboard 输出已用 `archive_session`）。
2. 卸载由决策收件箱会话自己做，归档的是另一个会话（巡视会话），不是 `archive_session("self")`，不受自动模式拦截 self 归档的限制。

## 未决问题

无。

## 文档建议

README 卸载一节（见要做的第 2 条）；其余无。
