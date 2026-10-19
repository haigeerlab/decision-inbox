<!-- spec-guard: review pending -->

# Plan: stage-c-fixes

依据 `spec/stage-c-fixes.md`（2026-10-20 用户批准）。每个任务先写在 1c2d3c9 上失败的测试，再改代码，跑全量 `PYTHONPATH=tests:. python3 -m unittest discover -s tests` 后提交。

## 任务

1. **协议升到 v2.4**（Spec 要做 0；验收 2 的样例部分）
   - 改：`protocol.py` 的 CONTRACT_VERSION 与【等待用户】解析加「模块」（键 `module`，「无」原样）；`items.py` 记下它；`tests/fixtures/session-protocol/v2.3` 改名 v2.4，用契约 495b475 的 `git archive` 覆盖，SHA256SUMS 对上。
   - 验证：v2.4 样例一致性测试与 module-id、module-none、module-with-kind 三份新样例先失败后通过。
2. **模块反查与重判**（DI-10；验收 1、2、3）
   - 改：`loops.py` 的 `_module_for`／`tag` 按假设 1、3（自带模块 → 交审编号 → 模块会话邮箱名 → 唯一模块 id → 未知；「无」为线级；未知的之后按内容重判）；`view.py` 抬头对「线级」的写法；`hub.py`、`stall.py` 不改逻辑，只加回归。
   - 验证：单测覆盖每一步与「两个 id 不猜」「已认出不改」「普通开发线照旧」；阶段丙重放夹具（di-p0 items 副本中 #59–#65 + 按 crew-rehearsal 事件日志还原的 zeta 事实）：#61–#63 归 zeta、第 3 项出三个选项、「63 继续等」记成继续等并静音、停滞信号②不再被压。
3. **停滞起点与扣除**（DI-12；验收 6、7）
   - 改：`stall._module_findings` 与 `loops` 的等待区间：起点取最后提交、startedAt、最近一次答复送达三者最晚；事项等待算到答复发送成功；合问对每个涉及模块都扣；模块协调的等待记录按点名扣。
   - 验证：epsilon 重放夹具（#47 答复晚 23 分钟送达、#55 时刻）不报停滞；点名／不点名／合问三种扣除各一条用例。
4. **`patrol-watch` 命令**（DI-11；验收 4）
   - 改：新 `decision_inbox/watch.py` 与 `__main__` 子命令：用 `hub.patrol_alarm` 判超时，调 `osascript` 发通知（命令可注入，测试用假的），状态记 `patrolWatch.lastNotifiedAt`，30 分钟内不重发，恢复后清掉。
   - 验证：停 20 分钟发一条、10 分钟后不发、35 分钟后再发、恢复后不发；通知正文含巡视会话名与修法。
5. **装、卸与体检**（DI-11；验收 5）
   - 改：`onboard.py` 的 hub 预览与步骤加「装巡视提醒」（写 plist、`launchctl bootstrap`），teardown 加 `bootout` 与删 plist；`doctor.py` 加「巡视提醒」检查；hub-setup、teardown 的命令说明跟上。
   - 验证：用假 `launchctl` 与临时 HOME 的用例：预览列出、确认后写入并调用、卸载调用并删除、doctor ok／bad。
6. **文档、版本与实跑**（Spec 要做 5；验收 8）
   - 改：README「排查」「卸载」、`docs/glossary.md`「巡视提醒」、协作规则段若受影响一并改；两个插件清单升 0.0.31。
   - 验证：全量测试通过；di-p0 副本（scratchpad）上跑主视图看 #61–#63 抬头；scratchpad 临时组手动跑一次 `patrol-watch` 弹一条真通知给你看（不装 launchd）；真实 di-p0 状态目录 md5 前后不变。

## 会改哪些文件

`decision_inbox/` 的 protocol、items、loops、view、stall、hub（仅回归）、onboard、doctor、`__main__`，新增 watch.py；`tests/` 对应测试与 `fixtures/session-protocol/v2.4`、阶段丙重放夹具；README、docs/glossary.md、两个插件清单、hub-setup／teardown 命令说明。

## 风险

- 重放夹具是从事件日志手工还原的 module-crew 事实，不是当时 `sessions --json` 的原样输出；夹具里注明来源与还原规则。
- 升 v2.4 会动样例目录；只用 `git mv` 与 `git archive` 覆盖，不删文件。
- 改停滞扣除可能让原有停滞用例变化；旧测试只在 Spec 改了口径的地方改写，改写的逐条记进 todo。

## 检查点

- 任务 1～5 各自完成后：report（记进 todo 继续，不停）。
- 任务 6 末尾：gate，最终验收，列出改动文件、提交号和每条验收的证据，批准后开 PR。
