<!-- spec-guard: review approved 267e20caa022 -->

# Spec: scope-authority-defaults

> 能力图模块 `scope-authority-defaults`（2026-10-19 用户确认插入，排在最后，不插队）。来源：接入协调人转来的 R21「模块打转」分派给本插件的 DI-1、DI-2、DI-3（依据用户决定 58–60）；R21 拆成 4 个模块，这是第 1 个。插入时的假设 1–6 用户 2026-10-19 确认；DI-2 的做法用户 2026-10-19 改定为「选 A」（见关键决策 2）。

## 目标

已批准的 Spec、Plan 范围内的事，包括 Plan 列出的依赖安装和官方源联网，做的时候不再问用户；只有 Plan 没列的新依赖才问，且只问一次。推送、强制重置、递归删除照旧先问。

## 现状（已核对代码与官方文档）

- **授权默认关**：`onboard.join` 的 `checkpoint_authority` 默认 False，命令行要加 `--checkpoint-authority` 才打开。打开后，协作规则段多一节「检查点答复即授权」（`onboard._AUTHORITY`），授权范围写的是「为完成检查点所需的安装依赖、联网下载……」，没有限定 Plan 列出的依赖和官方源。`commands/join.md`、Codex 的 join skill、README 都写着「默认不开」。
- **规则段把联网装依赖算作不可逆**：`_COMMON` 的「停滞询问与常规授权」一节写着「推送、删除分支或历史、联网安装依赖、改全局配置这类不可逆操作，必须由用户在本会话里亲手确认」。这句是 stall-and-patrol（R16）加的。
- **Claude 权限固定先问**：`onboard.ALWAYS_ASK` 里有 `Bash(npm install *)`、`Bash(pip install *)`。接入时只追加缺的规则（`_merge_rules`），从不删除。
- **Claude Code 权限规则的语义**（官方文档 https://code.claude.com/docs/en/permissions，已核实）：
  - 末尾「空格 + `*`」的规则也匹配不带参数的命令，`Bash(npm install *)` 同时匹配 `npm install` 和 `npm install lodash`；
  - 没有 `*` 的规则只匹配完全相同的一条命令；
  - 判断顺序是 deny → ask → allow，先匹配到的为准，规则写得更具体也不改变顺序；
  - 用 `&&` 等连起来的复合命令按段分别检查。

## 要做的

1. **DI-1 授权默认打开**：
   - `onboard.join` 默认 `checkpoint_authority=True`；命令行新增 `--no-checkpoint-authority` 用来关掉，原来的 `--checkpoint-authority` 保留，等于默认值。
   - 名册条目照旧记 `checkpointAuthority`：打开时为 true，关掉时不写这个键。
   - 改写「检查点答复即授权」一节，写明授权什么、不授权什么：
     - 授权：Spec、Plan 范围内的常规操作，以及 Plan 列出的依赖（或 Plan 写的允许范围）的安装，只从官方源下载；项目已有的依赖规则照旧（锁文件、新版本发布时长等）。
     - 不授权：Plan 没列的新依赖（要问一次）；把密钥或凭据发到外部；删除工作区以外的文件或大范围删除；推送、合并、发布；修改全局配置。
   - 接入预览开头加一行，说明默认打开了这项授权，不要就加 `--no-checkpoint-authority`。
2. **DI-2 Claude 权限（选 A）**：
   - `ALWAYS_ASK` 去掉 `Bash(npm install *)`、`Bash(pip install *)`，只留推送、`reset --hard`、`rm -rf`。
   - `ROUTINE_ALLOW` 加 `Bash(npm ci)`、`Bash(npm ci *)`、`Bash(npm install)`（只匹配不带参数的这一条）、`Bash(pip install -r *)`。
   - 带包名的 `npm install <包>`、`pip install <包>` 不匹配本插件写的任何规则，交给宿主的默认处理（默认权限模式下会弹窗问）。规则段写明「加新包要先问，只问一次」。
   - **清理旧规则**：重跑接入时，如果 `.claude/settings.local.json` 的 ask 里有旧版本插件写的 `Bash(npm install *)` 或 `Bash(pip install *)`，预览列出并提议删除，确认后只删这两条原文，别的规则不动。删不删以预览为准，不确认就不改。
3. **DI-3 规则段**：
   - 「停滞询问与常规授权」一节改为：已批准范围内的常规操作（按 Spec、Plan 改本仓库文件、本地提交、跑测试与构建、安装 Plan 列出的依赖）直接做，不用再问，也不送审；Plan 没列的依赖，抛一项【等待用户】问一次，一次列全要加的包；推送、删除分支或历史、改全局配置仍然必须由用户在本会话里亲手确认。
   - 去掉「联网安装依赖」算作不可逆操作的说法。
4. **文档**：`commands/join.md`、Codex 的 join skill、README 的「检查点答复即授权」和接入一节，改成「默认打开，可用 `--no-checkpoint-authority` 关掉」，并写明 Claude 权限的新规则；README 的升级一节写明协作规则段变了，已接入的线要重跑接入。

## 关键决策与取舍

1. **授权的边界写在规则段，不靠宿主强制**：宿主规则分不出「Plan 列出的包」。边界由规则段约束，宿主那一层只放行「按锁文件或清单装」。
2. **DI-2 选 A**（用户 2026-10-19）：ask 规则优先于 allow，所以不能在 ask 里留 `npm install *`、再在 allow 里放行裸 `npm install`。改为 ask 里不写 npm、pip 安装，带包名的安装交给宿主默认处理。代价是：auto 模式下加新包会不会问，由宿主自己判断，所以规则段要写明先问。
3. **只删本插件写过的原文**：清理旧 ask 规则时只认那两条字符串，不碰用户自己写的规则；不确认就不删。
4. **Codex 不在本模块**：接入时写的 Codex 侧权限和联网对照留给第 3 个模块（DI-4）。

## 范围

做：`decision_inbox/onboard.py`（默认值、授权一节、常规授权一节、权限规则与旧规则清理）、`decision_inbox/__main__.py`（`--no-checkpoint-authority`）、`commands/join.md`、`skills/decision-inbox-join/SKILL.md`、README，以及对应测试。

不做：
- 不改 Codex 的权限和沙箱（DI-4）；
- 不改决策收件箱的规则段（hub 角色）；
- 不改契约；
- 不动版本号：4 个模块都做完后再一起发版，冻结和安装切换另请用户批准。

## 验收标准

1. 不加参数接入开发线：协作规则段有「检查点答复即授权」一节，写明授权与不授权的内容；名册条目 `checkpointAuthority` 为 true；预览开头有一行说明默认打开、怎么关。
2. 加 `--no-checkpoint-authority`：没有这一节，名册不写这个键；加 `--checkpoint-authority`：和默认一样。
3. Claude 线接入时写的权限：allow 里有 `npm ci`、`npm ci *`、`npm install`、`pip install -r *`；ask 里只有推送、`reset --hard`、`rm -rf`，没有 npm、pip 安装。
4. 设置文件 ask 里已有旧版写的 `Bash(npm install *)`、`Bash(pip install *)`：预览列出要删的这两条；确认后只删这两条，用户自己写的其他规则原样保留；不确认不改。
5. 规则段不再把「联网安装依赖」列为不可逆操作，写明 Plan 没列的依赖问一次、小步骤不送审。
6. `commands/join.md`、join skill、README 不再写「默认不开」。
7. 全量测试通过。

## 假设

1. 官方文档描述的权限语义（上面「现状」最后一条）就是当前宿主的行为；实跑验证留到冻结后的实测。
2. 旧版插件写进设置文件的 ask 规则原文就是 `Bash(npm install *)`、`Bash(pip install *)`（`ALWAYS_ASK` 从 stall-and-patrol 起没有变过）。

## 未决问题

无。

## 文档建议

README：接入一节和「检查点答复即授权」一条改为默认打开；写明 Claude 权限的新规则；升级一节写明要重跑接入。其余无。
