# Todo: crew-coordinator-seam

测试命令：`python3 -m unittest discover -s tests -v`

- [x] Task 1：停止钩子跳过已挂起的模块，并给协调会话开例外
  - 验收：Spec 验收 4
  - 文件：`decision_inbox/stophook.py`、`decision_inbox/store.py`、`tests/test_stophook.py`、`tests/test_store_roster.py`
  - 记录（2026-10-18）：先写用例。新增的用例有：挂起的模块放行；协调会话有没勾完的 todo 时放行；协调会话有人在等时照常拦；协调会话有已答复、没发【已恢复】的事项时照常拦；普通开发线照常拦；两个字段只认布尔值，crewCoordinator 只能用于 dev，localRules 只能用于 Claude。先跑，2 个失败；实现 `_silent_stop` 的两个例外和名册校验后通过。Ran 599 tests, OK

- [x] Task 2：`--crew-coordinator` 标记和约定块里的新一节
  - 验收：Spec 验收 3
  - 文件：`decision_inbox/onboard.py`、`decision_inbox/doctor.py`、`decision_inbox/__main__.py`、`commands/join.md`、`tests/test_onboard.py`、`tests/test_doctor.py`
  - 记录（2026-10-18）：
    - 先写用例：预览阶段不写名册；确认后标记写进名册，约定块里在「开发线」一节之后多出「### 并行开发协调会话」，8 条要点都在；去掉参数重跑后，标记和这一节都消失；负责人、总协调带这个标记会报错，名册不变；其他角色的约定块里没有这一节；doctor 核对为 ok，修复命令保留 `--crew-coordinator`。先跑，4 个报错。
    - 实现：`_CREW_COORDINATOR`、`block(crew_coordinator=)`、`join(crew_coordinator=)`、doctor 的期望约定块和修复命令（修复命令同时保留 `--checkpoint-authority`，以前漏掉了，照着重跑会把它关掉）、命令参数、`commands/join.md`。Codex 的接入 skill 不改：module-crew 第一版的协调会话只在 Claude 上跑。
    - 结果：Ran 603 tests, OK

- [x] Task 3：`--local-rules`：写进 CLAUDE.local.md，处理忽略规则，加 AGENTS.md 警告
  - 验收：Spec 验收 1、2
  - 文件：`decision_inbox/onboard.py`、`decision_inbox/doctor.py`、`decision_inbox/__main__.py`、`tests/test_onboard.py`、`tests/test_doctor.py`
  - 记录（2026-10-18）：
    - 先写 8 个用例，都在真实的临时 git 仓库里跑：
      - 预览不写文件，并提示会改 info/exclude；
      - 确认后约定块写进 CLAUDE.local.md，CLAUDE.md 一字不变；
      - 重跑不会重复加 exclude 行，`git status` 里看不到 CLAUDE.local.md；
      - leave 删掉约定块，删掉这个由插件新建的文件，也删掉那一行 exclude；
      - 已经被 .gitignore 忽略时，exclude 不加也不删；
      - worktree 里接入时，写的是公共目录的 info/exclude；
      - 不是 git 仓库也照常写；
      - Codex 接入报错；只有 AGENTS.md 时给出警告；
      - doctor 核对为 ok，修复命令保留 `--local-rules`。
    - 先跑，8 个报错。
    - 实现：`rules_path`、`_git_exclude`（`rev-parse --git-common-dir`）、`_git_ignored`（`check-ignore -q`）、`_add_exclude`、`_drop_exclude`（状态里记 `excludeAdded`；只删插件自己加的那一行，别的会话还要用就不删）、join 和 leave 走同一套路径、命令参数。
    - 结果：Ran 611 tests, OK

- [x] Task 4：文档和版本 0.0.16
  - 验收：Spec 验收 5
  - 文件：`README.md`、`docs/host-differences.md`、`commands/join.md`、两份 `plugin.json`、`tests/test_packaging.py`
  - 记录（2026-10-18）：先改打包测试（版本 0.0.16；README 里要有 `--crew-coordinator`、`--local-rules`、`CLAUDE.local.md`、「不再读 AGENTS.md」；join 命令说明里要有两个新参数），3 处失败。然后补齐：README 接入一节加两条、使用注意事项加一行、升级一节说明 0.0.16 已接入的会话不用重跑；宿主差异新增 H26（依据官方文档，桌面版是否加载列入待复核第 8 条）；join 命令说明；两份清单改为 0.0.16。Ran 611 tests, OK

### Checkpoint（gate）：模块最终验收

- [ ] 全部测试通过；验收标准逐条有证据；列出实际改动的文件
