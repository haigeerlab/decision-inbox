<!-- spec-guard: review approved 1c97ad1d2421 -->

# Spec: launcher-own-code

> 能力图模块 `launcher-own-code`（2026-10-20 插入，排在 stage-c-fixes 之后）。来源：2026-10-20 本机实测——固定路径的转发脚本 `~/.decision-inbox/bin/decision-inbox` 指向 v0.0.29 固定副本，在 stage-c-fixes 的 worktree 里运行 `onboard watch di-p0`，跑出了 0.0.31 才有的命令。

## 目标

`bin/decision-inbox` 不管在哪个目录被调用，跑的都是它自己所在插件目录里的 `decision_inbox`，不是调用者当前目录里的同名包。

## 现状

- `bin/decision-inbox` 把插件根放进 `PYTHONPATH`，再 `exec python3 -m decision_inbox`。
- `python3 -m` 会把当前目录排在 `sys.path` 最前面、`PYTHONPATH` 之前。当前目录是 decision-inbox 的仓库或 worktree 时，加载的是那里的代码。
- 本机 `python3` 是 3.10.7（`/usr/local/bin/python3`），不支持 `-P`／`PYTHONSAFEPATH`（3.11 才有）；`/usr/bin/python3` 是 3.9.6。

## 要你确认的假设

1. 做法：改成 `exec python3 -c '<几行引导代码>' "$ROOT" "$@"`。引导代码先只 `import sys`（内建模块，不走 sys.path），把 `sys.path[0]`（`-c` 下是代表当前目录的 `''`）换成插件根，然后才 `import runpy` 并按 `-m` 的方式运行 `decision_inbox`。不用 `-P`，因为本机 3.10 不支持；不用 `-I`，因为它会连 `PYTHONPATH` 一起忽略。
2. 只改「从哪里加载代码」，不改进程的当前目录：`whoami`、`--project "$PWD"` 等照旧按调用者的目录读。`DECISION_INBOX_PLUGIN_ROOT` 照旧导出，调用者自己的 `PYTHONPATH` 照旧排在插件根之后。
3. `sys.argv[0]` 照旧是 `decision_inbox/__main__.py` 的路径（与 `-m` 一致），命令行参数原样传入。

## 要做的

1. 改 `bin/decision-inbox`，按假设 1。
2. 加测试：在一个含假 `decision_inbox` 包（运行时打印标记）和假 `runpy.py` 的临时目录里运行 `bin/decision-inbox glossary`，输出里不得有假标记、退出码 0、输出是真术语表。

## 做 / 不做

- 做：上面 1、2。
- 不做：改 `~/.decision-inbox/bin/decision-inbox` 转发脚本的生成逻辑（它 exec 的是插件的 `bin/decision-inbox`，修这一处就够）；钩子命令（`hooks/hooks.json` 也走 `bin/decision-inbox`）；改版本号、打标签；升级本机 di-p0。

## 验收标准

1. 新测试在当前 main（85debcf）上失败（输出是假包的标记），改后通过。
2. 全量 `PYTHONPATH=tests:. python3 -m unittest discover -s tests` 通过。
3. 用 `/usr/local/bin/python3`（3.10）手工复核：在本仓库目录外的临时目录里放假包，`bin/decision-inbox glossary` 跑的是真代码；`whoami` 仍按调用者目录。

## 风险

- `-c` 下 `import runpy` 若早于换路径，会被当前目录里的 `runpy.py` 劫持：引导代码先换路径再导入，测试里放了假 `runpy.py` 盯着这一点。

## 文档建议

无（行为对用户不可见，只是不再跑错代码）。
