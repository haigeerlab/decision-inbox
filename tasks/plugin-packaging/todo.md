# Todo: plugin-packaging

测试命令：`python3 -m unittest discover -s tests -v`

- [x] Task 1：`bin/decision-inbox`、`shim`、固定命令路径
  - 验收：Spec 验收 1（转发脚本可执行、等价于插件的 `bin/decision-inbox`、内容不变不重写、`--if-installed` 在目录不存在时什么都不建）、Spec 验收 4（收件枢纽约定块、巡视提示词、onboarding 步骤里的命令都是固定路径；`onboard hub`／`join` 确认时写出转发脚本）
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`bin/decision-inbox`、`decision_inbox/install.py`、`decision_inbox/__main__.py`、`decision_inbox/hub.py`、`decision_inbox/patrol.py`、`decision_inbox/onboard.py`、`tests/test_install.py` 及相关测试

- [x] Task 2：`whoami` 与 `hook stop` 不带 `--group`
  - 验收：Spec 验收 2（仓库目录、子目录、规则文件目录能认出；对不上退出码 4；对上多个退出码 5 并列出）、Spec 验收 3（不带 `--group` 时有人在等就拦；没接入静默放行；对上多个时放行并在 stderr 说明；带 `--group` 行为不变）
  - 验证：`python3 -m unittest discover -s tests -v`
  - 文件：`decision_inbox/install.py`、`decision_inbox/__main__.py`、`tests/test_install.py`

- [x] Checkpoint 1（report）：全部测试全绿，记下命令与结果后继续
  - 记录（2026-10-17）：`python3 -m unittest discover -s tests -v` → Ran 414 tests, OK。Task 1、2 的测试都先失败；Task 1 改默认路径后，hub-loop 一条写死 `python3 -m decision_inbox` 的旧断言按计划改为固定路径；变异检查：查找只认仓库本身、不认子目录，被 1 个测试抓住

- [ ] Task 3：`hooks.json`、两份清单、`marketplace.json`
  - 验收：Spec 验收 5（名字、版本一致；Codex 清单含 `skills`、`hooks`；marketplace 指向仓库根目录）、Spec 验收 6（两条钩子命令在 `PLUGIN_ROOT` 或 `CLAUDE_PLUGIN_ROOT` 下都能跑；两者都没有时退出码 0、没有 stdout；有人在等时输出 block JSON）
  - 验证：`python3 -m unittest discover -s tests -p test_packaging.py -v`
  - 文件：`hooks/hooks.json`、`.claude-plugin/plugin.json`、`.claude-plugin/marketplace.json`、`.codex-plugin/plugin.json`、`tests/test_packaging.py`、`tests/test_package.py`

- [ ] Task 4：8 个斜杠命令与 Codex 技能
  - 验收：Spec 验收 7（都有 `description`；接入、卸载类写明「先预览、用户确认后加 --confirm」；用到的子命令都存在；查询命令要求原样显示输出）
  - 验证：`python3 -m unittest discover -s tests -p test_packaging.py -v`
  - 文件：`commands/*.md`、`skills/decision-inbox-join/SKILL.md`、`tests/test_packaging.py`

- [ ] Task 5：README
  - 验收：Spec 验收 8（安装两边、接入顺序、日常用法、升级、卸载与 `~/.decision-inbox` 保留、排查）；文中命令与实际子命令一致
  - 验证：`python3 -m unittest discover -s tests -p test_packaging.py -v`
  - 文件：`README.md`、`tests/test_packaging.py`

- [ ] Checkpoint 2（report）：全部测试全绿（Spec 验收 9）；在 scratchpad 里用复制出来的插件按 `hooks.json` 的命令手动跑一次放行和拦截，记下输出后继续

- [ ] Task 6：本机安装与实测
  - 验收：Spec 验收 10。先问用户。按规格测试策略的实测 4 步走；Codex 侧只验安装；结果写进 `spec/plugin-packaging.md` 的实测记录
  - 验证：`claude plugin list`、命令输出、定时任务运行记录、钩子拦截与放行、卸载后的插件列表
  - 文件：`spec/plugin-packaging.md`

- [ ] Checkpoint 3（gate）：模块最终验收——全部测试全绿、10 条验收标准逐条有测试或实测记录、列出实际改动文件、原样附上规格差异、能力图完成时的文档建议；停下等用户确认
