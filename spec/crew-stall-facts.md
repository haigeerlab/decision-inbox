<!-- spec-guard: review approved ecd0cda24417 -->

# Spec: crew-stall-facts

> 能力图模块 `crew-stall-facts`（2026-10-19 用户确认插入，排在最后，不插队）。来源：module-crew 0.4.0 冻结知会（标签 v0.4.0 → ca990a3，`sessions --json` 新增停滞事实，定义见 module-crew `spec/crew-stall-signals.md`）；插入时的假设 1–8 用户 2026-10-19 确认。

## 目标

模块协调那条线下的模块会话卡住时，R14 能按模块发现，并让模块协调就这个模块抛【等待用户】。依据只用 module-crew 给的事实，阈值由本插件定。

## 现状（已核对代码与实跑）

- **R14 只按线判断**（`decision_inbox/stall.py` 的 `_findings`）：
  - 线状态停住超过 `stalledHours`（默认 12 小时）；
  - 审查来回超过 `reworkRounds`（3 轮）；
  - 本插件记录的待决事项里，同一件事在 `repeatHours`（24 小时）内报批达到 `repeatAsks`（3 次）。

  巡视（`patrol.plan`）每轮调 `stall.asks`，叫醒那条线。线在 `answerWaitMinutes`（30 分钟）内没抛【等待用户】时，`stall.overdue_rows` 在主视图列出三个选项。同一个键在 `askAgainHours`（12 小时）内只问一次。
- **模块协调那条线**：`crew.read_modules` 读 module-crew 的 `sessions --json`，只解析 `module`、`relayName`、`stage`、`suspended`、`review`，用来显示各模块状态。不看提交时间，也不看报批次数。
- **module-crew 0.4.0 的新字段**：用 0.4.0 副本对 crew-rehearsal 实跑过，本插件现有解析照常通过。每行新增：
  - `startedAt`：没有登记事件时为 null；
  - `commits`：`{ahead, last: {commit, at} | null, error}`。`last` 是开工以来模块自己的最新一次提交，合入后仍有值；读不到时 `ahead`、`last` 都为 null，`error` 写原因；
  - `asks[]`：`{node, count, refs, ats, lastAt}`，其中 `ats` 和 `refs` 一一对应，是每次交审进入提请批准或被答复的时间；
  - `returns[]`；
  - `waitUser[]`：这个模块发来的全部【等待用户】，开着的和已关的都在，每条有 `state`。
- **stage 取值**：`spec-plan`、`build`、`returned`、`wait-merge`、`merged`。

## 要做的

1. **读字段**（`crew.py`）：`Module` 加四个可选字段，形状不对一律当作没有，不影响原有显示：
   - `started_at`；
   - `last_commit_at`（取 `commits.last.at`）；
   - `commits_error`；
   - `asks`：按节点给出时间列表。

   还有一个字段 `waiting_user`，表示 `waitUser` 里有没有 `state` 为 open 的项。
2. **按模块判停滞**（`stall.py`）：对每条模块协调线，读到 module-crew 的模块后逐个看。以下模块跳过：
   - 已合入或在等合并（stage 为 `merged` 或 `wait-merge`）；
   - 已挂起（`suspended` 有值）；
   - 正在等你（`waiting_user` 为真）；
   - 正在审查或返工（`review` 有值）。

   剩下的模块里：
   - **太久没产出**：取 `last_commit_at`，没有就取 `started_at`，用现在减去它，超过 `stalledHours` 就算。`commits_error` 有值时这一项不判（读不到提交，不能当成没提交）；两个时间都没有时也不判；
   - **重复报批**：同一节点 `ats` 里落在最近 `repeatHours` 内的次数达到 `repeatAsks` 就算。
3. **问谁、怎么问**：
   - 问模块协调（假设 1），键为 `<模块协调邮箱名>|<stalled|repeat>:<模块>`，去重沿用 `askAgainHours`（假设 4）；
   - 叫醒文字沿用 R14 的三个选项，开头写明哪个模块、卡在哪。例如「模块 alpha 已经 14 小时没有新提交（开工以来最后一次提交 10-19 01:20）」；
   - 挂起由模块协调按 module-crew 的做法处理，提示里不写 spec-guard 的 module-suspend（那是开发线的做法）。
4. **主视图**（`overdue_rows`）：模块协调被问后在 `answerWaitMinutes` 内没有抛【等待用户】，就列一行。这一行写出模块名，例如「⚠ 停滞：crew-rehearsal 的模块协调（模块 alpha）被问了 40 分钟……」。三个选项不变。
5. **兼容**：module-crew 0.3.x 没有这些字段，所有模块都不触发新判断，线级 R14 照旧。读不到 module-crew 时也不触发。
6. **外部依赖表**（`spec/CAPABILITY-MAP.md`）：加一行，写 module-crew 0.4.0 的这几个字段和 `commits.last` 修订后的含义。

## 关键决策与取舍

1. **补充假设 3：`wait-merge` 也跳过**。等合并时模块已经做完，不会再有新提交，按提交时间判断一定会误报。合并是模块协调和你的事，不算模块卡住。
2. **补充假设 3：`commits.error` 有值时不按时间判断**。worktree 读不到时，`last` 为 null 不代表没提交。改用 `startedAt` 会误报，所以这种情况跳过；重复报批照常判断。
3. **线级判断和模块判断并存**：线级的「重复报批」数的是本插件记录的待决事项，模块级数的是 module-crew 记的交审时间。两者的键不同，可能各问一次，但都受 `askAgainHours` 限制。不合并，保持各自来源清楚。
4. **`returns`、`commits.ahead` 不作为判断依据**（假设 8 之外的说明）：返工轮次已由 `review` 覆盖，`ahead` 合入后为 0，和是否停滞无关。

## 范围

做：
- `decision_inbox/crew.py`（解析新字段）；
- `decision_inbox/stall.py`（模块判断、叫醒文字、主视图行）；
- `decision_inbox/patrol.py`（把每轮已读到的 crew 结果传给 `stall.asks`）；
- `spec/CAPABILITY-MAP.md` 外部依赖表；
- README 里 R14 的说明，以及对应测试。

不做：
- 不改协作规则段，已接入的线不用重新接入（假设 8）；
- 不换 module-crew 的安装（假设 6）；
- R16 的 join 不引用 module-crew 的 `permissions plan/apply`；
- 不改阈值默认值，也不加新设置项（假设 2）；
- 不动版本号：另开 PR，冻结和安装切换另请用户批准。

## 验收标准

1. 模块 stage 为 `build`、最后一次提交在 13 小时前时，巡视对模块协调发一次叫醒，文字含模块名和三个选项。12 小时内再巡视，不重复问。
2. 没有 `commits.last` 时按 `startedAt` 算；`commits.error` 有值时不按时间判断；两者都没有时不判断。
3. 同一节点 `ats` 在 24 小时内有 3 次时，发一次「重复报批」叫醒；只有 2 次，或者第 3 次在 24 小时以前时，不发。
4. stage 为 `merged`、`wait-merge`，或已挂起、有开着的 waitUser、`review` 有值的模块，一律不问。
5. 模块协调被问后 30 分钟内没有抛【等待用户】时，主视图列出含模块名的停滞行；抛了就不列。
6. module-crew 输出没有新字段（0.3.x 形状）或读不到时，不产生模块级叫醒，线级 R14 和现有测试不变。
7. 用 module-crew 0.4.0 副本对 crew-rehearsal 实跑，能解析出新字段。那里的模块已合入，不产生叫醒。
8. 全量测试通过。

## 假设

1. module-crew 0.4.0 的这几个字段按其 `spec/crew-stall-signals.md` 的定义稳定，字段只增不改（`schemaVersion` 仍为 1）。
2. 模块协调收到叫醒后，会按 module-crew 的做法抛【等待用户】（契约 v2.1 里已有的消息），本插件不需要新的消息格式。

## 未决问题

无。

## 文档建议

README：R14 一节加一句「模块协调那条线按模块判断（需 module-crew 0.4.0）」，并写明跳过哪些模块。其余无。
