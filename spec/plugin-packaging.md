<!-- spec-guard: review approved 2db421a3fcb8 -->
# Spec: plugin-packaging

> 能力图模块 `plugin-packaging`。需求来源：`docs/requirements-record.md` 第 9 节（停止钩子）、第 10.4 节（接入）、第 7.1 节（查询视图）、第 7.3 节（Codex 侧）、第 12 节第 2 项。
> 依据：spec-guard 0.64.0 与 agent-relay 0.7.x 的打包方式（`hooks/hooks.json` 用 `PLUGIN_ROOT` 或 `CLAUDE_PLUGIN_ROOT` 找插件目录；Codex 清单用 `"hooks"`、`"skills"` 字段；两边都从仓库根目录的 `.claude-plugin/marketplace.json` 安装）；stop-hook 规格的实测记录；onboarding 规格把「按提示建巡视任务」的实测挪到了本模块。

## 目标

把前面 15 个模块装成一个能在 Claude Code（含桌面版）和 Codex 上安装的插件：

- 一个固定路径的命令入口，插件升级后约定块和巡视任务不失效；
- 插件自带的停止钩子，不用指定协作组，按工作目录自己找到；
- Claude 侧 8 个斜杠命令，Codex 侧 1 个接入技能；
- 安装、接入、升级、卸载、排查的 README；
- 实测：本机装上插件，按提示接入一个临时协作组，建巡视任务并手动立即运行一次，停止钩子在真实安装下拦一次、放一次，再卸载。

## 已定事项（用户确认）

1. **停止钩子随插件自带**，`hooks/hooks.json` 两边共用；stop-hook 返工：`--group` 改为可选（能力图，2026-10-16）。
2. **固定路径启动脚本，会话开始时自动刷新**（2026-10-17）：插件自带 `bin/decision-inbox`；接入时在 `~/.decision-inbox/bin/decision-inbox` 写一个转发脚本，指向当前插件目录。约定块和巡视提示词都写这个固定路径。插件的 SessionStart 钩子在会话开始时刷新它，只在 `~/.decision-inbox` 已存在时才刷新。
3. **Codex 侧给一个接入技能**（2026-10-17）：教 Codex 会话用固定路径跑 `onboard join`、`leave`。查询命令留到第二版（需求 7.3）。
4. **Claude 侧 8 个斜杠命令**（2026-10-17）：查询 `/lines`、`/flow`、`/item`、`/map`；接入 `/hub-setup`、`/join`、`/leave`、`/teardown`。
5. **保留插件名 decision-inbox**（第 12 节第 2 项，2026-10-17）：命令写作 `/decision-inbox:map`。

## 关键决策与取舍（请重点审）

1. **命令入口**：
   - `bin/decision-inbox`（bash）：找到自己所在的插件目录，以它为 `PYTHONPATH` 运行 `python3 -m decision_inbox "$@"`。
   - 新增子命令 `decision-inbox shim [--if-installed]`：在 `~/.decision-inbox/bin/` 下写转发脚本，内容是 `exec "<当前插件目录>/bin/decision-inbox" "$@"`，权限 0755，原子写入；内容没变就不写。带 `--if-installed` 时，`~/.decision-inbox` 不存在就什么都不做。
   - 返工：hub-loop 的 `convention`、patrol 的 `prompt`、onboarding 的提示，默认命令从 `python3 -m decision_inbox` 改为固定路径 `~/.decision-inbox/bin/decision-inbox`（展开成绝对路径）。`onboard hub` 和 `onboard join` 确认时顺带写一次转发脚本。
2. **`hooks/hooks.json`**：
   - `Stop`：`"$ROOT/bin/decision-inbox" hook stop`，不带 `--group`；
   - `SessionStart`：`"$ROOT/bin/decision-inbox" shim --if-installed`，不输出任何东西；
   - `ROOT` 取 `PLUGIN_ROOT`，没有就取 `CLAUDE_PLUGIN_ROOT`。取不到，或脚本出错，一律放行、退出码 0，不卡住会话（stop-hook 关键决策 6）。
3. **stop-hook 返工：不给 `--group` 时按工作目录找**：
   - 遍历 `~/.decision-inbox` 下每个协作组，找名册里和钩子输入的 `cwd` 对得上的会话。对得上指两种情况：开发线的 `repo` 等于 `cwd`，或者 `cwd` 在 `repo` 里面；onboarding 记下的规则文件就在 `cwd` 这个目录。
   - 已经 `onboard leave`／`teardown` 退出的会话不算：退出时在领域 `onboarding` 记下「已退出」，名册条目照旧保留；重新接入时清掉这个记号（Task 6 实测发现：不这样做，退出后钩子还会继续拦）。
   - 恰好一个：按这个协作组和会话判断。一个都没有：静默放行，这个项目没有接入。多于一个：放行，并在 stderr 说明对上了哪几个，请用户检查名册。
   - 新增子命令 `decision-inbox whoami [--cwd <目录>]`，用同一套查法，打印协作组名、身份名、角色（JSON）。斜杠命令和技能都用它确定协作组，不让用户每次输入。
4. **清单**：
   - `.claude-plugin/plugin.json`：命令从 `commands/` 读，钩子从 `hooks/hooks.json` 读（Claude Code 的默认位置）；版本升到 0.0.2。
   - `.codex-plugin/plugin.json`：`"skills": "./skills/"`、`"hooks": "./hooks/hooks.json"`，版本同步。
   - 新增 `.claude-plugin/marketplace.json`：marketplace 名为 `decision-inbox-marketplace`，`source` 指向仓库根目录。Claude Code 和 Codex 都从这里安装。
5. **斜杠命令**（`commands/*.md`，每个开头先跑 `whoami` 确定协作组）：

   | 命令 | 谁用 | 步骤 |
   |---|---|---|
   | `/lines` | 收件枢纽 | `bridge_agents` 原样存文件 → `query lines` |
   | `/flow` | 收件枢纽 | `bridge_agents`、`bridge_wake_status` 原样存文件 → `query flow` |
   | `/item <编号>` | 收件枢纽 | `query item-ids` → 每个编号的消息状态原样存文件 → `query item` |
   | `/map [线\|all] [全部]` | 收件枢纽、负责人 | `map` |
   | `/hub-setup <协作组> <身份名>` | 收件枢纽 | `get_session("self")` 取编号 → `onboard hub` 预览，给用户看 → 用户确认后加 `--confirm` → 按打印的步骤建巡视任务、`onboard task` 记编号、请用户手动立即运行一次 |
   | `/join <协作组> …` | Claude 工作会话 | `get_session("self")` → `onboard join` 预览 → 用户确认后 `--confirm` → `bridge_register` |
   | `/leave` | Claude 工作会话 | `onboard leave` 预览 → 确认 |
   | `/teardown` | 收件枢纽 | `onboard teardown` 预览 → 确认 → `delete_scheduled_task` |

   查询命令输出原样显示，不改写；接入和卸载都要先预览、经用户确认才加 `--confirm`。
6. **Codex 技能** `skills/decision-inbox-join/SKILL.md`：教 Codex 会话：
   - 先跑 `whoami`；
   - 用固定路径跑 `onboard join`（宿主 `codex-desktop`，不填会话编号）、`onboard leave`，先预览，用户确认后再加 `--confirm`；
   - 在 agent-relay 登记身份；
   - 在 Codex 里信任插件钩子。
7. **README**（仓库根目录，中文）：
   - 是什么；
   - 依赖：agent-relay、可选的 spec-guard；
   - 两边的安装命令；
   - 接入顺序：收件枢纽 → 负责人 → 开发线和总协调；
   - 日常用法：在收件枢纽里直接说话，以及 8 个斜杠命令；
   - 升级：升级插件后开新会话，转发脚本自动刷新；
   - 卸载：先在各会话 `/leave`、在收件枢纽 `/teardown`，再卸载插件；`~/.decision-inbox` 保留；
   - 排查：钩子不生效、巡视不跑、读不到 agent-relay。

## 范围

做：

- `bin/decision-inbox`、`hooks/hooks.json`、两份清单、`marketplace.json`、`commands/` 下 8 个命令、`skills/decision-inbox-join/SKILL.md`、`README.md`。
- 子命令 `shim`、`whoami`；`hook stop` 的 `--group` 改为可选。
- 默认命令路径改为固定路径（hub-loop、patrol、onboarding 的返工，只改默认值）。
- 实测（见测试策略）。

不做：

- Codex 侧查询命令（第二版，需求 7.3）。
- 发布 0.1.0、推送到 GitHub、在真实协作组里替换规则版收件枢纽（第六阶段）。
- 英文 README。

## 接口约定

```text
~/.decision-inbox/bin/decision-inbox <子命令> …     # 转发到当前插件的 bin/decision-inbox
decision-inbox shim [--if-installed]                # 写或刷新转发脚本；退出码 0
decision-inbox whoami [--cwd <目录>]                # {"group":…, "relayName":…, "role":…}；对不上退出码 4，对上多个退出码 5
decision-inbox hook stop [--group <协作组>] [--session <身份名>]   # 不给 --group 时按 cwd 找；任何问题都放行
```

## 依赖

- 本插件：stop-hook（返工）、query-commands、map-view、onboarding、hub-loop、patrol（默认命令路径）、group-store。
- 外部组件：Claude Code 和 Codex 的插件机制（`commands/`、`skills/`、`hooks/hooks.json`、`marketplace.json`）、Claude 桌面版的 `get_session` 和定时任务工具、agent-relay 的 MCP 工具。都是已有的接口，不缺。

## 项目结构

- 新增：`bin/decision-inbox`、`hooks/hooks.json`、`.claude-plugin/marketplace.json`、`commands/{lines,flow,item,map,hub-setup,join,leave,teardown}.md`、`skills/decision-inbox-join/SKILL.md`、`README.md`、`decision_inbox/install.py`（shim、whoami 的查找）、`tests/test_install.py`、`tests/test_packaging.py`
- 修改：`.claude-plugin/plugin.json`、`.codex-plugin/plugin.json`、`decision_inbox/__main__.py`、`decision_inbox/hub.py`、`decision_inbox/patrol.py`、`decision_inbox/onboard.py`、相关测试

## 命令

`python3 -m unittest discover -s tests -v`

## 代码风格

沿用现有模块。命令文件和技能用中文写；`bin/decision-inbox` 用 POSIX 兼容的 bash，不依赖 GNU 专有选项（macOS 自带工具）。

## 测试策略

- 单元测试：
  - `shim` 写入、内容不变不重写、`--if-installed` 时目录不在什么都不做；
  - `whoami` 和 `hook stop` 按 `cwd` 找：开发线的仓库、仓库子目录、onboarding 记下的规则文件目录、对不上、对上多个；
  - 默认命令路径是固定路径。
- 打包测试：
  - 两份清单名字和版本一致；`marketplace.json` 指向仓库根目录；`hooks.json` 是合法 JSON，含 Stop 和 SessionStart，命令里不带 `--group`；
  - 8 个命令文件都有 `description`，用到的子命令都存在；
  - 技能文件有 `name`、`description`；
  - 在 `PLUGIN_ROOT` 指向临时副本的环境下跑 `hooks.json` 里的两条命令：放行退出码 0；有人在等时输出 block JSON。
- 实测（最终验收前，先问用户；会改你本机的 Claude Code 插件配置）：
  1. 用 `claude plugin marketplace add <本 worktree>` 和 `claude plugin install` 装上插件；
  2. 在 scratchpad 临时目录里用 `/decision-inbox:hub-setup` 接入一个临时协作组，按提示建巡视任务、`onboard task` 记编号，请你手动「立即运行」一次，看运行记录；
  3. 在另一个临时项目里开一个桌面版会话，用 `/decision-inbox:join` 接入，制造「有人在等它」的状态，看插件自带的停止钩子拦一次、放一次；
  4. `/teardown` 删除巡视任务，`/leave` 卸载，最后卸载插件和 marketplace。
  
  Codex 侧只做安装，并确认技能和钩子出现在 `codex plugin list` 里；Codex 会话里的实测放到第六阶段。

## 边界

- 始终：钩子出任何问题都放行；斜杠命令里的接入、卸载先预览、经用户确认；查询结果原样显示。
- 先问：实测里安装插件、开新会话、建定时任务。
- 绝不：钩子里联网或调用 agent-relay；改用户的 `~/.claude/settings.json`；删 `~/.decision-inbox`。

## 验收标准

1. `shim`：写出可执行的转发脚本，执行它等于执行插件的 `bin/decision-inbox`；内容不变不重写（修改时间不变）；`--if-installed` 时 `~/.decision-inbox` 不存在就什么都不建。
2. `whoami`：开发线的仓库目录和它的子目录、onboarding 记下的规则文件目录都能认出；已退出的会话认不出，重新接入后又能认出；对不上退出码 4；对上多个退出码 5，并列出是哪几个。
3. `hook stop` 不带 `--group`：有人在等时拦下；目录没接入时静默放行；对上多个时放行，并在 stderr 说明；带 `--group` 的原有行为不变。
4. 默认命令路径：收件枢纽约定块、巡视提示词、onboarding 的步骤里，命令都是 `~/.decision-inbox/bin/decision-inbox` 展开后的绝对路径；`onboard hub`、`onboard join` 确认时写出转发脚本。
5. 清单与 `marketplace.json`：名字、版本一致；Codex 清单含 `skills`、`hooks`。
6. `hooks.json`：两条命令在 `PLUGIN_ROOT` 或 `CLAUDE_PLUGIN_ROOT` 下都能跑；两者都没有时放行、退出码 0、没有 stdout。
7. 8 个斜杠命令和 1 个技能：都有 `description`；接入、卸载类命令写明「先预览、用户确认后加 --confirm」；用到的子命令都存在。
8. README 含：安装（两边）、接入顺序、日常用法、升级、卸载（`~/.decision-inbox` 保留）、排查。
9. 原有子命令和测试不受影响。
10. 实测：按测试策略走完，记录写进本规格的「实测记录」。其中包括从 onboarding 挪过来的「按提示建巡视任务并手动立即运行一次」。

## 实测记录

2026-10-17 00:40–12:25，用户同意后做，后半段用户授权全权操作。用了真实的 `~/.decision-inbox`，测试协作组 `pp-probe`；scratchpad 里建了三个临时目录 `pp-hub`、`pp-fe`、`pp-api`；agent-relay 测试身份 `di-pp-hub`、`di-pp-fe`。

| 步骤 | 结果 |
|---|---|
| `claude plugin validate .` | 通过；marketplace 缺描述的警告已补；「根目录 CLAUDE.md 不作为插件内容加载」的警告属于假设 3，不影响 |
| `claude plugin marketplace add` + `install`（scope user） | 识别出 8 个命令、1 个技能，钩子 Stop 和 SessionStart；插件被复制到 `~/.claude/plugins/cache/decision-inbox-marketplace/decision-inbox/0.0.2` |
| 新会话 pp-hub 运行 `/decision-inbox:hub-setup pp-probe di-pp-hub` | **发现**：命令里写的 `${CLAUDE_PLUGIN_ROOT:-$PLUGIN_ROOT}` 没有被替换，Bash 里取到的是空值。改成原样写 `${CLAUDE_PLUGIN_ROOT}`，加测试，重装（5b4c358）。pp-hub 本轮改用实际安装路径完成：预览 → 用户确认 → 写 `CLAUDE.md`、建组、写转发脚本 → `bridge_register` → `create_scheduled_task`（`*/5 * * * *`）→ `onboard task` 记下编号 |
| 巡视任务第一次运行 | 成功；按固定路径跑完 `patrol plan` 和 `patrol record`，留下 `patrol.run` 事件；没有停在权限确认上（任务保存为 Auto 模式） |
| 新会话 pp-fe 运行 `/decision-inbox:join pp-probe dev di-pp-fe 前端 前端` | 修正后的命令里 `${CLAUDE_PLUGIN_ROOT}` 被替换成插件目录，一次跑通；预览 → 用户确认 → 写 `CLAUDE.md`、登记名册（含 `desktopSession`）、`bridge_register` |
| SessionStart 刷新转发脚本 | pp-fe 开会话后，转发脚本从缓存目录改指向本次加载的插件目录，说明自动刷新生效 |
| 名册加 API（`pp-api`），开等待单「API 等前端」，请 pp-fe 回一句后结束 | 插件自带的 Stop 钩子拦了一次，pp-fe 复述第一行「【decision-inbox】收工前请先处理：有会话在等你。」；第二次结束放行 |
| 定时巡视（每 5 分钟，共 131 轮） | 等待单开出后的第一轮（相隔 5 秒）判为信号 1「全线互等」，发了桌面通知并叫醒收件枢纽，两个动作都记为完成；其余各轮没有动作、没有报错 |
| 卸载：pp-hub 运行 `/decision-inbox:teardown`、pp-fe 运行 `/decision-inbox:leave` | 两边预览正常。pp-hub 收到主会话转达的用户授权后执行：约定块删除、`delete_scheduled_task` 删除任务、状态目录保留。pp-fe 不认其他会话转来的批准（符合约定），由主会话用同一命令加 `--confirm` 执行，规则文件只剩原有一行 |
| 卸载后核对 | **发现**：退出后 `whoami` 仍认出该目录，钩子仍会拦。原因是名册保留，却没有「已退出」记号。修正：退出时在领域 `onboarding` 记下「已退出」，按目录查找时跳过，重新接入时清掉（59aa8c8，含测试）。补跑确认后 `whoami` 退出码 4，钩子静默放行，一致性正常 |
| 卸载插件和 marketplace | 插件列表与安装前相比只差 spec-guard 自己从 0.64.0 升到了 0.64.2（与本插件无关）；marketplace 列表一致 |
| Codex：`codex plugin marketplace add` + `codex plugin add` | `codex plugin list` 显示 installed, enabled, 0.0.2；缓存里有 `.codex-plugin/plugin.json`（含 skills、hooks）、接入技能、`hooks.json`，启动脚本可执行；Stop 钩子命令以缓存副本运行退出码 0。随后 remove，`~/.codex/config.toml` 与安装前逐字节一致 |

留下的东西：`~/.decision-inbox/pp-probe`（按规定保留）和 `~/.decision-inbox/bin/decision-inbox`；agent-relay 测试身份 `di-pp-hub`、`di-pp-fe`，待用户退役；131 个巡视运行会话和 pp-hub、pp-fe 两个会话，待用户决定是否归档。

## 假设

1. Claude Code 在插件根目录有 `hooks/hooks.json` 时自动加载，命令从 `commands/` 自动发现；同一目录下的 `marketplace.json` 和 `plugin.json` 可以共存（spec-guard 等插件就是这样放的）。
2. Codex 的钩子环境里有 `PLUGIN_ROOT`，Claude Code 的有 `CLAUDE_PLUGIN_ROOT`（spec-guard 的 `hooks.json` 两个都兼容）。
3. 插件目录就是仓库根目录，安装后会带上 `spec/`、`tests/`、`docs/`；第一版接受，第六阶段发布前再定要不要拆到子目录。

## 未决问题

无。

## 文档建议

README 由本模块写（见关键决策 7）。能力图全部完成后，另外建议补 CHANGELOG（0.0.2），放到第六阶段发布前再写。
