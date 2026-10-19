<!-- spec-guard: review approved cdd12c7e25ab -->

# Spec: host-permission-check

> 能力图模块 `host-permission-check`（2026-10-19 用户确认插入，排在最后，不插队）。来源：R21「模块打转」分派给本插件的 DI-4（依据用户决定 58–60）；R21 拆成 4 个模块，这是第 3 个。插入时的假设 1–6 用户 2026-10-19 确认，假设 2 按建议：先直接读 Plan 里这一节，以后 spec-guard 在 `/map --json` 给出时再改读那里。

## 目标

一条开发线接入决策收件箱后，能做的事不比在自己会话里少；做不了时提前说清楚。接入预览和 doctor 只读宿主的实际权限，与当前模块已批 Plan 写的「需要的外部条件」对照；对不上就提醒，给出确切改法（由用户自己改）或「到时去会话点允许」两个选项。

## 现状（已核对代码、源码与配置）

- **Codex 的权限来源**（openai/codex main 分支源码查证，本机 codex-cli 0.162.1，没有实跑）：
  - 全局 `~/.codex/config.toml`：`sandbox_mode`（`read-only`／`workspace-write`／`danger-full-access`）；`[sandbox_workspace_write] network_access`（默认 false）；`[projects."<路径>"] trust_level = "trusted"`。
  - 项目里的 `.codex/config.toml`（当前目录、上级目录、git 仓库根）：只在项目受信任时生效；`sandbox_workspace_write` 不在项目配置的屏蔽清单里，可以按项目开联网（`codex-rs/config/src/loader/mod.rs`、`config_toml.rs`）。
  - 本机现状：全局 `sandbox_mode = "workspace-write"`，没开 `network_access`，多个项目已设为 trusted。
  - 用户的 Codex 线跑在 Codex 桌面应用里；桌面应用是否用同一套配置加载，文档没有直接写，未实测。
- **Claude 的权限来源**：仓库 `.claude/settings.json` 与 `.claude/settings.local.json` 的 `permissions.allow`／`ask`；scope-authority-defaults 起接入会放行 `npm ci`、`npm ci *`、`npm install`、`pip install -r *`。
- **本插件**：doctor 已经手工按行读 `~/.codex/config.toml`（钩子信任、插件安装；Python 3.10 没有内置 TOML 解析）；接入时已检查 Codex 能否加载协作规则段（`onboard.codex_loads`）。没有读沙箱、联网、项目信任。
- **Plan 的「需要的外部条件」**：R21 的 SG-2 要求 spec-guard 在 Plan 模板加这一节，还没发版。spec-guard 自己的 Plan 已经这样写：`需要的外部条件：无（不装依赖、不联网；…）`（Plan 开头的一行字段）。正式模板可能是一行字段，也可能是一个小节标题。

## 要做的

1. **读宿主事实**（新模块 `decision_inbox/hostperm.py`，只读）：
   - Codex：全局 `sandbox_mode`、`network_access`；仓库路径或它的上级目录有没有 `trust_level = "trusted"`；仓库里 `.codex/config.toml` 的 `sandbox_mode` 和 `network_access`（项目受信任时才算数）。得出三个事实：能不能写工作区、能不能联网、项目受不受信任。
   - Claude：两个设置文件里有没有本插件放行的安装规则（`npm ci`、`npm install`、`pip install -r *`），ask 里还有没有旧版写的 `npm install *`、`pip install *`。
   - 读不到文件、格式看不懂时不报错，这一项记为「未知」并写明原因。
2. **读 Plan 的需要**：从 spec-guard 读当前模块（`/map --json` 的 `activeModule`），再读这条线仓库里 `tasks/<当前模块>/plan.md`：
   - 认两种写法：一行 `需要的外部条件：…`（续行到空行为止），或者一个标题为「需要的外部条件」的小节（到下一个标题为止）；
   - 内容以「无」开头算「不需要」；其余算「需要装依赖或联网」（不细分）；
   - 没有当前模块、没有 Plan 文件、Plan 里没有这一项：算「Plan 没写，没法对照」。
3. **对照规则**：
   - Plan 需要、宿主不让：Codex 不能联网，或 Claude 没有放行安装规则（或还留着旧的先问规则）→ 对不上；
   - Plan 不需要、或宿主都允许 → 对得上；
   - Plan 没写 → 只列宿主事实，不判断。
4. **doctor**：每条开发线加一项「宿主权限：<线名>」：
   - 对得上：✔，写宿主事实（例如「Codex 可写工作区、可联网（项目配置）、项目已信任」）；
   - Plan 没写：✔，写宿主事实，加一句「Plan 没写需要的外部条件，没法对照」；不算异常；
   - 对不上：✘，写哪里对不上，「怎么做」给两个选项：
     - **A 自己改**（确切改法）：Codex——先确认项目已信任（没信任就先「在 Codex 里信任这个项目」），再在仓库建 `.codex/config.toml`，写 `[sandbox_workspace_write]` 和 `network_access = true`；注明「依据 openai/codex 源码，Codex 桌面应用没实测，改完在开发会话里试一次」；不改 `~/.codex/config.toml`。Claude——重跑接入拿到新规则（scope-authority-defaults），确认删掉旧的两条先问规则。
     - **B 到时去点**：不改配置，开发线碰到时按「去会话操作」上报，在决策收件箱最上面一栏提醒你。
   - 宿主事实未知：「?」（未知），写原因。
5. **接入预览**：开发线接入时同样对照一次；对不上就在提醒（⚠）里写一行，附 A、B 两个选项的简短说明，完整改法见 doctor。
6. **不写任何宿主配置**：不写 `~/.codex/config.toml`、项目 `.codex/config.toml`、Claude 设置文件（Claude 设置照旧只由接入确认时按 scope-authority-defaults 写）。

## 关键决策与取舍

1. **只读 Plan 这一项，不解析别的**（假设 2）：本插件原则上不解析 spec-guard 的文件；这里是例外，只找这一项、只分「无」和「其他」。spec-guard 以后在 `/map --json` 给出时改读那里。
2. **判断宽松**：「需要的外部条件」写了任何不是「无」的内容，都按「可能要装依赖或联网」处理，宁可多提醒一次。
3. **改法 A 只给文字**：本插件不改任何宿主配置（R21 边界）；改法注明来源和没实测。
4. **只看开发线**：审查者、跨线协调不跑构建，不对照。

## 范围

做：新文件 `decision_inbox/hostperm.py`；`decision_inbox/doctor.py`（每条开发线一项）；`decision_inbox/onboard.py`（接入预览一行）；对应测试；README（doctor 一节、接入一节）。

不做：
- 不写任何宿主配置；
- 不细分「装依赖」和「联网」；
- 不对审查者、跨线协调对照；
- 不动版本号：R21 的模块做完再一起发版。

## 验收标准

1. Codex 线，Plan 写了需要（非「无」），全局没开联网、项目没有 `.codex/config.toml`：doctor 这一项 ✘，A、B 两个选项齐全，A 含 `.codex/config.toml` 两行写法、「没实测」说明；所有配置文件读前读后逐字相同。
2. 同上，但项目受信任且项目 `.codex/config.toml` 开了 `network_access`：✔；项目不受信任时同样的项目配置不算数，仍 ✘，A 先写「在 Codex 里信任这个项目」。
3. 全局开了 `network_access`，或 `sandbox_mode = "danger-full-access"`：✔。
4. Plan 写「需要的外部条件：无」：✔；Plan 没有这一项、没有 Plan、没有当前模块：✔ 并写「没法对照」，不计异常。两种写法（一行字段、小节标题）都认。
5. Claude 线，Plan 需要，设置里没有放行安装规则或还留着旧的先问规则：✘，A 写重跑接入；有放行规则：✔。
6. 配置读不到或看不懂：「?」并写原因。
7. 接入 Codex 开发线时对不上：预览有一行 ⚠，含 A、B。
8. 全量测试通过，旧称扫描通过。

## 假设

1. Codex 的项目信任按路径前缀算：仓库路径本身或它的任一上级目录设为 trusted，就算受信任（与本机配置里 `/Users/vilin` 被设为 trusted 的用法一致）。
2. 当前模块取 spec-guard `/map --json` 的 `activeModule`；读不到 spec-guard 时按「Plan 没写」处理。

## 未决问题

无。

## 文档建议

README：doctor 一节加「宿主权限」一项的说明和两个选项；接入一节写明接入时会对照。其余无。
