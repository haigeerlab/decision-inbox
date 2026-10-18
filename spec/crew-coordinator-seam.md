<!-- spec-guard: review approved 4d8fee30ef5e -->
# Spec: crew-coordinator-seam

> 能力图模块 `crew-coordinator-seam`，2026-10-18 用 add-module 插入，排在 hub-patrol 之后。来源是 LIVE-SAAS 联合接入的「插件补改」阶段，对应接入方案的 D3、D4，以及接缝联合检查 JOINT-SEAM-CHECK.md 的 S1、S8、S9。用户 2026-10-18 在本会话直接同意插入，Spec 先交审。

## 目标

module-crew 的协调会话按 B 方式接入（角色 dev、line 填前端、挂审查者），要做到三点：

- 约定块不被模块 worktree 继承；
- 协调会话「模块在干活、自己收工」不被停止钩子误拦；
- 约定块和 crew-coordinator skill 分工清楚。

另外顺带修一个普通开发线也有的缺口：当前模块已经挂起时，停止钩子仍然会拦。

## 现状（已核对代码）

- `onboard join` 把约定块写进 `<项目目录>/<RULES_FILES[host]>`，Claude 写的是 `CLAUDE.md`（`onboard.py` 第 264、451 行）。在集成 checkout 里，CLAUDE.md 由 git 跟踪：如果提交了，模块 worktree 会继承协调会话的身份；如果不提交，module-crew 的检查（`git status --porcelain` 只要有任何一行就挡住）会把它当成未提交的改动。
- `leave` 在带 `--project` 时，按 `RULES_FILES[host]` 重新拼出规则文件路径（第 491 行）；doctor 用接入记录里的路径（`doctor.py` 第 64 行），按 `block(role, group, hub, checkpointAuthority)` 生成期望内容来比对。
- 停止钩子的 `_silent_stop`（`stophook.py`）：对 dev 角色，只要当前模块的 todo 没勾完、本会话又什么都没报，就拦一次。它**不看模块状态**：spec-guard 读取器其实已经读到了 `status`（挂起时是 `suspended`）和 `suspended_reason`（`specguard.py` 第 106、168–170 行），主视图也在用（`mapview.py` 第 27 行），只有停止钩子没用上。
- LIVE-SAAS 的集成 checkout 会继承 `activeModule=multi-page-pwa-lifecycle`，这个模块已经挂起，todo 也没勾完。
- Claude Code 官方文档（code.claude.com/docs/en/memory）写明：`CLAUDE.local.md` 和 `CLAUDE.md` 一起加载，要自己加进 `.gitignore`；被忽略的 `CLAUDE.local.md` 只存在于创建它的那个 worktree；另外，只要有 `CLAUDE.md` 或 `CLAUDE.local.md`，Claude 默认就不再读 `AGENTS.md`。

## 要做的

1. **约定块写进 CLAUDE.local.md**：`onboard join` 增加 `--local-rules`，只对 Claude（`claude-desktop`）有效，对 Codex 直接报错。打开后：
   - 约定块写进 `<项目目录>/CLAUDE.local.md`；接入记录和名册条目都记下这个选择（条目字段 `localRules: true`）。之后 `leave`（不论带不带 `--project`）、doctor、重跑 join 都找这个文件。
   - 预览时用 `git check-ignore -q CLAUDE.local.md` 核对这个文件有没有被忽略：
     - 已经被忽略：照常写；
     - 没被忽略：预览写明「确认时在本仓库 git 公共目录的 `info/exclude` 里加一行 `CLAUDE.local.md`」。这一行只影响本机，不改仓库里的任何文件，所有 worktree 共用这份设置。确认时执行，并把加过这一行记进接入记录，`leave` 时删掉它（只删本插件加的那一行）；
     - 项目不是 git 仓库：照常写，不做核对。
   - 项目目录有 `AGENTS.md`、却没有 `CLAUDE.md` 时，预览要警告：「加了 CLAUDE.local.md 之后，Claude 默认不再读 AGENTS.md」。只警告，不拦。
2. **「并行开发协调会话」标记**：
   - `onboard join` 增加 `--crew-coordinator`，只允许和 `--role dev` 一起用；名册条目记 `crewCoordinator: true`。
   - 这个标记**只能在接入时、经用户确认（`--confirm`）后写入**。会话不能自己声明，也没有别的命令能写它；`store` 校验名册时，`crewCoordinator` 只认布尔值，并且只认 dev 角色。手改名册得到的标记，不在本模块的防护范围内，见「范围」。
   - 有这个标记时，约定块在「开发线」一节后面多一节「并行开发协调会话」，内容如下：
     - 你代表这条线和收件枢纽说话，模块会话只和你说话；
     - 模块在干活、你在等它们时收工，不用抛【等待用户】；
     - 几个模块的事要合成一项抛出，或者写【与 #旧编号 并行】，否则后发的会默认取代先发的；
     - 收到【用户答复】、转给模块、模块开工之后，立刻发【已恢复】，结束行写这个编号，不用等模块做完；
     - 跨线请求每个模块开一张【等待其他会话】，「等什么」开头写模块 id；
     - 【答复告知】只记录，不执行；
     - 分工：对用户和收件枢纽的事，以本约定块为准；crew 内部的事，以 crew-coordinator skill 为准；谁的话算用户决定，以 session-protocol 契约为准。
   - doctor 生成期望的约定块时，要带上这个标记（以及上面 1 的 localRules）。
3. **停止钩子**（`_silent_stop`）：
   - 当前模块状态是 `suspended` 时不拦。这一条**对所有开发线都生效**。
   - 名册条目带 `crewCoordinator` 时，不做「当前模块没勾完」这项检查，因为模块进度归 module-crew 管。另外两项照常拦：有人在等本会话；用户已答复、本会话还没发【已恢复】。
   - 普通开发线（不带标记）的行为不变。
4. **文档**：README 的接入一节，写明 `--local-rules` 和 `--crew-coordinator` 的用法和适用场景，并引用宿主差异：Claude 读 CLAUDE.local.md 时不再读 AGENTS.md。
5. **版本 0.0.16**。

## 关键决策与取舍（请重点审）

1. **忽略规则写进 `.git/info/exclude`，不改 `.gitignore`**：exclude 只影响本机，不进仓库，符合「不改 LIVE-SAAS 的文件」，用户决定 21 也允许这样做。代价是换一台机器不生效，但协调会话本来就在这台机器上。
2. **标记只经 `onboard join --confirm` 写入**：和「检查点答复即授权」（`checkpointAuthority`）是同一个模式，接入预览本身就交给用户看。不另做签名或校验：名册在用户自己的目录里，手改名册属于用户本人的操作。
3. **挂起模块不拦，对所有开发线生效**：挂起本来就是「在等外部条件」，这时不该被要求抛事项。这修的是一个通用缺口，不只为了协调会话。
4. **不新增角色**：协调会话仍是 dev。B 方式已经和 module-crew、监测会话对齐，主视图、审查行、多线规则都照旧，改动最小。
5. **约定块内容只写和收件枢纽接口有关的规则**：crew 内部怎么开工、合并，不写进约定块，避免两边重复、互相矛盾。

## 范围

做：`decision_inbox/onboard.py`（两个参数、写 CLAUDE.local.md、exclude、协调会话一节）、`store.py`（条目字段校验）、`stophook.py`、`doctor.py`（期望约定块）、`__main__.py`（参数）、`commands/join.md` 与 `skills/decision-inbox-join`（组装 join 命令的地方）、README、两份 `plugin.json`，以及对应测试。

不做：
- 主视图显示并行模块状态（D5）、doctor 看到 module-crew（D6）：这两项要等 module-crew 发布只读出口；
- 过渡期兼容格式和「只登记」条目（D1、D8，模块 ③）；
- 改 module-crew 或 session-protocol；
- 防止有人手改名册。

## 验收标准

1. `join --local-rules` 时：
   - 约定块写进 CLAUDE.local.md，CLAUDE.md 一字不变；
   - 文件没被忽略时，预览写明并在确认时往 `info/exclude` 加一行，加过一次的不再重复加；已被忽略时不加；
   - `leave` 能找到这个文件、删掉约定块，并删掉本插件加的那一行 exclude；
   - doctor 能核对这个文件里的约定块；
   - Codex 加 `--local-rules` 报错。
   这些都有测试，exclude 用临时 git 仓库实测。
2. 有 AGENTS.md、没有 CLAUDE.md 时，预览有警告；有测试。
3. `--crew-coordinator`：
   - 只能和 dev 一起用；
   - 名册条目带上这个标记，约定块多出「并行开发协调会话」一节，doctor 期望的约定块也一致；
   - 不带这个参数重跑 join，标记被去掉。
   都有测试。
4. 停止钩子：
   - 当前模块挂起时不拦（普通开发线）；
   - 带协调会话标记、当前模块没勾完时不拦；
   - 带标记、但有人在等它，或者有已答复还没发【已恢复】的事项时，照常拦；
   - 普通开发线、当前模块没勾完时照常拦。
   都有测试，对应联合测试 T9 ①②②′④。
5. 原有测试全部通过；两份清单都是 0.0.16。
6. **实测（开始前另问用户）**：放到联合演练阶段，按 JOINT-TEST-LIST 的 P2、T9 跑。

## 假设

1. Claude 桌面版 Code 标签页里的会话，和 Claude Code 一样加载 `CLAUDE.local.md`。官方文档写的是 Claude Code；桌面版的行为放到联合演练（P2）实测，不行就回到这份 Spec。
2. 集成 checkout 是普通 git 仓库或 worktree，`git rev-parse --git-common-dir` 能找到公共目录。
3. module-crew 的模块 worktree 在仓库同级的 `<仓库名>-crew/`（module-crew `start.py` 第 103 行），停止钩子不会把模块会话认成协调会话。

## 未决问题

无。

## 文档建议

README：接入一节加 `--local-rules`、`--crew-coordinator`；使用注意事项里加一条「Claude 读 CLAUDE.local.md 时不再读 AGENTS.md」；docs/host-differences.md 可以补一条宿主差异（编号待定），记下这个加载规则和 worktree 不继承 CLAUDE.local.md 的事实。
