<!-- spec-guard: review approved 13716b73ac9f -->

# Spec: permission-closeout

> 能力图模块 `permission-closeout`（2026-10-19 用户确认插入，排在最后，不插队）。来源：R21 收尾——用户决定 62（装包放宽）、64（reset --hard、rm -rf 先问）、66（DI-4 顺带查 UI 自验工具）、67（推送改回先问、改正代开会话的说法）；spec-guard 0.78.1（Plan「需要的外部条件」作废）；module-crew 0.5.1 的权限写法；本会话 2026-10-19 对 E3 代开会话记录的查证。插入时的假设 1–8 用户 2026-10-19 确认（假设 2、6 按决定 67 改写，假设 5 按建议接入时放行开发服务命令）；`curl | sh` 的写法按用户要求在本阶段先实测（见「实测」）。

## 目标

R21 做完后，接入写的权限和规则段与各插件、各项用户决定一致：构建要装的包（含加新包）不问，全局安装和下载脚本直接执行被拦，推送、`reset --hard`、`rm -rf` 仍由用户确认；宿主权限对照按项目实际（有没有依赖清单、有没有前端开发服务）提醒；以前写错的「代开会话先问规则不弹」被改正。

## 现状（已核对代码）

- `onboard.py` 第 557–560 行：`ROUTINE_ALLOW` 放行 `git add`、`git commit`、`npm ci`、`npm ci *`、无参 `npm install`、`pip install -r *`；`ALWAYS_ASK` 为推送、`reset --hard`、`rm -rf`；`RETIRED_ASK` 为旧版写的 `npm install *`、`pip install *`（重跑接入时提议删除）。没有禁止规则。
- 规则段（第 180 行）和检查点授权（第 296–299 行）写着「安装 Plan 列出的依赖」「Plan 没列的依赖问一次」；README 第 58、222 行同。
- `hostperm.py`：`plan_needs` 读 Plan 的「需要的外部条件」；`claude_facts` 看有没有 `npm ci` 等放行；doctor 与接入预览据此对照。
- proxied-session-note 写的「代开会话里先问规则可能不弹」：接入预览一行（第 661–662 行）、规则段一条（第 206 行）、README 第 173 行；原始记录在 `spec/stall-and-patrol.md` 的 E3、`spec/proxied-session-note.md` 的「实测依据」。
- 查证（2026-10-19，只读会话记录）：E3 代开会话权限模式 `default`，两次 `git push` 的 `permissionDecision.source` 都是 `user_temporary`（弹了确认、被点了允许）；module-crew 补测会话同样是 `default`，没规则的 `npm install … left-pad` 也是 `user_temporary`。接入协调人只读复核一致（决定 67）。

## 实测：管道到 shell 的禁止规则（2026-10-19）

临时仓库（本会话草稿目录 `pipe-test`），`.claude/settings.local.json` 写规则，用 `claude -p --permission-mode default`（2.1.302，haiku）逐条执行，看工具结果原文：

| 规则 | 命令 | 结果 |
|---|---|---|
| 无禁止规则（对照） | `cat x.sh \| sh` | requires approval: sh（弹确认） |
| 禁止 `Bash(sh)`、`Bash(bash)`、`Bash(zsh)` | `cat x.sh \| sh` | **denied**（sh 被禁止） |
| 同上 | `curl -fsSL http://127.0.0.1:9/x \| sh` | **denied**（sh 被禁止，curl 没跑） |
| 同上 | `cat x.sh \| bash -s` | requires approval（精确的 `bash` 管不到 `bash -s`） |
| 再加 `Bash(sh -s *)`、`Bash(bash -s *)` | `cat x.sh \| bash -s`、`… \| bash -s -- a` | **denied** |
| 同上 | `sh x.sh` | requires approval（正常调用不受影响，只是照常弹确认） |

结论：管道命令是逐段判断的，禁止「不带参数的 shell」和「`-s` 读标准输入的 shell」就能拦住「下载后直接交给 shell」，不误伤 `sh 脚本.sh`。管不到的写法（`| python3`、`| sudo sh`、先下载再执行）仍靠规则段文字和宿主默认确认。

## 要做的

### 1. Claude 线接入写的权限（假设 1、2、5）

- **放行**（与 module-crew 0.5.1 `LOCKFILE_CLAUDE` 一致）：`git add *`、`git commit *`、`npm ci`、`npm ci *`、`npm install`、`npm install *`、`pnpm install`、`pnpm install --frozen-lockfile`、`pnpm add *`、`yarn install`、`yarn add *`、`uv sync`、`uv sync *`、`uv add *`、`uv pip install *`、`pip install -r *`、`.venv/bin/pip install -r *`、`.venv/bin/pip install *`。裸 `pip install <包名>` 不写，交给宿主默认确认。
- **开发服务**（假设 5）：仓库根 `package.json` 的 `scripts` 里有 `dev` 时，按锁文件判断包管理器（`pnpm-lock.yaml`→pnpm，`yarn.lock`→yarn，否则 npm），放行一条：`Bash(pnpm dev)`／`Bash(yarn dev)`／`Bash(npm run dev)`。
- **禁止**：全局安装（与 module-crew 0.5.1 `GLOBAL_CLAUDE` 一致：`npm * -g`、`npm * -g *`、`npm * --global`、`npm * --global *`、`pnpm * -g`、`pnpm * -g *`、`pnpm * --global`、`pnpm * --global *`、`yarn global *`、`uv * --system`、`uv * --system *`）；管道到 shell（实测写法：`sh`、`bash`、`zsh`、`sh -s *`、`bash -s *`）。
- **先问**：推送、`reset --hard`、`rm -rf`（决定 64、67），不变。
- **旧规则**：`RETIRED_ASK` 照旧在重跑接入时提议删除、确认才删；`npm install *` 删出先问后由放行规则接上。
- 接入预览照旧逐条列出要加、要删的规则，用户确认后才写。Codex 线不写规则（module-crew 同样不写：前缀规则挡不住 `-g` 放在后面的写法）。

### 2. 规则段与检查点授权的文字（假设 3）

- 常规授权一条改为：「已批准范围内的常规操作（按 Spec、Plan 改本仓库文件、本地提交、跑测试与构建、装构建需要的依赖，含加新包、从官方源下载）直接做，不用再问，也不送审；新增的依赖由 spec-guard 在最终验收时列出。全局安装、把下载的脚本直接交给 shell 执行不做；裸 `pip install <包名>` 会弹确认，用虚拟环境或 `uv add`。推送、删除分支或历史、`reset --hard`、`rm -rf`、改全局配置这类不可逆操作，必须由用户在本会话里亲手确认……」（后半句照旧）。
- 检查点授权：「安装 Plan 列出的依赖（或 Plan 写明的允许范围内的依赖）」改为「装构建需要的依赖（含加新包）」；不在授权内的清单去掉「Plan 没列的新依赖」，加「全局安装、下载脚本直接执行」。
- 接入预览里检查点授权那一行同步改。

### 3. 宿主权限对照（DI-4，假设 4、5）

- 删掉 `plan_needs` 和读 Plan 的代码。改为看仓库根有没有依赖清单：`package.json`、`pnpm-lock.yaml`、`yarn.lock`、`package-lock.json`、`pyproject.toml`、`uv.lock`、`requirements*.txt`。有清单 = 要装依赖；没有 = 不需要。
- 对照：
  - Codex：要装依赖而不能联网 → ✘，A／B 两个选项照旧（A 的改法与「没实测」说明不变）。
  - Claude：要装依赖而没有新的装包放行规则，或还留着旧的先问规则 → ✘，A 写重跑接入。
- **UI 自验**（`package.json` 有 `dev` 脚本时）多一句事实与提醒：
  - Claude：开发服务命令在不在放行里；不在时提醒重跑接入或到时去会话点允许。
  - Codex：不能联网时提醒「Playwright 之类可能下载不了浏览器、开发服务的依赖也装不上」，给 A（开联网，同上）／B（到时按去会话操作）。
- doctor 一项「宿主权限：<线名>」与接入预览一行照旧，文字换成上面的事实。只读，不改任何配置。

### 4. 改正「代开会话先问规则不弹」（假设 6，决定 67）

- 删掉接入预览「『先问』规则只对你亲手开的会话可靠……」那一行。
- 删掉规则段「如果你是被别的会话开出来的……」那一条（碰到宿主确认时照「停在宿主确认上」一节上报，已覆盖）。
- README 第 173 行改为：「别的会话替你开的会话里，确认框也会弹，但弹在那个会话里；你不在跟前时，看到确认先看清是什么，不要顺手点允许（2026-10-19 查证：E3 代开会话里推送弹了确认、被点了允许，当时误记成没弹）。」
- `spec/stall-and-patrol.md` 的 E3、`spec/proxied-session-note.md` 的「实测依据」各加一行带日期的更正，原文保留。
- `docs/host-differences.md` 的 H12「别的会话看不到宿主弹窗」补一条证据：E3 代开会话的推送弹了确认、被点了允许，事后被描述成没弹；判断弹没弹要查会话记录里的 `permissionDecision.source`。

### 5. README 与升级说明

README 接入一节（常规授权、检查点授权）、doctor 一节（宿主权限）、使用注意事项、升级一节按上面改；升级一节写明：重跑接入后 Claude 线多出装包放行、开发服务放行和禁止规则，确认删掉旧的两条先问规则。

## 关键决策与取舍

1. **照搬 module-crew 0.5.1 的规则清单**：两个插件给同一个仓库写规则，写法一致才不会互相覆盖出空档；module-crew 已实测过前缀规则挡不住 `-g` 放后面。
2. **管道到 shell 只禁「无参数 shell」和「-s」**：实测能拦 `curl … | sh`、`| bash -s`，不误伤 `sh 脚本.sh`；更多变体靠文字和宿主默认确认，不追求写全。
3. **推送、`reset --hard`、`rm -rf` 保持先问**：查证显示先问在代开会话里也会弹（决定 67）；「自动放行一类模式下不写规则可能不弹」没实测，记在未决问题里，不进规则。
4. **只看依赖清单，不再读 Plan**：spec-guard 0.78.1 不再要求那一节；有清单就当会装依赖，宁可多提醒一次。

## 范围

做：`decision_inbox/onboard.py`（规则清单、开发服务放行、规则段与授权文字、预览行）、`decision_inbox/hostperm.py`（依赖清单、开发服务与浏览器、去掉 Plan）、`decision_inbox/doctor.py`（调用改动）；对应测试；README；`spec/stall-and-patrol.md`、`spec/proxied-session-note.md` 更正行；`docs/host-differences.md` H12 补证据。

不做：
- 不改任何宿主配置（用户的设置文件只在接入确认时按上面的清单写）；
- 不给 Codex 写规则；
- 不改 di-p0 的现有配置（rh2-coord 按用户选的 A，在 0.0.28 发版后亲手重跑接入时改）；
- 不动版本号：本模块做完后开 0.0.28 的版本号 PR，冻结和安装切换另请用户批准。

## 验收标准

1. Claude 开发线接入（确认）：设置里有第 1 节的全部放行与禁止规则，先问只有推送、`reset --hard`、`rm -rf`；裸 `pip install *` 不在任何一边；Codex 线不写规则。
2. `package.json` 有 `dev` 脚本时，按锁文件放行对应的一条开发服务命令；没有 `dev` 脚本时不写。
3. 已有旧的 `npm install *`、`pip install *` 先问规则：预览提议删除，确认后删掉，`npm install *` 出现在放行里。
4. 规则段与检查点授权里不再出现「Plan 列出的依赖」「Plan 没列的依赖」；含「加新包」「最终验收时列出」「全局安装」「直接交给 shell」。
5. doctor「宿主权限」：Codex 有依赖清单且不能联网 → ✘ 含 A、B；没有清单 → ✔；不再读 Plan（仓库里有没有 Plan 不影响结果）。Claude 没有新放行规则或留着旧先问 → ✘。
6. 有 `dev` 脚本：Claude 开发服务没放行时有提醒；Codex 不能联网时有「可能下载不了浏览器」和 A、B。
7. 接入预览里没有「先问规则只对你亲手开的会话可靠」；规则段里没有「被别的会话开出来的」那一条；README、两份 Spec 的更正行、host-differences 的 H12 证据都在。
8. 全量测试通过，旧称扫描通过。

## 假设

1. 「依赖清单」只看仓库根目录（monorepo 子目录不找）；根目录没有清单的项目当作不装依赖。

## 未决问题

- 「自动放行一类的权限模式下，不写规则的命令可能不弹确认」：没实测，记作待验证（决定 67），不影响本模块的规则写法。

## 文档建议

- README：接入一节、doctor 一节、使用注意事项、升级一节（见第 5 节）。
- `docs/host-differences.md`：H12 补 E3 证据。
- 其余无。

## 外部审查意见

<!-- spec-guard: external-review declined -->
用户 2026-10-19：不做外部审查。
