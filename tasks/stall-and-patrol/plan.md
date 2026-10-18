<!-- spec-guard: review approved -->

# Implementation Plan: stall-and-patrol

> 依据：`spec/stall-and-patrol.md`（用户 2026-10-19 批准；R14 用 B、阈值照默认）。任务清单：`tasks/stall-and-patrol/todo.md`。分支 `claude/stall-and-patrol`（叠在 #20 上）。

## Overview

六个任务，按风险排序：R19 叫醒兜底（阶段丙前必须稳）→ R18 巡视会话 → R16 常规授权 → R14 停滞提问 → 协作规则段与 README → 上报宿主观察。每个任务先写失败的测试，再改代码。不升版本号。

## 已核实

- `bridge_outbox` 每条未确认消息带 `wake: {state, detail, pendingReason}`，`pendingReason` 取值为 offline、unreachable、busy（agent-relay `bridge-store.ts`）。巡视以收件枢纽的身份读这份输出：收件枢纽发出的答复如果叫不醒，就在这里看得到。
- 定时任务每次运行都新开会话（E0），跑完自动归档行不通（E1），`/loop 5m` 一个会话循环可行（E2）。
- Claude 侧放行只认 settings 规则（E0、E3）；Codex 要先信任项目（E4）。

## Architecture Decisions

- **Task 1 R19 叫醒兜底**：
  - `relay.py`：解析 outbox 时，每条消息加上 `wake_pending`（pendingReason）和 `wake_state`。
  - `patrol plan` 新增 `--outbox` 参数。巡视提示词第 1 步多一项：用 `bridge_outbox`（agent 写收件枢纽身份）读收件枢纽发出的消息，写进 io 文件。
  - 新规则：收件枢纽发给某个 Claude 会话的消息，`pendingReason` 为 offline 且已过 3 分钟，就用现有的 `_wake` 叫醒（一个积压周期只叫一次）。下一轮还是这样，或者名册里没登记 desktopSession，就生成一条通知「去打开〈短名〉：claude://claude.ai/epitaxy/<会话编号>」，同时写进主视图的提醒行。
  - Codex 会话 presence 为 not-loaded、又有积压时，提醒「去 Codex 打开〈短名〉的任务」。
  - `IDLE_WAKE_MINUTES` 从 5 改成 3。
  - 快照：每轮把 agents、outbox 的原文另存到 `io/snapshots/<时间>-agents.json`、`-outbox.json`，只保留最近 24 份；输入文件照旧读完就删。
- **Task 2 R18 巡视会话**：
  - `onboard hub` 的后续步骤，把「建定时任务」换成「开巡视会话」：用桌面版的开会话工具在收件枢纽目录开一个会话，叫「decision-inbox 巡视 <组>」，提示词是「用 /loop 5m 执行下面的巡视提示词」，后面接 `patrol prompt` 的输出。
  - 发现组里登记过巡视定时任务（`patrolTask`）时，加一步「删除旧巡视定时任务 <id>（它建过的会话会一起归档）」。两步都是经用户确认后由收件枢纽执行。
  - 新增 `onboard record-patrol <组> --session <编号>`，记下巡视会话。
  - doctor 的巡视检查改看两样：巡视会话有没有登记，`lastRunAt` 有没有超过 15 分钟。超时时提示「巡视会话可能停了：打开它，或重跑 hub-setup」。
  - 「收件枢纽被叫醒时顺带巡视」的逻辑不变，用作兜底。
- **Task 3 R16 常规授权**：
  - `onboard join` 新增 `--test-command <命令>`（可选）。Claude 主机的线，预览里列出要合并进 `<仓库>/.claude/settings.local.json` 的规则：
    - allow：`Bash(git add *)`、`Bash(git commit *)`，以及有测试命令时的 `Bash(<测试命令> *)`；
    - ask：`Bash(git push *)`、`Bash(git reset --hard *)`、`Bash(rm -rf *)`、`Bash(npm install *)`、`Bash(pip install *)`。
  - 加 `--confirm` 才写入。只追加缺的规则，不删别人写的；内容不变就不重写。
  - Codex 主机的线：后续步骤第一条是「在 Codex 里信任这个项目（否则不读约定块）」。
  - `view._confirm_card`（要你去原会话确认的卡片）加链接：Claude 用桌面版链接，Codex 写任务短名。
  - README 使用注意事项写明：代理替你开的会话里，先问规则可能不生效（E3）。
- **Task 4 R14 停滞提问（用 B）**：
  - `health` 新增三个停滞触发，阈值读组配置 `group.json` 的 `stall`，没写就用默认值：
    - 线停住（信号 3）≥12 小时；
    - 同一审查节点返工 ≥3 轮（信号 7）；
    - 同一发件会话 24 小时内同一件事报了 ≥3 项（「要你决定」第一行相同，或者 approvalModule 加 approvalNode 相同）。
  - 巡视对命中的线生成动作 `stall-ask`：叫醒那条线（Claude 用会话消息，Codex 写成通知）。正文写明卡了多久、卡在哪，请它抛【等待用户】给三个选项：
    - A：挂起，先开可开工的模块，从 /map 的 ready 和 module-crew 出口列出；
    - B：换做法；
    - C：继续等。
  - 发出后记下时间。30 分钟内那条线没抛新事项，主视图的异常里列出这三个选项和「去〈短名〉处理」的链接。
  - 同一条线、同一种触发，问过之后 12 小时内不再问（对应选 C 的「N 小时内不再问」）。
- **Task 5 协作规则段**：开发线、审查者、跨线协调三种角色加一句：收到【decision-inbox 巡视】的停滞询问，就抛一项【等待用户】，写清卡在哪，给 A 挂起先开别的、B 换做法、C 继续等三个选项。Codex 主机的规则段加上第 44 条授权范围的说明（不可逆操作仍要用户亲手确认）。README 补上巡视会话、settings 规则和注意事项。
- **Task 6 上报**：给 module-crew 发一条消息说明 E3 的发现（代理开的会话里先问规则没生效），请它核对模块会话的开法。这是对外发消息，发之前先给你看原文。

## Task List

- **Task 1 R19**（Spec 验收 1）。验证（`tests/test_patrol.py`、`tests/test_relay.py`）：
  - offline 满 3 分钟，生成 wake；
  - 下一轮还是这样，生成带链接的通知；
  - 没登记 desktopSession，直接通知；
  - Codex not-loaded 时提醒；
  - 空闲积压满 3 分钟也叫醒；
  - 快照只留 24 份；
  - 原有巡视测试全部通过。
- **Checkpoint A（report）**：R19 测试全过，记入 todo 后继续。
- **Task 2 R18**（Spec 验收 2）。验证（`tests/test_onboard.py`、`tests/test_doctor.py`）：
  - hub 的后续步骤里有「开巡视会话（/loop 5m）」；
  - 登记过定时任务时，多出删除那一步；
  - `record-patrol` 能记下巡视会话；
  - doctor 在巡视超时和没登记巡视会话时都报异常。
- **Task 3 R16**（Spec 验收 3）。验证（`tests/test_onboard.py`、`tests/test_view.py`）：
  - 预览列出要写的规则，不加 `--confirm` 不写；
  - 写入时保留已有规则；内容不变不重写（mtime 不变）；
  - Codex 线的步骤里有「信任项目」；
  - 确认卡片带链接。
- **Task 4 R14**（Spec 验收 4）。验证（`tests/test_health.py`、`tests/test_patrol.py`、`tests/test_view.py`）：
  - 三种触发条件各一条；
  - stall-ask 正文里有卡了多久、卡在哪、可开工模块和三个选项；
  - 30 分钟没抛事项时，主视图列出选项；
  - 12 小时内不重复问；
  - 阈值可以从 group.json 改。
- **Task 5 规则段与 README**。验证：三种角色的规则段都有停滞询问这一句；Codex 规则段有授权说明；打包测试的关键词通过。
- **Checkpoint B（report）**：全量测试通过，记入 todo 后继续。
- **Task 6 上报 module-crew**：先给你看消息原文，你同意了再发。
- **Checkpoint C（gate）：模块最终验收**。列出改动的文件、每条验收标准的证据、测试数，然后开 PR（base 是 `claude/r20-fixes`）。

## 影响面

- 巡视提示词变了：多读 outbox，并改由巡视会话来跑。已经接入的收件枢纽要重跑 hub-setup。
- join 会改 Claude 线仓库里的 `.claude/settings.local.json`，每次都要你确认。
- 三种角色的协作规则段变了，要重新接入。

## 风险

| 风险 | 对策 |
|---|---|
| 巡视会话被应用停掉或重启后没了 | 收件枢纽被叫醒时会顺带巡视兜底；doctor 发现巡视超过 15 分钟没跑就报，提示重开 |
| 巡视会话在默认权限模式下，每轮写 io 文件时弹确认 | hub-setup 的放行清单已经放行 io 目录的写入（rehearsal2-fixes）；巡视会话开在收件枢纽目录，沿用同一份放行规则；阶段丙实测确认 |
| 巡视会话上下文越跑越长 | 每轮输出很短；靠宿主的自动压缩；阶段丙观察，太长就定期重开 |
| R14 误报（线只是在正常地慢慢做） | 阈值可以改；同一种触发 12 小时内只问一次；只问，不代你做 |
| settings 规则写错，挡住了正常操作 | 预览给你看全文；只追加不删除；可以手工改回 |
