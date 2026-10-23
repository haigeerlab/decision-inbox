<!-- spec-guard: review approved -->

# Implementation Plan: patrol-launchd

> 依据：`spec/patrol-launchd.md`（已批准，cf2d8087bfc8）。任务清单：`tasks/patrol-launchd/todo.md`。分支 `claude/patrol-launchd`（从 main adcaede）。版本 0.0.38。

需要的外部条件：agent-relay 0.9.0（接口 2.8，本机已装）。不在本机安装或升级（Spec「不做」）。

## Overview

五个任务，每个先写在 adcaede 上失败的测试再改代码：脚本调用 → `patrol tick` → 脚本身份登记与收件箱收信 → hub-setup／`onboard watch`／doctor → 文档、术语表与版本。最后用本机真实 agent-relay 跑一次只读核对（验收 7），交最终验收，批准后推送、开 PR（base main，由用户合并）。

## Architecture Decisions

- **脚本调用放 `relay.py`**：`script_argv(kind, **subs)` 经 `deps.find("agent-relay")` 读 `interface.json` 的 `script` 一节，`~` 换成 `$HOME`，`<agent>`／`<script identity>` 代入；`run_script(kind, ...)` 用 `subprocess.run`（`stdin` 给正文或 `DEVNULL`，超时 30 秒），返回 `(退出码, stdout, stderr 首行)`。没有 `script` 一节（低于 0.9.0）或读不到接口时抛 `RelayUnreadable`，原因写「agent-relay 需升级到 0.9.0（没有脚本命令）」。读到的 JSON 交给现有 `parse_agents`／`parse_outbox`／`_sessions_read`，不另写解析器。
- **`patrol tick` 放新文件 `decision_inbox/tick.py`**，`__main__` 的 `patrol` 子命令加 `tick`。流程：拿锁 → `agents`／`outbox <收件箱>`／`sessions` → 存快照 → `patrol.plan`（与 `patrol plan` 同参）→ 执行动作 → `patrol.record` → 放锁 → `watch.check`。launchd 跑它，任何异常都吞掉、退出 0（沿用 `patrol-watch`）。
  - `agents` 读不到（启动脚本退出非 0 或没有脚本命令）：不跑 plan／record，弹「巡视读不到 agent-relay：<原因>」，状态记在 `patrol-watch` 域的 `relayDownAt`，30 分钟内不重复；下一轮读到就清掉。`outbox`／`sessions` 读不到只跳过对应检查（与现在一致）。
  - `wake`：动作编号是 `wake:<邮箱名>`，取出邮箱名，`send --from <脚本身份> --to <邮箱名>`，正文走标准输入，不要求回复；`owner-alert` 同样发给 `target`。`notify` 调 `watch.desktop_notify`。退出 0 记 done，否则记 failed。`plan` 的判断规则不动。
  - 没登记脚本身份（协作组没记 `patrolIdentity`，或 `send` 报 `is not a script identity`）：发信动作全记 failed，弹一次「巡视发不出信：请在终端登记脚本身份 <名>」；状态记 `identityMissingAt`，发信成功一次后清掉，同一段只弹一次。
- **锁**：`~/.decision-inbox/<组>/patrol.lock`，`os.open(O_CREAT|O_EXCL)` 写入 `{by, at}`；超过 10 分钟的锁视为残留，删掉重拿。`patrol tick` 拿不到就这一轮跳过（日志写一行）。收件箱的 `patrol plan --from-hub` 也拿这把锁、`patrol record` 放；它拿不到时写出 `skipped: true`、没有动作的计划，`record` 遇到 `skipped` 什么都不写。
- **脚本身份记在 onboarding 域**：`patrolIdentity`、`patrolIdentityAt`。`onboard patrol-identity <组> --name <名>` 预览／`--confirm`；名字与名册里任何邮箱名相同就拒（退出 2）；预览时用 `agents` 查它是否已登记为脚本身份（`host.app == "script"`），没登记写一行提醒，不拦。
- **巡视由谁跑**：`hub._patrol_runner` 先认 `patrolIdentity`（`launchd`），再认旧的 `patrolSession`／`patrolTask`。`patrol_alarm` 对 `launchd` 给的办法改成「运行 doctor 看巡视定时任务；没装或没加载就重跑 onboard watch --confirm」。
- **收件箱收到脚本身份的信**：`hub._dispatch` 在最前面认出发件人是本组 `patrolIdentity`，记为 `patrol` 类，只确认，不退回、不登记待决事项、不进「unknown」、不回复。
- **hub-setup 步骤**：去掉「开巡视会话」「onboard patrol-session」，不再打印巡视提示词；有旧巡视会话或旧定时任务时照旧先停止、归档／删除；新增「请用户在终端运行 `~/.agent-relay/bin/agent-relay register-script-identity <收件箱邮箱名>-patrol --confirm`」和「运行 `onboard patrol-identity <组> --name <收件箱邮箱名>-patrol`」，再接 `onboard allow`、`onboard watch`。teardown 加一行：脚本身份留着，要退役请用户用 `/agent-relay:collaboration`。`patrol prompt`、`onboard patrol-session` 两个命令保留不删（旧组还在用）。
- **`onboard watch`**：plist 的程序参数改成 `patrol tick <组>`，Label 不变；预览文字改为「巡视定时任务」。doctor 的「巡视提醒」改名「巡视定时任务」，新增：协作组没记脚本身份 → bad；`agents` 里查不到它是脚本身份 → bad，办法写登记命令；doctor 的「巡视」一项认 `patrolIdentity`。

## Task List

- **Task 1 脚本调用**（要做的 1；假设 9）：测试——假 `installed_plugins.json` 指向带 `script` 一节的假插件、假启动脚本：`agents`／`outbox X`／`sessions` 的命令行与代入正确、`~` 换成 `$HOME`；`send` 的正文走标准输入；接口没有 `script` 一节时报「需升级到 0.9.0」；启动脚本退出 3 时返回退出码和 stderr 首行。
- **Task 2 `patrol tick`**（要做的 2；假设 1、2、4、5、7；验收 1～4）：测试在 `env -i PATH=/usr/bin:/bin` 下跑——读三份状态、`wake` 变成 `send --from <身份> --to <邮箱名>`（不是会话编号）、`owner-alert` 同、`notify` 调通知、`record` 记下 done／failed；启动脚本退出 3 时弹一次「读不到 agent-relay」、30 分钟内第二轮不弹、恢复后清掉；`send` 被拒时发信动作 failed、只弹一次登记提醒；锁被收件箱拿着时跳过、不发信；残留锁超过 10 分钟被接管；`--from-hub` 拿不到锁时写 `skipped` 计划、`record` 不写；末尾仍跑 `watch.check`。
- **Task 3 脚本身份登记与收件箱收信**（要做的 3 前半、5；假设 3、6；验收 5）：测试——`onboard patrol-identity` 预览不写、确认写入 `patrolIdentity`；与名册邮箱名重名被拒；未登记时预览有提醒；`patrol_alarm` 认 `launchd` 并给新办法；收件箱收到脚本身份的信只确认（不退回、不登记、不进 unknown）。
- **Task 4 hub-setup、`onboard watch`、doctor**（要做的 3 后半、4；假设 8；验收 6）：测试——hub 步骤里没有「开巡视会话」、有登记命令和 `onboard patrol-identity`、有旧巡视会话时先停止归档；plist 程序参数是 `patrol tick <组>`；doctor 项名「巡视定时任务」、没记脚本身份 bad、`agents` 里查不到 bad、都在 ok；doctor「巡视」认 `patrolIdentity`；teardown 带脚本身份那一行。
- **Task 5 文档、术语表、版本**（要做的 6）：README（巡视怎么跑、0.0.38 升级步骤：用户在终端登记脚本身份 → 重跑 hub-setup → `onboard patrol-identity` → `onboard watch --confirm`；排查表加「读不到 agent-relay」「脚本身份没登记」两行；写明 0.0.36 的巡视目录不再用、留着不删）；`commands/hub-setup.md` 不再开巡视会话；`docs/glossary.md` 照原件 v1.3 同步（标题与来源行改 v1.3、加 v1.3 说明、新增「C 待定编号」「轻任务」、第五节编号那一行换成原件写法；本地独有的「卡片」「复制块」「看 N 全文」保留），并把「巡视提醒」改成「巡视定时任务」、新增「脚本身份」；两份 `plugin.json` 升到 0.0.38；全量测试；用本机真实 agent-relay 0.9.0 跑 `agents`／`outbox <di-p0 收件箱>`／`sessions` 只读，核对解析结果与 MCP 读到的一致（验收 7）。

## Files likely touched

- 新增：`decision_inbox/tick.py`、`tests/test_tick.py`
- 修改：`decision_inbox/relay.py`、`decision_inbox/__main__.py`、`decision_inbox/hub.py`、`decision_inbox/onboard.py`、`decision_inbox/watch.py`、`decision_inbox/doctor.py`；对应 `tests/test_relay.py`、`test_hub.py`、`test_onboard.py`、`test_watch.py`、`test_doctor.py`、`test_patrol.py`
- 文档与版本：`README.md`、`commands/hub-setup.md`、`docs/glossary.md`、`.claude-plugin/plugin.json`、`.codex-plugin/plugin.json`
- 不新增依赖，不碰全局配置、不改契约。

## Checkpoint（gate）：模块最终验收

列出改动文件（新增／修改／删除与行数，取自版本库）、测试数、验收 1～8 逐条结果和没验证的范围，交你批准。批准即授权：告诉 decision-inbox-owner 要发 0.0.38（它先通知依赖方）→ 推送 `claude/patrol-launchd` → 开 PR（base main，由你合并），不打标签。中途没有别的 `gate`。

## 风险

| 风险 | 对策 |
|---|---|
| launchd 环境里找不到 agent-relay | 命令从 `interface.json` 取、`~` 换 `$HOME`，不靠 PATH；测试在 `env -i PATH=/usr/bin:/bin` 下跑 |
| 收件箱与 launchd 同一轮重复发信 | 协作组级锁，拿不到就跳过；10 分钟残留锁接管，有测试 |
| 唤醒信被收件箱当成未知消息退回或登记 | `_dispatch` 先认脚本身份，只确认；有测试 |
| 被桌面版停掉的会话叫不醒 | Spec 已知限制：沿用「叫不醒，请手动打开」通知；收件箱那一轮仍用 `send_message` |
| 测试碰到真实 `~/.decision-inbox`、LaunchAgents 或真实信箱 | 沿用 `TempHomeTestCase`、`DECISION_INBOX_LAUNCH_AGENTS`、`DECISION_INBOX_PLUGINS_FILE` 与假启动脚本；只有验收 7 跑真实 agent-relay，且只读 |
