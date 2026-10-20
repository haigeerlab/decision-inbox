<!-- spec-guard: review approved a8c2e21b4c1a -->

# Spec: hub-stop-scope

> 能力图模块 `hub-stop-scope`（2026-10-20 用户确认插入，排在 rules-dir-guard 之后）。来源：2026-10-20 实测，接入协调会话只读跑了一次 `decision-inbox view di-p0`，停止钩子就拦下它，要求逐字贴出复制块「66 A …」；而 #66 已经被代答成 B，照贴可能答错。decision-cards 第 4 节（DI-4）写的是「收件箱会话的停止检查」，实现却对所有会话生效。

## 目标

收件箱停止检查只拦收件箱自己；其他会话跑 `view`／`inbox reply` 不受影响。doctor 的「收件箱停止检查」只拿收件箱自己的会话记录来试读。

## 现状

- `__main__._hook` 第一步对每个会话都调 `stophook.hub_turn_check(payload)`（注释写「wherever it runs」），之后才用 `install.locate(cwd)` 认会话。`hub_turn_check` 只看会话记录：本轮跑过 `decision-inbox view` 或 `inbox reply` 就核对回复。
- `install.locate(cwd)` 已能认出收件箱：收件箱的名册条目没有 `repo`，靠 onboarding.json 的 `files[<邮箱名>]`——cwd 正好是那个规则文件所在目录就算它；离开的成员不算。`whoami` 用的就是它。
- doctor 的 `_hub_transcript` 在 `~/.claude/projects/*/*.jsonl` 里按修改时间取最近 50 份，第一份出过主视图的就拿来试读，不管是谁的会话。
- Claude Code 的会话记录放在 `~/.claude/projects/<编码后的目录>/<会话 id>.jsonl`，编码规则是把目录路径里非字母数字的字符都换成 `-`（本机实测：`/Users/vilin/Documents/haigeerlab/di-p0/hub` → `-Users-vilin-Documents-haigeerlab-di-p0-hub`）。名册里的 `desktopSession` 是桌面版的 `local_…` 编号，和会话记录文件名对不上，所以不用它找记录。

## 假设（请确认）

1. **怎么认收件箱**：用钩子 payload 的 `cwd` 走 `install.locate`（和 `whoami` 同一套），认出来的条目 `role` 是 `hub` 才做收件箱检查。钩子带了 `--group` 和 `--session` 时，改按名册里这个邮箱名的 `role` 判断。
2. **判不出时放行，并在 stderr 写原因**，分三种情况：payload 没有 `cwd`；cwd 同时对上多个条目（其中有收件箱）；读名册出错。cwd 根本不属于任何协作组时直接放行，不写 stderr（和现在「这个项目没接入」的处理一样，免得每个无关会话都刷一行）。
3. **只认收件箱规则文件所在的那个目录本身**，不认它的子目录（`locate` 本来就这样）。收件箱会话在子目录里开、或者旧版接入时没有记下规则文件，这个检查就不生效（放行）。这两种情况算降级，不算拦错；doctor 会在第 2 条里把它报出来。
4. **doctor 怎么找收件箱的会话记录**：对每个组里没离开的收件箱，取 `files[<邮箱名>]` 所在目录，按上面的规则编码，到 `transcripts_dir()/<编码>/*.jsonl` 里按修改时间取最近 50 份，找第一份出过主视图的去试读。目录按记下的写法和 realpath 后的写法各试一次（`/tmp` 和 `/private/tmp` 这种情况）。这一项仍然只有一条，名字不变，证据里写明是哪个组的收件箱。
5. **doctor 判不出时**：收件箱没有记下规则文件，报 unknown「<组> 的收件箱没有记下规则文件，认不出它的会话记录」，怎么做写「在收件箱目录重跑 hub-setup」；找到了目录但还没出过主视图，报 unknown，沿用现在的说法。

## 要做的

### 1. 停止钩子只对收件箱做卡片检查

`_hook` 先认会话（假设 1），是收件箱才调 `hub_turn_check`；不是收件箱就跳过这一步，后面 `stophook.decide` 的流程不变。判不出时按假设 2 处理，写一行 `decision-inbox 停止钩子：收件箱停止检查放行：<原因>` 到 stderr，然后继续走原来的流程（原来的流程对这几种情况本来就会放行）。

`hub_turn_check` 本身的核对规则不改。

### 2. doctor 只试读收件箱自己的会话记录

`_hub_transcript` 改成只扫假设 4 的那几个目录；其他目录里出过主视图的会话记录不再算数。结果三态和措辞沿用现在的，只在证据里加组名。

### 3. 回归测试

- 非收件箱会话（开发线 repo 里、审查者目录里、不属于任何组的目录里）本轮跑了 `view` 而且没照贴：不拦。
- 收件箱会话（cwd 是收件箱规则文件所在目录）同样的情况：照旧拦。
- 判不出（没有 `cwd`、cwd 对上多个条目）：放行，stderr 有原因。
- doctor：别的目录里有一份读不懂但出过主视图的记录、收件箱目录里有一份读得懂的，报 ok；只有别的目录里有，报 unknown。

## 做 / 不做

- 做：上面 1～3。
- 不做：改 `hub_turn_check` 的核对规则；让收件箱子目录也算收件箱；用 `desktopSession` 找会话记录；改版本号或 README（等发版时一起）；升级本机；打标签。

## 验收标准

1. 组里有收件箱（规则文件在 `<组>/hub/CLAUDE.md`）和开发线；从开发线 repo 和不属于任何组的目录各发一份停止 payload，本轮会话记录里跑了 `decision-inbox view <组>`、回复是摘要：钩子不输出 block。
2. 同样的会话记录，`cwd` 是 `<组>/hub`：钩子输出 block，理由和现在一样。
3. payload 没有 `cwd`：不拦，stderr 有「收件箱停止检查放行」和原因。
4. 带 `--group <组> --session <开发线邮箱名>` 时不做卡片检查；`--session <收件箱邮箱名>` 时照做。
5. doctor：`transcripts_dir()/<别的目录>/` 里有一份出过主视图但读不懂的记录，`<收件箱目录编码>/` 里有一份读得懂的，报 ok，证据里有组名；去掉收件箱目录那份后报 unknown，不报 bad。收件箱没有记下规则文件时报 unknown，写明原因。
6. 每条修复先有一条失败的测试；全量 `PYTHONPATH=tests:. python3 -m unittest discover -s tests` 通过。

## 风险

- 假设 3 的降级：收件箱在子目录里开会话时，卡片检查不生效。这是从「拦错别人」换成「漏拦自己」，后者只是少了一道兜底，不会让用户答错；doctor 会报 unknown 提醒。
- 会话记录目录的编码规则是 Claude Code 的内部约定，将来可能变；变了以后 doctor 报 unknown（找不到），不会误报 ok。

## 文档建议

无。doctor 项名字不变；README 的升级说明等发版时一起写。
