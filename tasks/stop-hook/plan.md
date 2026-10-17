<!-- spec-guard: review approved -->
# Implementation Plan: stop-hook

> 依据：`spec/stop-hook.md`（已批准）。任务清单：`tasks/stop-hook/todo.md`。

## Overview

模块很小，分三步：先写判断函数 `decide`，再写命令行入口 `hook stop`，最后在 Claude 桌面版上实测一次。前两个任务先写失败的测试，再实现到全绿，各自单独提交。第三个任务是实测，结果写回规格。代码在 `decision_inbox/stophook.py`。

## Architecture Decisions

- `decide` 返回 `Decision(block, reason, note)`，是纯函数：只读协作组状态和传入的 payload，不碰 stdin、stdout。命令行只负责读 stdin、调用 `decide`、打印。
- 判断顺序如下，前四步命中就放行，`note` 写放行原因：
  1. `stop_hook_active` 为 true；
  2. 认不出本会话（对不上，或对上多个）；
  3. 本会话已经报了阻塞（自己开着等待单，或有完全停住的待答事项）；
  4. 没人在等本会话；
  5. 以上都不是：拦下，给出说明。
- 认会话时，`cwd` 和 `repo` 都先转成真实路径，再判断是否相等或在其下面。
- 出错放行在命令行这一层兜住：解析 stdin、打开协作组、`decide` 抛出的任何异常，都按放行处理，并往 stderr 写一行。
- 「已等」的写法沿用 map-view 的 `_waited`：不到 60 分钟写分钟，不到 24 小时写小时，否则写天。把它挪到 hub-view，作为公开的时长写法，由 map-view 和本模块共用。

## 实测方案（Task 3，开会话前先问你）

1. 在临时目录（scratchpad）里建：
   - 一个测试项目；
   - 一个独立的 `DECISION_INBOX_HOME`，里面放一个协作组：「探针」会话被另一个会话开着等待单等着。
2. 在测试项目的 `.claude/settings.json` 里配 Stop 钩子。命令是一个测试包装脚本：先把输入 JSON 追加到临时日志，再调用 `python3 -m decision_inbox hook stop --group probe --session probe`。
3. 经你同意后，在这个测试项目里开一个新的 Claude 桌面版会话，让它回一句话就结束。
4. 看三件事：
   - 日志里有没有两次调用，第二次的 `stop_hook_active` 是否为 true；
   - 会话里是否收到了 `reason`，并在同一轮继续；
   - 第二次是否放行。
5. 结果写进 `spec/stop-hook.md` 的「实测记录」一节；规格改了要你复审。测试项目和临时协作组都在 scratchpad 里，不动本仓库和你真实的协作组。

## 影响面

- 新增：`decision_inbox/stophook.py`、`tests/test_stophook.py`。
- 修改：
  - `decision_inbox/__main__.py`：加 `hook` 子命令；
  - `decision_inbox/view.py`：加公开的时长写法 `waited`；
  - `decision_inbox/mapview.py`：改用这个公开写法；
  - `spec/stop-hook.md`：加实测记录，需要复审；
  - `tasks/stop-hook/todo.md`：勾选；
  - `.agent/state.json`：最终验收时切换当前模块。
- 用户可见界面：拦下时会话里显示的那段说明。由 Task 3 实测在桌面版里看。

## Task List

### Phase 1：判断与入口

- [ ] Task 1：`decide`——认会话、四种放行、拦下与说明（Spec 验收 1～5）
- [ ] Task 2：命令行 `hook stop`——读 stdin、输出、出错放行、只读（Spec 验收 6～8）

### Checkpoint 1（report）

- [ ] 全部测试全绿；用子进程跑一次命令行，记下真实的 stdout 和 stderr

### Phase 2：实测

- [ ] Task 3：Claude 桌面版实测（Spec 验收 9），结果写回规格

### Checkpoint 2（gate）：模块最终验收

- [ ] 全部测试全绿；9 条验收标准逐条有测试或实测记录；列出实际改动的文件；给出规格的修订内容（实测记录）供复审
- [ ] 本 Plan 获批即授权：
  - 每个任务完成后在当前分支做一次本地提交；
  - 在 scratchpad 里建测试项目和临时协作组。
- [ ] 不授权：开实测会话（到时另外问你）、推送、开 PR

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| 桌面版会话不认项目级的 `.claude/settings.json` 钩子，或要先信任 | 中 | 如实记录，回来改规格（规格假设 2），再和你商量怎么装 |
| 实测会话在临时项目里弹权限确认 | 低 | 测试会话只让它回一句话，不让它跑任何工具；弹了就如实记下 |
| 挪动 `_waited` 影响 map-view | 低 | 只挪位置、不改行为；map-view 原有测试全部通过 |

## Open Questions

无。
