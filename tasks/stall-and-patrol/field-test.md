# stall-and-patrol 冻结后实测（Spec 验收 6）

> 2026-10-19，用户批准方案：只用测试组 di-t22、临时目录 `~/Documents/haigeerlab/di-t22/` 和临时会话，测完清掉；不碰 di-p0、LIVE-SAAS，不改全局配置。安装版本：两个宿主和转发脚本都是 0.0.23（标签 v0.0.23 → 737f716）。

## 搭建

- 决策收件箱：本插件开发会话自己接入（`onboard hub di-t22`，邮箱名 `di-t22-hub`），规则段写在临时目录。
- 离线线 `di-t22-ghost`：临时 Claude 会话登记邮箱名后归档，`onboard enroll` 登记进名册（带 desktopSession）。
- 测试线 `di-t22-dev`：Codex 宿主条目（`onboard enroll`），邮箱名由开发会话登记、不绑定唤醒。
- 测试组 `group.json` 设 `stall.answerWaitMinutes = 1`，方便观察超时。

## 结果

| 项 | 结果 | 证据 |
|---|---|---|
| R19 叫醒兜底 | 通过 | 收件箱发给离线线的消息 7356 在 agent-relay 里 `pendingReason: offline`；满 3 分钟后第一轮巡视产出 `wake:di-t22-ghost`（会话消息叫醒），因会话已归档叫醒失败；5 分钟宽限后下一轮产出 `notify:unwakeable:di-t22-ghost`：「叫不醒 离线线，它还停着，请手动打开 claude://claude.ai/epitaxy/local_d0ab99f6-…（来源：Claude 桌面版）」，桌面通知已发；同一积压之后不再重复提醒 |
| R19 快照 | 通过 | 每轮在 `io/snapshots/` 存 agents、outbox 各一份，实测期间到 10 份以上 |
| R14 停滞提问 | 通过 | 测试线 24 小时内同一件事报批 3 次，第一轮巡视产出 `stall:di-t22-dev\|repeat`（owner-alert，A 挂起／B 换做法／C 继续等）；超过等回答阈值后主视图第一行出现「⚠ 停滞：测试线 被问了 2 分钟还没抛待决事项。请去『测试线』处理（去 Codex 打开它的任务）：A…；B…；C…」；测试线抛出【等待用户】后这一行消失 |
| R18 巡视会话 | 通过 | 按 hub-setup 的步骤开「decision-inbox 巡视 di-t22」，`/loop 5m` 建了会话内定时任务，连续跑了 4 轮以上（02:15:53、02:20:51 …），巡视记录持续更新；doctor 巡视项「最近一轮 0 分钟前」，异常 0；`bridge_agents` 不带参数一次返回全部 36 个邮箱名，没有分页漏读 |
| R16 常规授权（Claude 规则写入） | 通过 | join 预览列出放行 3 条（git add、git commit、测试命令）、先问 5 条（git push、git reset --hard、rm -rf、npm install、pip install），确认后写进临时仓库 `.claude/settings.local.json`；重复接入不重写文件 |
| R16 用户会话里的弹窗、Codex guardian 对推送 | **未实测** | 用户 2026-10-19 决定跳过：两个临时仓库和本地裸远端都没有出现新提交和推送，结果无法核实 |
| 卸载（teardown-patrol-session） | **部分通过** | `onboard teardown di-t22` 的后续步骤第一条是「用 archive_session 归档巡视会话 local_0cedfd79-…」，没有旧定时任务步骤；但照做时归档被拒：巡视会话里 `/loop` 建的会话内定时任务算「后台工作」，宿主不让归档。要先让巡视会话用 CronDelete 删掉自己的循环任务，再归档（见发现的问题 3） |

## 发现的问题（还没改）

1. 巡视提示词（`patrol.PROMPT`）里「把 text 原样发给**身份** target」漏改，术语表应为「邮箱名」；旧称扫描只查「身份名」，没查到单独的「身份」。
3. 卸载时归档巡视会话会被宿主拒绝（「still has live work」）：`/loop 5m` 在巡视会话里建了会话内定时任务。卸载的后续步骤要先写「给巡视会话发消息，让它用 CronDelete 删掉循环任务」，再归档；或者巡视会话的提示词里约定收到「停止巡视」就删任务。建议另开小模块修。
4. 测试组线为 legacyFormat（enroll 登记）时，收件箱收【等待用户】不回【登记回执】，这是旧格式兼容的预期行为，只记录不改。

## 清理

- 测试组 di-t22：卸载决策收件箱、归档巡视会话和离线线会话、删除 `~/.decision-inbox/di-t22` 和 `~/Documents/haigeerlab/di-t22`。
- agent-relay 里登记过的 `di-t22-hub`（已解除唤醒绑定）、`di-t22-ghost`、`di-t22-dev`：邮箱名本身无法用工具注销，留在 agent-relay 名册里；`di-t22-ghost` 还有 1 条测试消息未读。
