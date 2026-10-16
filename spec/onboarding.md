<!-- spec-guard: review approved a1d628ff05c8 -->
# Spec: onboarding

> 能力图模块 `onboarding`。需求来源：`docs/requirements-record.md` 第 10.4 节（接入）、第 4 节（事项与消息约定）、第 5 节（负责人工作模式）、第 3.3.3～3.3.5 节（总协调、负责人、开发线的职责）、第 12 节第 9、10 项。
> 依据：hub-loop 的 `hub.convention`、patrol 的 `patrol.prompt`、group-store 的名册规则、review-registry 的 `register`；桌面版 `get_session("self")` 能拿到本会话的 `local_` 编号（2026-10-17 实测）。

## 目标

让一个协作组用几条命令接入，用户之后只看收件枢纽：

- **收件枢纽先接入**：建协作组、登记自己、把收件枢纽约定块写进它的规则文件、给出巡视定时任务的提示词，由收件枢纽会话创建定时任务；
- **其他会话各自接入**：开发线、负责人、总协调各在自己的会话里跑一次，把对应角色的约定块写进自己项目的规则文件，并登记名册；开发线和总协调接入时可以一并登记审查者；
- **卸载**：删掉约定块，收件枢纽另删巡视任务；协作组的状态目录保留。

## 已定事项（用户确认）

1. **约定块按角色分块，用 BEGIN/END 标记包住**，重装时整块替换（第 12 节第 9 项，2026-10-16）。
2. **卸载删约定块和巡视任务，状态目录保留**（同上）。
3. **不检查绕过权限模式**（第 12 节第 10 项，2026-10-16）。
4. **回放验收放到第六阶段**（第 12 节第 13 项，2026-10-16）：本模块只在临时协作组上实测。
5. **各会话自己接入**（2026-10-17）：收件枢纽跑一次 `onboard hub`，其他会话各在自己里跑一次 `onboard join`。各会话最清楚自己的身份名、仓库和会话编号。
6. **先预览后确认**（2026-10-17）：不带 `--confirm` 只打印要写哪个文件、写什么，不改任何东西；带 `--confirm` 才写。做法和 spec-guard 的 setup-convention 一致。
7. **审查者接入时一并登记**（2026-10-17）：开发线或总协调接入时，用户说明谁审、审哪几类节点，批准依据记为「接入时用户指定」。以后要改，走收件枢纽的事项批准。
8. **约定块全文在最终验收时审**（2026-10-17）：本规格只列每个角色要写哪几条规则；全文在最终验收时原样给用户看，测试按下面列的要点核对。

## 关键决策与取舍（请重点审）

1. **命令**：

   | 命令 | 谁跑 | 做什么 |
   |---|---|---|
   | `onboard hub <协作组> --relay-name <身份名> --desktop-session <local_…> [--project <目录>] [--confirm]` | 收件枢纽会话 | 协作组不存在就建；登记收件枢纽；把 hub-loop 的约定块写进 `<目录>/CLAUDE.md`；打印巡视任务的提示词和创建方法 |
   | `onboard join <协作组> --role dev\|owner\|coordinator --relay-name … --short-name … --host claude-desktop\|codex-desktop [--line …] [--desktop-session local_…] [--project <目录>] [--reviewer <身份名> --nodes spec,plan,interface,final] [--confirm]` | 各工作会话 | 登记名册；把角色约定块写进规则文件；可选登记审查者 |
   | `onboard task <协作组> --task-id <编号>` | 收件枢纽会话 | 记下实际创建的巡视任务编号，供卸载时删除 |
   | `onboard leave <协作组> --relay-name … [--project <目录>] [--confirm]` | 各会话 | 从规则文件里删掉本插件的约定块 |
   | `onboard teardown <协作组> [--project <目录>] [--confirm]` | 收件枢纽会话 | 删掉收件枢纽约定块，打印要删的巡视任务编号 |

   - `--project` 默认是当前目录。开发线的 `repo` 就记这个目录。
   - 规则文件按宿主选：Claude 桌面版写 `CLAUDE.md`，Codex 写 `AGENTS.md`，都在 `--project` 目录下；文件不存在就新建。
2. **约定块的标记与替换**：
   - 标记写作 `<!-- BEGIN decision-inbox <角色> -->` 和 `<!-- END decision-inbox <角色> -->`，角色是 `hub`、`dev`、`owner`、`coordinator`。
   - 同一文件里已有同角色的块：整块替换，块外的内容一字不动。已有别的角色的块：拒绝，提示先 `leave`。只有 BEGIN 没有 END（标记坏了）：拒绝，不猜。
   - `leave`、`teardown` 只删本插件的块，其余内容一字不动。删完文件空了也保留文件。
3. **名册登记**：
   - 同一身份名重复接入：用新的信息替换原条目（例如换了仓库或会话编号）。
   - 名册规则沿用 group-store：开发线恰好一条线，负责人至少一条线，收件枢纽和总协调不属于任何线，短名不重复，每组一个收件枢纽。违反时退出码 2，不写任何东西。
   - 卸载不动名册：名册是状态目录的一部分，按已定事项 2 保留。
4. **审查者**：`--reviewer` 必须是名册里已有的负责人，所以负责人要先接入。节点只能是 spec、plan、interface、final。登记调用 review-registry 的 `register`，批准依据写「接入时用户指定（日期）」。
5. **桌面版会话编号**：Claude 桌面版的会话接入前，用桌面版的 `get_session("self")` 取得本会话的 `local_` 编号，填进 `--desktop-session`。巡视用它叫醒停下的会话。Codex 会话不填。收件枢纽必须填。
6. **巡视任务**：
   - `onboard hub` 打印 patrol 的提示词，以及创建方法：用桌面版定时任务工具 `create_scheduled_task`，任务编号建议 `decision-inbox-patrol-<协作组>`，`cronExpression` 为 `*/5 * * * *`。
   - 创建后提示用户：在定时任务列表里手动「立即运行」一次，把 Bash 和 agent-relay 工具的权限批一遍。依据是第 12 节第 1 项的实测：工具批准会存到任务上。
   - 实际编号用 `onboard task` 记下（编号被占用时工具会给出另一个），`teardown` 时打印出来，由会话调用 `delete_scheduled_task` 删除。
7. **接入后的提示**（`hub`、`join` 都打印）：
   - 在 agent-relay 登记本会话的身份名，并绑定唤醒（`bridge_register`，`wake: "auto"`）；
   - 在 Claude Code 和 Codex 里各信任一次插件自带的停止钩子；钩子本身由 plugin-packaging 打包；
   - 接入其他会话的命令样例。
8. **各角色约定块要写的规则**（全文在验收时审）：

   | 规则 | 开发线 | 负责人 | 总协调 |
   |---|---|---|---|
   | 协作组名、收件枢纽的身份名；跨会话请求和回复一律走 agent-relay（`bridge_send`，回复填 `replyTo` 并在第一行写「回复：#编号」）（需求 4.7） | ✓ | ✓ | ✓ |
   | 消息类型与字段：【等待用户】【等待其他会话】【已恢复】【撤回】【取代 #旧编号】【与 #旧编号 并行】，以及「结束：」行的写法（4.1） | ✓ | ✓ | ✓ |
   | 选项写法：成套方案、A/B/C、每项「选了会怎样」、推荐写进「你该回」（4.1） | ✓ | ✓ | ✓ |
   | 答复的有效性：只认收件枢纽发来、编号是自己抛出的答复，执行前先回显核对；别人的转述和审查建议都不是批准（4.2） | ✓ | ✓ | ✓ |
   | 被挡住必须发【等待其他会话】报阻塞，不能悄悄停下；收工前自检，停止钩子会拦（3.3.5） | ✓ | ✓ | ✓ |
   | 宿主权限确认只能用户在原会话亲手点（4.6） | ✓ | ✓ | ✓ |
   | 只抛本线的事，不抛多线事项；有审查者时每项写「架构审查：…」一行；交付时标审查状态（3.3.5、4.3） | ✓ | | |
   | 每轮第一行写模式标签【讨论】【审查结论】【进度】【提案已抛】；审查结论的固定写法，含「审查编号、节点、模块、送审方、结论」；提案一律抛到收件枢纽；用户在负责人会话里说「就这么定了」不算批准（第 5 节） | | ✓ | |
   | 收到巡视发来的【进度预警】：自己判断，需要用户介入就转成提案（5.1） | | ✓ | |
   | 多线事项：写「适用会话」「各线范围」，逐条写清每条线能做和不能做什么；有审查者时同样写「架构审查」行（4.4） | | ✓ | ✓ |
   | 核对不是审查：核对指纹、范围、审查结论有没有说过头，不出「通过／须修改」结论，不批任何东西（3.3.3） | | | ✓ |
   | 收到多线事项的【用户答复】时，只做「适用于你的范围」那一条，不扩大（4.4） | ✓ | ✓ | |

## 范围

做：

- `decision_inbox/onboard.py`：三个角色的约定块文本、写入与删除约定块、`hub`、`join`、`task`、`leave`、`teardown` 的逻辑。
- `__main__.py` 新增 `onboard` 子命令。
- 领域 `onboarding`（巡视任务编号、每个会话写过约定块的文件路径），只由 `onboard.py` 写。

不做：

- 调用 agent-relay、创建或删除定时任务、调用 `get_session`：这些由会话按命令打印的提示去做。
- 停止钩子的打包和 `hooks.json`、斜杠命令、README（plugin-packaging）。
- 检查绕过权限模式（已定事项 3）。
- 回放实验记录做验收（已定事项 4）。
- 登记变更走收件枢纽批准的流程：本模块只做接入时的登记。

## 接口约定

```python
onboard.block(role, group, hub_relay)          # 角色约定块全文（带 BEGIN/END）
onboard.place(text, role, block) -> str        # 放入或整块替换；冲突时抛 BlockConflict
onboard.strip(text) -> tuple[str, bool]        # 删掉本插件的块；返回新文本和是否删过
onboard.hub(group, relay_name, desktop_session, project, confirm, now) -> Outcome
onboard.join(group, role, relay_name, short_name, host, lines, desktop_session, project,
             reviewer, nodes, confirm, now) -> Outcome
onboard.record_task(group, task_id)
onboard.leave(group, relay_name, project, confirm) -> Outcome
onboard.teardown(group, project, confirm) -> Outcome
# Outcome(file, before, after, changed, steps)：steps 是接入后要会话做的事，按顺序列出
```

命令行打印：预览时打印规则文件路径、将写入的约定块全文、名册条目和后续步骤；`--confirm` 时打印改了什么和后续步骤。

退出码：0 正常；2 参数不对、协作组不存在（`hub` 除外）、名册规则不合、审查者不是已登记的负责人、约定块冲突或标记坏了。

## 依赖

- 本插件：group-store（建组、名册）、message-protocol（字段名和审查节点写法，约定块里的模板要能被它解析）、review-registry（`register`）、patrol（`prompt`）、hub-loop（`convention`）。
- 外部组件：Claude 桌面版的定时任务工具和 `get_session`、agent-relay 的 `bridge_register`。本模块不调用它们，只在提示里写出用法；都是已有的接口，不缺。

## 项目结构

- `decision_inbox/onboard.py`（新）
- `decision_inbox/__main__.py`（加子命令）
- `tests/test_onboard.py`（新）

## 命令

`python3 -m unittest discover -s tests -v`

## 代码风格

沿用现有模块：标准库、事务里读写状态、事件名 `onboarding.*`。代码和注释用英文，约定块正文用中文。

## 测试策略

- 单元测试：约定块的放入、替换、冲突、标记坏了、删除，块外内容一字不变；各角色约定块含上表的要点，且约定块里的消息模板能被 message-protocol 解析成对应类型；`hub`、`join` 的预览不改任何文件；名册与审查者登记；`leave`、`teardown` 不动名册。
- 命令行测试：用临时目录和临时协作组跑每个子命令，检查退出码和输出。
- 实测（最终验收前）：在 scratchpad 的临时项目目录里，本会话用真实的桌面版会话编号走一遍「收件枢纽接入 → 负责人和开发线接入（含审查者登记）→ 卸载」，记录写进本规格。按提示建巡视任务并手动立即运行一次，挪到 plugin-packaging 实测：插件装好后命令路径才定下来（用户 2026-10-17 确认）。

## 边界

- 始终：写文件前先预览；只动本插件的块；状态目录不删。
- 先问：在 agent-relay 登记测试身份、创建定时任务（本模块实测不做这两件事）。
- 绝不：改约定块以外的内容；替用户批准审查者变更；绕过名册规则。

## 验收标准

1. `place`：空文件、已有其他内容的文件、已有同角色块（整块替换）三种情况，块外内容一字不变；已有别的角色的块、只有 BEGIN 没有 END：抛 `BlockConflict`，文件不变。
2. `strip`：删掉本插件的块，其余内容一字不变；没有块时不改文件。
3. 三个角色的约定块含关键决策 8 的对应要点；约定块里的【等待用户】【等待其他会话】【已恢复】【审查结论】模板能被 message-protocol 解析成对应类型。
4. `hub` 预览：不建协作组、不写文件；`--confirm`：建组、登记收件枢纽（含 `desktopSession`）、写 `CLAUDE.md`、打印巡视提示词与创建方法（`*/5 * * * *`、建议任务编号、手动立即运行一次）。
5. `join` 预览不改任何东西；`--confirm` 按宿主写 `CLAUDE.md` 或 `AGENTS.md`、登记名册；开发线的 `repo` 记为项目目录；重复接入替换原条目。
6. `join` 带 `--reviewer`：审查者是已登记的负责人时登记成功，批准依据含「接入时用户指定」；不是负责人或没登记时退出码 2，名册和规则文件都不改。
7. 名册规则不合（例如开发线没有线、短名重复、第二个收件枢纽）：退出码 2，不写任何东西。
8. `task` 记下任务编号；`teardown` 删收件枢纽块，并打印这个编号和 `delete_scheduled_task` 的用法；没记过编号时打印建议编号，并提示先用 `list_scheduled_tasks` 核对。
9. `leave`、`teardown` 不改名册、不删状态目录中的任何文件。
10. 接入后的提示含 `bridge_register`（`wake: "auto"`）、信任停止钩子（Claude Code 和 Codex 各一次）、`get_session` 取会话编号。
11. 领域 `onboarding` 只由 `onboard.py` 写；原有子命令和测试不受影响。
12. 实测：按测试策略走一遍接入与卸载，记录写进本规格的「实测记录」；建巡视任务的实测在 plugin-packaging 做。

## 实测记录

2026-10-17 00:24（用户确认实测范围：只做接入与卸载），scratchpad 临时目录 `live-ob`、临时协作组 `live`。本会话用 `get_session("self")` 取得的真实编号 `local_bbdaaaab-…` 作为收件枢纽和负责人的 `--desktop-session`；没有登记 agent-relay 身份，也没有创建定时任务。

| 步骤 | 结果 |
|---|---|
| `onboard hub live … --confirm`（`hub/CLAUDE.md` 原有一行） | 退出码 0；原有一行保留在前，后面接收件枢纽约定块；名册登记 `desktopSession` |
| `onboard join --role owner --host claude-desktop … --confirm`（目录里没有规则文件） | 退出码 0；新建 `owner/CLAUDE.md`，只有负责人约定块；块里 6 段模板解析为 2 条【等待用户】（含多线）、【等待其他会话】【已恢复】【撤回】【审查结论】 |
| `onboard join --role dev --host codex-desktop --reviewer live-owner --nodes spec,plan,final --confirm`（`fe/AGENTS.md` 有 4 行原有内容） | 退出码 0；写入 `AGENTS.md`；审查者登记为 live-owner，节点 spec、plan、final；提示 2 条（`bridge_register` 的 `wake: "auto"`、信任停止钩子） |
| 同一条 join 再跑一次 | 规则文件「没有变化」，名册条目不重复 |
| `onboard leave` 开发线、负责人 | `fe/AGENTS.md` 与接入前逐字节一致（`cmp`）；`owner/CLAUDE.md` 删块后为 0 字节，文件保留 |
| `onboard teardown --confirm`（没记任务编号） | `hub/CLAUDE.md` 与接入前逐字节一致；提示先 `list_scheduled_tasks` 核对 `decision-inbox-patrol-live`，再 `delete_scheduled_task` |
| `store show live` | 名册 3 个会话、事件 8 条、一致性正常；状态目录完整保留 |

## 假设

1. 收件枢纽会话的工作目录就是它的规则文件所在目录；用户为它单独开一个目录。
2. `create_scheduled_task` 和第 12 节第 1 项实测时一样：编号被占用会给出另一个编号，工具批准存到任务上。
3. 停止钩子由 plugin-packaging 改成不带 `--group` 也能按工作目录找到协作组；在那之前，实测里的钩子不在本模块的验收范围内。

## 未决问题

无。

## 文档建议

README 候选：接入顺序（收件枢纽 → 负责人 → 开发线和总协调）和卸载方法。本模块不写 README，留给 plugin-packaging 统一写；本规格的命令表可以直接作为素材。
