<!-- spec-guard: review approved -->

# Implementation Plan: rehearsal2-fixes

> 依据：`spec/rehearsal2-fixes.md`（用户 2026-10-18 批准，巡视选 A+B，假设确认）。任务清单：`tasks/rehearsal2-fixes/todo.md`。分支 `claude/rehearsal2-fixes`。

## Overview

六个任务，从影响大到小：线状态（已退出、stopped）→ 巡视免确认 → 写法提示 → join 两处 → 文档与版本。每个任务先写失败的测试，再改代码。冻结步骤（标签、固定副本、改安装、重跑 allow 和巡视任务）不在本 Plan 内，合并后另请用户批准。

## 已核实（假设 2）

官方文档（code.claude.com/docs/en/permissions）：文件写入只认 `Edit(path)` 规则，写成 `Write(...)` 会被接受但不生效；绝对路径要用 `//` 开头。所以放行规则写成 `Edit(//Users/<你>/.decision-inbox/<组>/io/**)`。文档没写清：只有 allow 规则时，项目外路径是否还会弹确认。这一点放到实测里验证，不行就回来找你。

## Architecture Decisions

- **Task 1 已退出条目**（`health._facts`）：遍历名册时跳过 `store.left_relays(g)`。`assess` 的 `names` 映射保留全名册（等待单的目标仍能显示简称）。
- **Task 2 stopped**：
  - `relay.AgentFact` 已有 `presence_raw` 和 `wake_bound`，不用新增字段。
  - `health` 新增 `_unreachable(f)`：presence 为 `unreachable`，或者 `presence_raw == "stopped"` 并且叫不醒（名册里没有 desktopSession、`wake_bound` 不为真、host 是 Claude）时返回真。只有这时写「掉线」。
  - Claude 会话 `stopped` 但能叫醒时，不在第一步返回，继续走后面的判断。
  - Codex 会话的 `stopped`（任务没打开）保持「掉线」，因为它确实收不到。
  - `_module_word`：`stopped` 写「停着」，`unreachable` 写「掉线」。
  - 信号 4 的文字改成「{简称} 停着，有 N 条消息等它」，判定条件不变。
  - 第 321 行用 `word == "offline"` 的地方逐一核对，保持语义。
  - patrol 不改。
- **Task 3 巡视（A+B）**：
  - `patrol.prompt` 的 workdir 默认改为 `~/.decision-inbox/<组>/io`（取 `store` 的组目录，写绝对路径）。
  - notify 一步改为 `{cli} notify "<text>"`。`__main__` 新增 `notify` 子命令：用 osascript 的 argv 方式发通知，文字作为参数传入，不拼进脚本。命令失败时退出码非 0，巡视记为失败。
  - `onboard.allow_entries(group)` 增加 `Edit(//<组 io 目录>/**)`，`allow` 预览里能看到这一条。
  - 已有巡视任务的提示词：`onboard task` 重新生成；README 写明升级后要重跑 `allow` 和 `task`。
- **Task 4 写法提示**（`protocol.parse`，只加 hints）：
  - `missing-project`：缺「项目」；
  - `reply-letter-only`：「你该回」只有选项字母，或「字母+空白」；
  - `review-empty-brackets`：「架构审查」写了「附建议N条」，但没有括号内容；
  - `brief-thin-batch`：「要你决定」里提到的 `#编号` 有 2 个以上，且要点非空行数少于编号数的 2 倍（用 bodies/8.txt 实测样例写测试：4 个编号、6 行，触发）。
  - 收件枢纽收下时，提示照旧进主视图；另外给发件人回一条只读告知：「收件枢纽已收下 #6546；下次请改：…」。不标 expectsReply，不是协议消息类型。复用 hub 已有的退回发送路径（outgoing），正文第一行写「收件提示：#邮箱号」，和退回区分开。
- **Task 5 join**（`onboard`）：
  - 后续步骤追加「约定块要在新开的会话里才生效：已经开着的会话，请新开一次」；
  - `_commit` 在 `after == before` 时不写规则文件，名册和记录照旧更新。
- **Task 6 文档与版本**：README 排查表加两行，升级一节写明 0.0.20 要重跑 `onboard allow` 和 `onboard task`；两份 `plugin.json` 和 `tests/test_packaging.py` 改为 0.0.20。

## Task List

- [x] Task 1：已退出条目不进线状态（Spec 验收 1）
- [ ] Task 2：stopped 能叫醒时不写「掉线」，模块写「停着」（Spec 验收 2）
- [ ] Task 3：巡视中间文件、notify 命令和 allow 放行（Spec 验收 3）
- [ ] Task 4：【等待用户】写法提示与收件提示（Spec 验收 4）
- [ ] Task 5：join 提醒新开会话、内容相同不重写（Spec 验收 5）
- [ ] Task 6：README、版本 0.0.20（Spec 验收 6）

### Checkpoint（gate）：模块最终验收

- [ ] 全部测试通过；每条验收标准都有证据；列出实际改动的文件
- [ ] 授权：Task 1–6 的代码、测试和文档；每个任务做完就提交，并推送 `claude/rehearsal2-fixes`
- [ ] 不授权：开 PR 或合并 PR、打标签、建固定副本、改用户的插件安装或配置（包括真的去运行 `onboard allow --confirm`、`onboard task --confirm`）、碰 LIVE-SAAS
- [ ] 实测（Spec 验收 7）放到冻结之后的批 2 重测里，开始前另问用户

## Risks

| 风险 | 预防 |
|---|---|
| 「能叫醒」判断太宽，把真掉线的会话说成正常 | 只对 Claude 会话、且有 desktopSession 或 wake 绑定时放宽；Codex 不变；测试覆盖四种组合 |
| 跳过已退出条目，影响迁移期旧格式的收发或 leave | 只改 health 的线状态；items 和 hub 的已退出逻辑不动；现有测试全部通过 |
| 只有 Edit 规则，项目外写入可能仍要确认 | 文档没写清，实测验证；不行再请你定（比如加 additionalDirectories） |
| 收件提示让发件会话多收一条消息 | 只在有提示时发，不标 expectsReply；写明「已收下」，不会被当成退回 |
| `brief-thin-batch` 误报 | 只在 2 个以上编号时判断；用实测样例和格式完整的样例各写测试 |
