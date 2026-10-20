<!-- spec-guard: review pending -->

# Spec: patrol-launchd

> 能力图模块 `patrol-launchd`（插入待用户经统筹确认，排在 stage-c2-fixes 之后）。来源：统筹派活，`livesaas-integration/REQ-R22-STAGE-C-FIXES.md` 的 DI-11 前半句。用户已定：短验证结束前只写 Spec，不写 Plan、不写代码。

## 目标

巡视有独立于收件箱和任何会话的定时触发：本机 launchd 每 5 分钟直接跑一轮巡视（读状态 → 算动作 → 叫醒、提醒、通知 → 记录），不再靠一个 `/loop` 的巡视会话。跑不成时直接弹系统通知告诉用户。

DI-11 的验收：「人为停掉巡视后，在设定时间内用户收到提醒；恢复后提醒消失」。

## 现状

- 巡视每轮由巡视会话（`/loop 5m`）里的模型执行：用 MCP 读 `bridge_agents`、`bridge_outbox`、`bridge_sessions`，运行 `patrol plan`，再按动作调用工具：`wake` 用桌面版 `send_message` 发给会话编号；`owner-alert` 用 `bridge_send`；`notify` 运行 `decision-inbox notify`。最后运行 `patrol record`。
- 巡视会话一停（卡在权限确认、循环断了、被桌面版收起），巡视就停了。0.0.31 起的 launchd 任务（`onboard watch`，每 5 分钟）只能在停了以后提醒用户，不能替它跑。
- 收件箱自己也能顺带跑一轮（hub-patrol，`--from-hub`），只在收件箱被叫醒时发生。
- agent-relay 0.9.0（接口 2.8，已发版 efaae59）提供脚本命令（接口文档 §2.4、`interface.json` 的 `script`），启动脚本是 `~/.agent-relay/bin/agent-relay`：
  - 只读：`agents`、`outbox <名>`、`sessions`，输出和对应 MCP 工具逐字段一致，不改信箱状态；
  - 发信：`send --from <脚本身份> --to <名>`，正文来自 `--body-file` 或标准输入，发出后为这条投递一次唤醒；
  - 登记脚本身份：`register-script-identity <名> --confirm`，由用户在终端运行。
- 2026-10-20 实测：在只有 `/usr/bin:/bin` 的环境里，`agents`、`sessions`、`outbox di-p0-hub` 都退出 0，字段和 MCP 一致（`sessions` 的 `thisSession` 为空）。
- agent-relay 方说明了三条限制：
  1. 被桌面版停掉的 Claude 会话，脚本发信也叫不醒，只能等 agent-relay 5 分钟后通知用户；Codex 任务要在 ChatGPT 里已加载才叫得醒。
  2. 脚本身份永远不会被唤醒，回给它的信只能靠下一轮用 `outbox`／`agents` 去读。
  3. 脚本身份由用户在终端登记；收件箱要另起一个名字。

## 假设（请确认）

1. **做法 A（推荐）：launchd 直接跑巡视，巡视会话退役。** 现在的巡视提醒任务改成跑新命令 `decision-inbox patrol tick <组>`，每 5 分钟一次：
   - 用脚本命令读三份状态；
   - 运行和现在一样的 `patrol.plan`；
   - 执行动作；
   - 运行 `patrol.record`。

   巡视会话不再需要。
   - 另一种做法 B：保留巡视会话，launchd 只在它停了的时候补跑一轮。两边会抢同一轮，还要判断「巡视会话停了没有」，更复杂；巡视会话卡在权限确认上的问题也还在。所以推荐 A。
2. **动作怎么执行**：
   - `wake`：用脚本身份向对方**邮箱名**发一封信，正文就是现在的唤醒文字，不要求回复。信发给邮箱名，谁持有这个邮箱名就叫醒谁，所以名册过期时也不会叫错人。被桌面版停掉的会话叫不醒；下一轮还在积压时，沿用现在「叫不醒，请手动打开 <链接>」的通知（链接按 roster-stale-wake 的核对结果给）。
   - `owner-alert`：同样用脚本身份发信，不要求回复。
   - `notify`：和巡视提醒现在一样，直接弹 macOS 通知。
   - 收件箱顺带跑的那一轮（`--from-hub`）不变，仍用桌面版 `send_message` 叫醒；它能叫醒被桌面版停掉的会话，正好补上脚本做不到的那部分。
3. **脚本身份**：
   - 默认名 `<收件箱邮箱名>-patrol`，比如 `di-p0-hub-patrol`。agent-relay 不允许会话接管脚本身份，所以不能和任何会话的邮箱名相同。
   - hub-setup 的后续步骤写出让用户在终端运行的登记命令：`~/.agent-relay/bin/agent-relay register-script-identity <名> --confirm`。用户登记后，运行 `decision-inbox onboard patrol-identity <组> --name <名>`，把这个名字记进协作组。
   - 还没登记或发信被拒时，这一轮的发信动作记为失败，并弹一次通知：「巡视发不出信：请在终端登记脚本身份 <名>」。
4. **跑不成就通知用户**：
   - `patrol tick` 读不到 agent-relay（启动脚本退出非 0，比如运行时没装、正在升级），就弹通知「巡视读不到 agent-relay：<原因>」，30 分钟内不重复。
   - 同一个 launchd 任务里，原来的巡视提醒检查（巡视超过 15 分钟没跑就提醒）照旧跑，所以任何原因停了都会提醒。
   - 恢复后，提醒随 `patrol-watch` 的现有逻辑消失。
5. **同时跑**：收件箱顺带的一轮和 launchd 的一轮可能撞在一起。加一个协作组级的文件锁 `~/.decision-inbox/<组>/patrol.lock`，拿不到锁的一方这一轮跳过。
6. **收件箱收到脚本身份的信**：巡视叫醒收件箱时，收件箱会收到脚本身份发来的信。收件箱只确认这封信，不退回、不登记成待决事项，也不回复（脚本身份收不到唤醒，回了也没人看）。
7. **巡视不等回复**：脚本身份发出的信都不要求回复，巡视不读回给它的信。
8. **launchd 任务和升级**：
   - 仍用 `onboard watch <组>` 预览、确认后安装，任务标识沿用现在的 `patrol-watch`，只把程序参数改成 `patrol tick`。
   - 升级时，收件箱重跑 hub-setup：步骤里先停止并归档巡视会话（0.0.36 在 `~/.decision-inbox/<组>/patrol` 开的那个），再登记脚本身份、重跑 `onboard watch --confirm`。
   - 0.0.36 的巡视目录以后不再使用，留着不删。
9. **环境**：launchd 任务跑的是 `~/.decision-inbox/runtime/` 下的副本（patrol-watch-runtime 的做法）；agent-relay 从 `interface.json` 的 `script` 一节取命令，`~` 换成 `$HOME`，不依赖 PATH。

## 要做的

1. 新增 `relay` 层的脚本调用：从 agent-relay 的 `interface.json` 读 `script` 命令，运行 `agents`、`outbox <名>`、`sessions`、`send`，结果交给现有的解析器。
2. 新增 `patrol tick <组>`：加锁 → 读状态 → `plan` → 执行动作 → `record` → 跑原来的巡视提醒检查。
3. 新增 `onboard patrol-identity <组> --name <名>`（预览、确认）；hub-setup 的后续步骤改成「登记脚本身份 → 记进协作组 → 装 launchd 任务」，不再开巡视会话，并停止、归档旧巡视会话。
4. `onboard watch` 的程序参数改成 `patrol tick`；doctor 的「巡视提醒」一项改名「巡视定时任务」，并检查脚本身份是否已登记。
5. 收件箱收到脚本身份的信时只确认。
6. README、`commands/hub-setup.md`、术语表跟着改；版本号到时再定（不在本 Spec 里定）。

## 做 / 不做

- 做：上面 1～6。
- 不做：
  - 替用户登记脚本身份（必须用户在终端自己做）；
  - 叫醒被桌面版停掉的会话（脚本做不到，只通知）；
  - 叫醒没加载的 Codex 任务（同上）；
  - 改 `patrol.plan` 的判断规则；
  - 改契约；
  - 在本机安装或升级。

## 验收标准

1. 在只有 `/usr/bin:/bin` 的环境里（`env -i`），用假的 agent-relay 启动脚本跑 `patrol tick <组>`：读三份状态、算出动作、`wake` 和 `owner-alert` 变成 `send --from <脚本身份> --to <邮箱名>`（正文走标准输入）、`notify` 弹通知、`record` 记下结果。
2. **重放 DI-11**：
   - 人为让巡视停掉（启动脚本退出 3），一轮之内用户收到「巡视读不到 agent-relay」通知，30 分钟内不重复；
   - 恢复后下一轮正常跑完，巡视提醒的状态清掉。
3. 脚本身份没登记（`send` 被拒）：这一轮的发信动作记为失败，用户收到一次「请在终端登记脚本身份」的通知。
4. 收件箱顺带跑的一轮拿着锁时，`patrol tick` 跳过这一轮，不重复发信。
5. 收件箱收到脚本身份的信，只确认，不退回、不登记成待决事项。
6. hub-setup 的预览：不再出现开巡视会话；有旧巡视会话时先停止、归档；写出登记脚本身份的终端命令和 `onboard watch`。
7. 用本机真实的 agent-relay 0.9.0 跑一次只读部分（`agents`、`outbox`、`sessions`），解析结果和 MCP 读到的一致。
8. 每条改动先有一条失败的测试；全量测试通过。

## 风险

- **被桌面版停掉的会话**：巡视改由 launchd 跑以后，这类会话只能等用户去点。收件箱被叫醒时顺带跑的一轮仍能用 `send_message` 叫醒它们，但那要看收件箱什么时候被叫醒。
- **唤醒信变成真信**：叫醒是一封真的信，对方要读、要确认。正文写明这是巡视的提醒、不用回复。
- **依赖 agent-relay 0.9.0**：低于 0.9.0（没有脚本命令）时，`patrol tick` 每轮都会报读不到，doctor 和通知会写明要升级 agent-relay。
- **0.0.36 的巡视目录刚上线就废弃**：留着不删，不影响使用；README 写明。

## 未决的小问题

- 版本号：等短验证结束、排期时再定。
- 默认脚本身份名是否接受 `<收件箱邮箱名>-patrol`。

## 文档建议

- README：巡视怎么跑、升级步骤（登记脚本身份、重跑 hub-setup 和 `onboard watch`）、排查表加两行（读不到 agent-relay；脚本身份没登记）。
- `commands/hub-setup.md`：不再开巡视会话。
- 术语表：加「脚本身份」。
