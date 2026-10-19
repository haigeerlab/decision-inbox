<!-- spec-guard: review approved fe97c4b47dc3 -->

# Spec: patrol-watch-runtime

> 能力图模块 `patrol-watch-runtime`（2026-10-20 用户确认插入，排在 launcher-own-code 之后）。来源：0.0.31 巡视提醒（stage-c-fixes DI-11）在本机实测失败——2026-10-20 01:13 `onboard watch di-p0 --confirm` 装上的 launchd 任务第一次运行就退出 126，日志写 `/bin/sh: …/decision-inbox-release/v0.0.31/bin/decision-inbox: Operation not permitted`；`doctor` 只看「已加载」，照样报 ok。用户 2026-10-20 选定做法：复制运行副本 + 指定 python。

## 目标

1. `onboard watch` 装上的巡视提醒在本机真的能跑：launchd 首次运行退出 0，巡视停着时弹出「决策收件箱：巡视停了」。
2. 插件升级或换安装位置后，巡视提醒跟着跑新代码，不用重装。
3. 巡视提醒装了但跑不起来时，`doctor` 报 bad，写明原因和修法。

## 现状（2026-10-20 实测，临时 Label 的 launchd 任务，测完已卸）

- plist 跑转发脚本 `~/.decision-inbox/bin/decision-inbox`，它 exec 到插件目录里的 `bin/decision-inbox`。插件从 `~/Documents` 下的固定副本装时，launchd 代理没有权限读 `~/Documents`（macOS 隐私保护，`~/Desktop`、`~/Downloads` 同理），退出 126。
- 把 plist 指向 Claude 或 Codex 的插件缓存（`~/.claude/plugins/cache/…`、`~/.codex/plugins/cache/…`），或指向复制到 `~/.decision-inbox` 下的副本：文件都能读，但都退出 1。原因是 launchd 的 PATH 只有 `/usr/bin:/bin:/usr/sbin:/sbin`，`python3` 解析成系统自带的 3.9.6，本包要求 3.10 及以上（`X | None` 注解直接 TypeError）。
- 复制到 `~/.decision-inbox` 下的副本，再在 plist 里把 PATH 设成 3.10 所在目录：退出 0。
- `doctor` 的「巡视提醒」只看 plist 在不在、`launchctl print` 能不能找到；`launchctl print` 里的 `last exit code` 没看。

## 要你确认的假设

1. **运行副本**：位置 `~/.decision-inbox/runtime/`（跟着 `DECISION_INBOX_HOME`），内容是插件的 `bin/decision-inbox` 和 `decision_inbox/` 包里的全部文件。整体替换：先写到旁边的临时目录，再换名，中途失败不留半套。
2. **谁来复制**：
   - `onboard watch <组> --confirm` 时复制（预览写明会复制到哪里）；
   - 插件升级：SessionStart 已经会跑 `shim --if-installed` 改写转发脚本，这时顺带刷新运行副本，**只在运行副本已存在时刷新**（没装巡视提醒的人不多出这个目录），内容一样就不动。哪个宿主最后启动会话，运行副本就跟哪个宿主的插件，和转发脚本的现有规则一致。
3. **plist 内容**：`ProgramArguments` 第一项改成 `~/.decision-inbox/runtime/bin/decision-inbox`；加 `EnvironmentVariables`：`PATH` = 「运行 `onboard watch` 的那个 python 所在目录」:/usr/bin:/bin（取 `sys.executable` 的目录，不解析符号链接，python 小版本升级后链接还在）；设了 `DECISION_INBOX_HOME` 时也带上。其他（每 300 秒、RunAtLoad、日志位置）不变。
4. **装之前就拒绝的情况**：运行副本或那个 python 落在 `~/Documents`、`~/Desktop`、`~/Downloads` 下时，`onboard watch` 不装，写明原因（launchd 读不了这些目录）。
5. **doctor 的「巡视提醒」**，按顺序判断，命中一条就停：
   1. 没有 plist → bad（原样）；
   2. 没加载 → bad（原样）；
   3. plist 跑的不是运行副本（0.0.31 装的旧任务），或运行副本缺失 → bad：「是旧版装的／运行副本不在」，修法是重跑 `onboard watch <组> --confirm`；
   4. `launchctl print` 的 `last exit code` 不是 0 → bad：写出退出码和日志最后一行；日志里有 `Operation not permitted` 时说明「运行的程序落在 macOS 受保护目录」；修法是升级到本版后重跑 `onboard watch <组> --confirm`；
   5. 其他（退出 0，或还没跑完过一次 `(never exited)`）→ ok（原样）。
6. 不改 `patrol-watch` 判断与通知本身（stage-c-fixes 已定），不改转发脚本 `~/.decision-inbox/bin/decision-inbox` 的指向。

## 要做的

1. `install`：加运行副本的复制与刷新（假设 1、2）；`shim` 命令在运行副本已存在时刷新它。
2. `watch`：plist 跑运行副本、带 PATH（假设 3）；装之前查受保护目录（假设 4）；`onboard watch` 的预览写明会复制运行副本、用哪个 python。
3. `doctor`：按假设 5 看旧任务、运行副本、上次退出码和日志。
4. 测试：plist 内容、受保护目录拒绝、刷新只在已存在时发生、整体替换、doctor 四种 bad 和 `(never exited)`（都用假 `launchctl`）。
5. README：排查表加「巡视提醒没弹、doctor 报退出码非 0／Operation not permitted」一行；升级说明里写明 0.0.31 装过的要重跑一次 `onboard watch`。版本号升到 0.0.32。

## 做 / 不做

- 做：上面 1～5；验收时在本机装上 di-p0 的巡视提醒（你确认后）。
- 不做：打标签、升级 di-p0 的插件；运行副本跟着「固定副本」走以外的版本选择；`teardown` 删运行副本（多个组共用它，状态目录本来就保留）。

## 验收标准

1. 新测试在 main（c4d97ca）上失败，改后通过；全量 `PYTHONPATH=tests:. python3 -m unittest discover -s tests` 通过。
2. 用本分支代码在本机 `onboard watch di-p0 --confirm`：`launchctl print` 显示首次运行 `last exit code = 0`；di-p0 的巡视现在停着，弹出「决策收件箱：巡视停了」；`doctor` 的「巡视提醒」报 ok。
3. 用一个临时 Label、程序指向 `~/Documents` 下脚本的任务复现退出 126，`doctor` 的判断函数对它报 bad，写明受保护目录（测完卸掉）。

## 风险

- 运行副本跟着最后启动的宿主走：Claude、Codex 装了不同版本时，巡视提醒跑哪一版不确定。和转发脚本一样，靠 README「两边都重装、用 doctor 核对」兜住。
- 运行 `onboard watch` 的 python 以后被卸掉：任务会退出非 0，假设 5 第 4 条会报出来，修法同样是重跑。
- 通知需要「脚本编辑器」的通知权限（stage-c-fixes 已写进 README），doctor 查不到这一点。

## 文档建议

README「排查」表与升级说明（见「要做的」第 5 条）；其他无。
