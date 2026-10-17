# decision-inbox

多会话协作时的决策收件箱。几个 Claude Code 和 Codex 会话一起干活时，要你拍板的事、谁在等谁、谁停下了，都集中到一个「收件枢纽」会话里：

- **待答表**：各会话抛来的【等待用户】事项，按挡住几条线排序，一项一张卡片，推荐选项带好复制块；你回「12 A」，收件枢纽原话转达给提出方（多线事项分别转给各条线）。
- **等待单**：谁在等谁的什么、等了多久，只按四种理由关单。
- **巡视**：每 5 分钟检查一次，停下的 Claude 会话先叫醒，叫不醒或全线停住时发桌面通知。
- **停止钩子**：有会话在等你时，工作会话收工前会被拦一次，提醒先交付或报阻塞。
- **查询**：各线状态、流畅度体检、单项时间线、能力图进度。

依赖：

- [agent-relay](https://github.com/haigeerlab/agent-relay)：会话之间的邮箱，必需；
- [spec-guard](https://github.com/haigeerlab/spec-guard-plugin)：可选，有了才能看能力图进度和进度预警；
- macOS、`python3`（3.10 及以上，只用标准库）、Claude 桌面版（收件枢纽和巡视任务都在桌面版里跑）。

## 安装

发布前从本地目录安装（把 `<仓库目录>` 换成这个仓库在你机器上的路径）：

| Claude Code | Codex |
|---|---|
| `/plugin marketplace add <仓库目录>` | `codex plugin marketplace add <仓库目录>` |
| `/plugin install decision-inbox@decision-inbox-marketplace` | `codex plugin add decision-inbox@decision-inbox-marketplace` |

装好后开一个新会话，插件的命令、技能和钩子才会生效。

## 接入

按这个顺序接入，每一步都会先预览要写哪个文件、写什么，你确认后才写：

1. **收件枢纽**：为它单独建一个目录，在这个目录里开一个 Claude 桌面版会话，运行
   `/decision-inbox:hub-setup <协作组名> <它在 agent-relay 的身份名>`。
   它会建协作组、把收件枢纽的约定写进本目录的 `CLAUDE.md`、建巡视定时任务（每 5 分钟）。
   建好后请在定时任务列表里**手动「立即运行」一次**，把 Bash 和 agent-relay 工具的权限批一遍，以后定时运行就不会卡在权限确认上。
2. **负责人**：在各负责人的会话里运行 `/decision-inbox:join <协作组> owner <身份名> <短名> <线名>`。
3. **开发线和总协调**：
   - Claude 会话：`/decision-inbox:join <协作组> dev <身份名> <短名> <线名>`（总协调用 `coordinator`，不写线名）；有审查者时告诉它审查者的身份名和审哪几类节点（spec、plan、interface、final）。
   - Codex 会话：对它说「接入 decision-inbox 协作组」，它会用自带的接入技能完成同样的步骤。

每个会话接入后还要做两件事（命令会提示）：

- 在 agent-relay 登记身份并绑定唤醒（`bridge_register`，`wake: "auto"`）；
- 在 Claude Code 和 Codex 里各信任一次插件自带的停止钩子。

约定会写进各项目的 `CLAUDE.md`（Claude）或 `AGENTS.md`（Codex），用 `<!-- BEGIN decision-inbox … -->` 和 `<!-- END … -->` 包住，块外的内容一字不动；重复接入会整块替换。

## 日常使用

平时只看收件枢纽，直接对它说话：

| 你说 | 它做什么 |
|---|---|
| `12 A`、`12 B 但先别上线`，或复制卡片里的推荐块 | 把你的原话转达给提出方 |
| `12 详情` | 显示事项全文、各线范围和消息编号 |
| `看等待`、`看已关闭`、`看已关闭 2026-10-15`、`看失效` | 展开对应明细 |
| `关掉 #5 已经不需要` | 按「用户关闭」关掉等待单 |
| `重发` | 重新列出没发出去的消息 |
| `以后 X 都这样` | 先问你发给哪几个会话，确认后原话转过去 |

查询命令（只读，不给任何会话发消息）：

- `/decision-inbox:lines`：各线状态；
- `/decision-inbox:flow`：流畅度体检，卡在哪、谁等谁；
- `/decision-inbox:item <编号>`：单项时间线；
- `/decision-inbox:map [线|all] [全部]`：能力图进度。

收件枢纽不替你决定、不改写选项、不批宿主的权限确认；要你去某个会话里亲手点确认时，它会明说。

负责人抛的事项被你答复后，收件枢纽会给这条线上的开发线各发一条【答复告知】：只是让它们知道答复已经有了，不是批准，开发线要等负责人转交后才执行。

## 升级

| Claude Code | Codex |
|---|---|
| `claude plugin marketplace update decision-inbox-marketplace`，再 `claude plugin update decision-inbox@decision-inbox-marketplace` | `codex plugin marketplace upgrade` |

升级后开一个新会话即可。约定块和巡视任务调用的是固定路径 `~/.decision-inbox/bin/decision-inbox`，插件在会话开始时会自动把它指向新版本，不用重新接入。

## 卸载

1. 在各工作会话里运行 `/decision-inbox:leave`（Codex 会话说「退出 decision-inbox 协作组」），删掉规则文件里的约定块。
2. 在收件枢纽里运行 `/decision-inbox:teardown`，删掉它的约定块和巡视定时任务。
3. 卸载插件：Claude Code 用 `claude plugin uninstall decision-inbox@decision-inbox-marketplace`；Codex 用 `codex plugin remove decision-inbox@decision-inbox-marketplace`。

`~/.decision-inbox` 下的状态目录（名册、事项、等待单、事件日志）**保留**，不会被删除；确实不要了再自己处理。

## 排查

| 现象 | 先看 |
|---|---|
| 停止钩子不拦 | 在那个会话的工作目录运行 `~/.decision-inbox/bin/decision-inbox whoami`：退出码 4 是没接入，5 是同一个目录对上了多个协作组；钩子出任何问题都会放行，不会卡住会话 |
| 巡视不跑 | 在定时任务列表里看任务是否启用、最近的运行记录；第一次是否手动「立即运行」批过权限 |
| 主视图第一行写「读不到 agent-relay」 | agent-relay 是否在运行、收件枢纽是否登记了身份 |
| 主视图写「有 N 条消息没发出去」 | 对收件枢纽说「重发」 |
| 命令提示找不到 `~/.decision-inbox/bin/decision-inbox` | 收件枢纽还没接入；或开一个新会话，让插件重新写一次 |
| 状态文件出问题 | 运行 `~/.decision-inbox/bin/decision-inbox store show <协作组>` 看一致性检查 |
