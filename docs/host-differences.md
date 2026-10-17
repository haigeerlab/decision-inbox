# Claude 桌面版与 Codex 桌面版的宿主差异（多会话协作视角）

| 项 | 内容 |
|---|---|
| 文档日期 | 2026-10-16 |
| 适用范围 | 同一台 Mac 上，用 Claude 桌面版（Claude Code）与 Codex 桌面版（ChatGPT 应用内的 Codex）同时跑多个 AI 编码会话、并通过 agent-relay 互相协作 |
| 用途 | 开发 decision-inbox、spec-guard、agent-relay 这类跨宿主插件时，作为两个宿主行为差异的依据；也作为 decision-inbox 接入说明里「已知限制」的来源 |
| 证据来源 | 2026-10-13 至 2026-10-16 在一个真实多会话协作组（5 条开发线 + 总协调 + 负责人 + 收件枢纽）上的观测；spec-guard、agent-relay 仓库的设计文档 |

## 证据等级

| 标记 | 含义 |
|---|---|
| **实测** | 在下文列出的版本上亲自观测或复现过，附时间和现象 |
| **文档** | 来自 spec-guard / agent-relay 仓库已发布的设计文档或升级说明，未在本次逐项复现 |
| **未验证** | 合理推断或尚未测试，不能作为设计依据 |

宿主行为会随版本变化。引用本文结论前，先用第 6 节的命令核对版本；版本不同的，按「未验证」对待。

---

## 1. 结论摘要

1. **会话生命周期相反**：Claude 桌面版会**挂起空闲会话**，agent-relay 叫不醒，只能由另一个 Claude 会话用桌面版自带的会话消息工具叫醒；Codex 桌面版的空闲会话能被 agent-relay 直接叫醒，但**应用一重启，所有会话都不会自动加载**，必须用户逐个点开。（H1、H2、H4）
2. **Codex 会话会丢联调身份**：长时间空闲或应用重启后，会话常以「不是本会话的身份」读不到自己的消息，需用原名重新登记；期间即使会话在运行，agent-relay 仍判它离线。（H3）
3. **Codex 原生跨会话消息不推回结果**，跨会话的请求与回复必须走 agent-relay 邮箱。（H5）
4. **审批模型不同**：Codex 的自动审批不认其他会话转来的批准，必须用户在原会话亲口确认；任何会话都看不到别的会话里弹出的宿主确认。（H10、H12）
5. **插件机制不同**：Claude 插件提供斜杠命令、更新后新开会话即可；Codex 插件只能提供技能、更新后要完全退出 ChatGPT 应用；Codex 钩子必须在命令行版里信任，桌面版不会提示。（H6、H7、H8）

---

## 2. 测试环境与版本

| 组件 | 版本 | 取得方式 |
|---|---|---|
| macOS | 15.7.3（24G419） | `sw_vers` |
| Claude 桌面应用 | 2.42304.0 | `defaults read /Applications/Claude.app/Contents/Info.plist CFBundleShortVersionString` |
| Claude Code | 2.1.299 | `claude --version` |
| ChatGPT 应用（含 Codex 桌面版） | 26.1007.71326（build 20398） | `defaults read /Applications/ChatGPT.app/Contents/Info.plist CFBundleShortVersionString` / `CFBundleVersion` |
| ChatGPT 应用内置 codex | codex-cli 0.162.0-alpha.17.2 | `/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex --version` |
| 命令行版 codex | codex-cli 0.162.1（nvm 安装） | `codex --version` |
| agent-relay | 运行时 0.6.10 起（2026-10-16 当天升级）；Codex 侧插件缓存 0.6.11；运行时提交 `8f12c880` | `~/.codex/plugins/cache/agent-relay-marketplace/agent-relay/`、`~/.agent-relay/runtime/manifest.json` |
| spec-guard | 0.63.0（两个宿主） | `~/.claude/plugins/installed_plugins.json`、`~/.codex/plugins/cache/spec-guard-marketplace/spec-guard/` |

注：观测期间 agent-relay 从 0.6.9 升到 0.6.11；与版本相关的现象在条目里注明。Claude 侧插件安装记录里的 agent-relay 版本号停留在 0.6.1（2026-10-09 写入），但两边共用同一个运行时（`~/.agent-relay/runtime`），实际行为以运行时为准。

---

## 3. 差异明细

### 3.1 会话生命周期与唤醒

#### H1 空闲会话：Claude 会被挂起，Codex 不会

| | Claude 桌面版 | Codex 桌面版 |
|---|---|---|
| 行为 | 应用会停止空闲会话；这是实验中**最常见的掉线原因**，每天多次 | 空闲会话保留，agent-relay 可直接让它开始新一轮 |
| 证据 | **实测**：agent-relay 唤醒记录为 `Claude session is not running (the Claude app may have stopped it while idle); the message waits and is delivered once that session is opened` | **实测**：唤醒记录为 `Codex confirmed a new turn` |
| 影响 | 收件枢纽、负责人这类 Claude 会话会周期性「消失」，期间待答表看起来是空的 | 只要应用没重启，叫醒可靠 |

#### H2 应用重启后：Codex 会话不自动加载

- **现象**：ChatGPT 应用重启后，之前的 Codex 会话在用户点开前都不会加载；发给它们的消息投递状态停在排队，唤醒按「离线」重试，直到用户点开。
- **证据（实测）**：2026-10-16 两次重启（14:14:54、15:56:42）。第一次：发给两个会话的唤醒分别重试 29 次和 23 次以上，记录为 `Codex local connection unavailable`；第二次：三个会话各重试 7 次，agent-relay 0.6.11 的记录为 `The ChatGPT app did not answer for this Codex task, usually because it was not opened since …`。用户点开后，三个会话在 1 分钟内全部开始处理，消息无丢失。同期两个测试用 Codex 会话收发正常，排除 agent-relay 整体故障。
- **Claude 对照**：Codex 重启不影响 Claude 会话。
- **对策**：重启 ChatGPT 应用后，逐个点开参与协作的 Codex 会话；唤醒只重试约 1 小时，超时后点开还需让会话主动读一次收件箱。

#### H3 联调身份丢失：只在 Codex 侧观察到

- **现象**：会话被点开后读收件箱，返回 `readRecorded: false`，`readNote` 为 `"<名字>" is not an identity of this session`；会话自己用原名重新登记后恢复。期间 agent-relay 仍把这个**正在运行**的会话判为离线、继续重试唤醒。
- **证据（实测）**：2026-10-16 共 4 次：长时间空闲的两个会话被点开时各 1 次（13:06）；应用重启后两个会话各 1 次（14:51），其中一个会话已正常回答用户，但发给它的消息仍是排队、未读。
- **Claude 对照**：观测期内未见 Claude 会话出现此提示（**未验证**是否不会发生）。
- **状态**：已作为实证提交 agent-relay 维护方，评估「身份失效自愈」的优先级。

#### H4 谁能叫醒已停止的 Claude 会话

- **结论**：agent-relay 叫不醒已停止的 Claude 会话；Claude 桌面版自带的会话消息工具可以叫醒，但它只能在 Claude 会话内部调用，外部进程（包括 agent-relay）调不到。
- **证据（实测）**：2026-10-16 13:36，由 Claude 桌面版定时任务启动的一次性会话调用该工具，向一个空闲的 Claude 会话发消息，状态 `delivered`，目标会话随即开始处理。
- **影响**：decision-inbox 的巡视必须运行在 Claude 侧（定时任务或收件枢纽），由它负责叫醒 Claude 会话；这是「唤醒归 agent-relay」原则下唯一的例外。

### 3.2 会话之间的消息

#### H5 原生跨会话消息

| | Claude 桌面版 | Codex 桌面版 |
|---|---|---|
| 原生工具 | 桌面版会话消息工具：消息以一轮用户输入送达目标会话，能叫醒已停止的会话 | `send_message_to_thread`：能把请求送到对方，但**对方的结果不会推回请求方** |
| 证据 | **实测**（见 H4） | **实测**：2026-10-16 统计，总协调与 4 条开发线之间约 193 次原生请求，邮箱里对应回复为 0；请求方要靠外部提醒才去对方会话取结果 |
| 结论 | 可用于兜底叫醒 | 跨会话请求与回复一律走 agent-relay 邮箱（agent-relay 0.6.9 起，Codex 之间派活默认走邮箱并按 `replyTo` 推回） |

### 3.3 插件机制

#### H6 安装与更新后的生效方式（文档）

| | Claude Code | Codex |
|---|---|---|
| 更新 | `claude plugin marketplace update <市场>`，`claude plugin update --scope user <插件>@<市场>` | 改 `~/.codex/config.toml` 里该市场的 `ref`，`codex plugin marketplace upgrade`，`codex plugin add <插件>@<市场>` |
| 生效 | **新开会话**即用新版本；已开着的会话仍是旧版本 | **⌘Q 完全退出 ChatGPT 应用再打开**（随之触发 H2） |

来源：agent-relay 0.6.10 升级说明。

#### H7 插件能提供的入口（文档）

| | Claude Code | Codex |
|---|---|---|
| 命令 | 插件可注册**斜杠命令**（如 `/spec-guard:map`） | 插件**不能注册斜杠命令**，只能提供技能，用自然语言或 `$技能名` 触发 |
| 插件根目录变量 | `CLAUDE_PLUGIN_ROOT`（命令里由宿主代入） | `PLUGIN_ROOT`；找不到时需查询 `codex plugin list` |
| 项目规则文件 | `CLAUDE.md` | `AGENTS.md` |
| 外部定位已安装插件 | `~/.claude/plugins/installed_plugins.json` 的 `installPath` | `~/.codex/plugins/cache/<市场>/<插件>/<版本>/` |

来源：spec-guard `docs/design.md`「两个宿主的差异」。

### 3.4 钩子

#### H8 钩子信任

| | Claude Code | Codex |
|---|---|---|
| 信任方式 | 首次使用时在 `/hooks` 中信任（**文档**） | **桌面版从不弹出信任提示**；必须在项目目录运行命令行版 `codex`，在「Hooks need review」中信任，写入 `~/.codex/config.toml` 的 `[hooks.state."<路径>/.codex/hooks.json:stop:0:0"] trusted_hash`（**实测**） |
| 修改钩子后 | — | 命令一变 `trusted_hash` 就失效，**必须重新信任**（**实测**） |
| 设计约束 | — | 钩子命令要尽量稳定；信任只能由用户亲自在终端操作 |

#### H9 停止钩子（Stop hook）

- **Codex（实测）**：命令行版 0.162.1 与桌面版内置 0.162.0-alpha.17.2 都会触发 `Stop`。返回 `{"decision":"block","reason":"…"}` 时，`reason` 喂回模型并**在同一轮继续**；再次触发时输入带 `stop_hook_active: true`，此时应放行以免死循环。输入还包含 `last_assistant_message`、`cwd`、`turn_id`。
- **Claude 桌面版**：**未验证**（本次未在 Claude 桌面版工作会话上测试停止钩子的拦截效果）。

### 3.5 权限与审批

#### H10 审批模型

| | Claude 桌面版 | Codex 桌面版 |
|---|---|---|
| 机制 | 按会话的权限模式（默认 / 自动 / 跳过）弹出确认 | 带自动审批；对写规则文件、改审计策略等动作做判断 |
| 转交的批准 | 不适用 | **不认**：用户在收件枢纽批过、由其他会话转来的批准，自动审批仍拒绝，要求用户在**该会话里直接**写出批准原话（**实测**，2026-10-16 两次：写长期规则文件、更新审计指纹） |
| 定时任务 | 创建时若没保存权限模式，运行用默认模式，会停在确认上；运行中批准的工具会记到任务上（**实测**） | 未验证 |

#### H11 沙箱（文档）

Codex 默认的 workspace-write 沙箱不允许写 `.git`，会话每次提交都要申请提权、由用户审批。Claude Code 无此限制。

#### H12 别的会话看不到宿主弹窗（两边相同）

- 任何会话都看不到别的会话里弹出的宿主确认。
- **证据（实测）**：2026-10-16 定时任务运行会话自述「全程没有弹出要人确认的提示」，实际调用 agent-relay 工具时弹了确认、由用户手动点了允许，停顿约 3 分钟。
- **设计约束**：巡视与收件枢纽不能依赖会话对权限情况的自述；「要用户去原会话确认」必须作为显式事项上报。

### 3.6 可观测性与运行环境

#### H13 会话记录

| | Claude 桌面版 | Codex 桌面版 |
|---|---|---|
| 位置 | `~/.claude/projects/<项目>/` 下的 JSONL | `~/.codex/sessions/<年>/<月>/<日>/rollout-*.jsonl` |
| 读取 | 跨会话读取要通过桌面版会话工具 | 文件里有 `task_started`、`task_complete` 等事件，**直接读文件即可判断哪个会话停在哪一轮**（**实测**） |
| 上下文窗口 | 记录里不写窗口大小（**文档**） | 记录里有窗口大小（**文档**） |

#### H14 Codex 有两份可执行文件，版本不同（实测）

ChatGPT 应用内置一份 codex（0.162.0-alpha.17.2），命令行另装一份（0.162.1）。桌面版行为以内置那份为准；钩子信任却要用命令行版完成（H8）。两份版本可能不同步，排查问题时要分别核对。

#### H15 定时任务

- **Claude 桌面版（实测）**：一次性定时任务按时启动（无延迟），能运行 Bash、只读查询 SQLite、调用 agent-relay MCP 工具、调用会话消息工具。周期任务每次触发有几分钟的负载均衡延迟（**文档**：工具说明）。周期间隔的实际值、应用关闭时的补跑行为**未验证**。
- **Codex 桌面版**：**未验证**。

### 3.7 使用习惯

#### H16 收件枢纽放在哪个宿主

- **实测**：收件枢纽放在 Codex 侧边栏时，它只是众多会话之一，13 项待决定事项里只有 5 项经它答复；移到用户平时审查所在的 Claude 桌面版后，绝大多数事项都经它答复。
- **结论**：收件枢纽固定放在 Claude 桌面版。

---

#### H17 自动压缩后容易抓「最近一条人工输入」当任务（Codex，待复核）

- **现象**：长会话在一轮中途自动压缩后，模型倾向于把**压缩前最近一条用户亲手输入**当成当前任务，而不是压缩前正在做的、由邮箱转来的新任务；核对发现旧任务已完成后直接结束这一轮。
- **证据（实测，3 次）**：2026-10-15 两次；2026-10-16 18:11:19 一次——会话正按邮箱转来的用户答复为新模块写 Spec，压缩后转去复核 8 小时前用户亲手发的一条旧批准，报告「已执行，不重复覆盖」后结束，新模块 Spec 一字未写。压缩时 spec-guard 注入了正确的当前模块与下一步，仍未接上。
- **推测机制（未验证）**：经 agent-relay 邮箱送达的任务不以「用户消息」形式进入会话记录，压缩摘要里保留的最近人工输入因此权重更高。
- **Claude 对照**：未观察到（**未验证**）。
- **设计约束**：停止钩子要能拦下「有人在等本会话交付却收工」；压缩后提示应明确「核对后接着做建议的下一步」（已作为改进建议提交 spec-guard 负责人）。

---

## 4. 对 decision-inbox 设计的约束汇总

| 约束 | 来源条目 |
|---|---|
| 收件枢纽与巡视运行在 Claude 桌面版 | H4、H15、H16 |
| 叫醒 Claude 会话由本插件做（会话消息工具），叫醒 Codex 会话交给 agent-relay | H1、H4 |
| 巡视要把「Codex 会话未加载」「身份未对上」识别为独立原因，提示用户点开或让会话重读收件箱 | H2、H3 |
| 接入说明写明：重启 ChatGPT 应用后逐个点开协作中的 Codex 会话 | H2 |
| 跨会话请求与回复一律走 agent-relay 邮箱 | H5 |
| Codex 侧查询做成技能，Claude 侧做斜杠命令 | H7 |
| 停止钩子命令保持稳定；Codex 侧接入后提示用户在命令行版信任 | H8 |
| 「要用户去原会话亲自确认」作为显式事项上报，算进「等你决定」 | H10、H12 |
| 不依赖会话对权限情况的自述 | H12 |
| 停止钩子拦下「有人在等本会话交付却收工」，覆盖压缩后跑偏 | H17 |

## 5. 未验证 / 待复核

1. Claude 桌面版工作会话上的停止钩子拦截效果（H9）。
2. Claude 会话是否也会出现联调身份丢失（H3）。
3. Claude 桌面版周期定时任务的实际间隔、应用关闭时的补跑（H15）。
4. Codex 桌面版是否有可用于巡视的定时任务（H15）。
5. Codex 压缩后抓最近人工输入的机制（H17），以及 Claude 侧是否同样发生
6. agent-relay「身份失效自愈」上线后，H2、H3 的对策是否可以自动化。

## 6. 复核方法

```bash
sw_vers
claude --version
codex --version
/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex --version
defaults read /Applications/Claude.app/Contents/Info.plist CFBundleShortVersionString
defaults read /Applications/ChatGPT.app/Contents/Info.plist CFBundleShortVersionString
```

- H2：重启 ChatGPT 应用后，给一个未点开的 Codex 会话发 agent-relay 消息，查 `~/.agent-relay/runtime/mailbox/bridge.sqlite` 的 `wake_jobs`（`state`、`attempts`、`pending_reason`、`detail`）；点开会话后再查一次。
- H3：在长时间空闲或重启后点开的 Codex 会话里读收件箱，看返回的 `readRecorded` 与 `readNote`。
- H5：用 `send_message_to_thread` 派一个任务，对方完成后检查请求方是否收到结果。
- H9：在 `.codex/hooks.json` 配一个返回 `decision:block` 的 Stop 钩子，经命令行版信任后在桌面版触发。

## 修订记录

| 日期 | 变更 |
|---|---|
| 2026-10-16 | 初版：16 条差异，基于 2026-10-13 至 10-16 的实测与两个插件仓库的文档 |
| 2026-10-17 | 新增 H17（Codex 自动压缩后抓最近人工输入当任务，待复核） |
