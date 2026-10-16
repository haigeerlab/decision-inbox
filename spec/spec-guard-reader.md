<!-- spec-guard: review approved d09f6f8ec992 -->
# Spec: spec-guard-reader

> 能力图模块 `spec-guard-reader`。需求来源：`docs/requirements-record.md` 第 7 节「按 spec-guard 实际接口调整」第 3、5 条，第 10.2～10.3 节，第 13 节第 1～3 行。
> 接口依据：spec-guard 仓库 main 上的 `spec/map-view.md`、`spec/stall-signals.md` 的 Contract 一节（`schemaVersion: 1`）；本机实测 spec-guard 0.63.0（2026-10-16）。

## 目标

对每条线的仓库，只读调用 spec-guard 的 `map_view.py --project <仓库> --json`，把结果整理成本插件统一使用的只读数据：
- 模块表：状态、进度、依赖、挂起原因、挡住了哪些模块、Spec/Plan 评审标记；
- 停滞数据：勾选时间、勾选次数、挂起开始时间，以及 git 历史是否完整；
- 仓库提交情况：未合入主线的提交数、未推送的提交数。

下游 line-health、map-view、query-commands 都从这里拿单项目的数据，**全插件不自己解析能力图和 todo**（需求第 13 节第 1 行）。

找不到 spec-guard、仓库没启用、读不出时，如实说明是哪种情况，不当成「没有进度」。

## 范围

**范围内**

- 按本机安装记录找到 `map_view.py`。
- 调用它：参数列表固定，不经过 shell，带超时。
- 区分 8 种结果，各给一句中文原因：
  - `ok` 成功；
  - `not-installed` 没装 spec-guard 或找不到脚本；
  - `bad-args` 参数或路径错误，对应退出码 2；
  - `no-map` 没有能力图，对应退出码 3；
  - `unreadable` 能力图或模块文件读不出，对应退出码 4；
  - `timeout` 超时；
  - `bad-output` 输出不是约定的 JSON；
  - `schema-mismatch` 版本号不是 1。
- 把 JSON 解析成固定结构。不认识的字段忽略；0.62 的输出缺少停滞字段时，这几项记为 `None`。

**范围外**

- 判断卡住、进度变慢、悄悄停下：归 line-health。
- 记录已勾数快照、和上次比较：归 patrol 与 line-health（需求第 7 节第 3 条）。
- 显示、两种审查分列、外部等待备注：归 map-view。
- 改动 spec-guard 的任何文件或状态。
- Codex 侧查找 spec-guard（`codex plugin list`）：第一版收件枢纽只在 Claude 桌面版运行，只读 Claude 的安装记录（需求假设第 4 条）。

## 关键决策与取舍（请重点审）

1. **按安装记录找脚本，不写死带版本号的路径**（需求第 7 节第 5 条）。
   - 安装记录在 `~/.claude/plugins/installed_plugins.json`，从里面键名以 `spec-guard@` 开头的条目取 `installPath`。
   - 同时有用户级和项目级安装时，先用 `projectPath` 等于这条线仓库的那个项目级安装，否则用用户级安装。
   - `installPath/hooks/map_view.py` 不存在，就算 `not-installed`。
   - 记录文件的位置可以用环境变量 `DECISION_INBOX_PLUGINS_FILE` 改，测试用。
2. **用 `subprocess` 调用，参数列表固定**：`[当前 Python 解释器, "-B", map_view.py, "--project", 仓库路径, "--json"]`，不经过 shell，超时 15 秒。
   - 仓库路径来自 group-store 名册里开发线的 `repo` 字段（必须是绝对路径），调用前先确认它是一个存在的目录。
   - 这是本插件第一个启动子进程的模块。relay-reader 有「不调用子进程」的约束，本模块没有。
3. **按退出码如实分类，不当成「没有进度」**（需求第 7 节第 5 条）：
   - 0：`ok`；
   - 2：`bad-args`，原因取 stderr；
   - 3：`no-map`，显示为「无能力图」；
   - 4：`unreadable`，原因取 JSON 的 `detail`；
   - 其他退出码：`bad-output`，附上 stderr 的前 200 个字。
4. **`schemaVersion` 不是 1 时拒绝解析**，结果为 `schema-mismatch`。spec-guard 承诺「版本 1 内只增不改」，所以版本号变了就说明契约变了，要先人工核对再接。
5. **原样保留停滞相关的原始字段，不在本模块判断**：`lastTickAt`、`firstTickAt`、`tickCommits`、`suspendedAt`、`history`。spec-guard 的约定是只给原始时间，由我们自己算门槛；第 7 节第 3 条要求的「git 历史不完整时不做时间类判断」，也由 line-health 来做。
6. **时间保持原值**（spec-guard 用 git 的 `%cI` 格式，带时区），比较先后时一律转成绝对时间，这件事在下游做。

## 接口约定

```python
from decision_inbox import specguard

script = specguard.locate(project="/Users/x/shop-fe")   # Located(path=..., version="0.63.0") 或 Missing(reason="...")
result = specguard.read_line(project="/Users/x/shop-fe", timeout=15)

result.status      # ok | not-installed | bad-args | no-map | unreadable | timeout | bad-output | schema-mismatch
result.reason      # 中文一句话；ok 时为 None
result.exit_code   # 子进程退出码；没调用或超时为 None
result.map         # status == "ok" 时为 LineMap，否则为 None
```

```python
@dataclass(frozen=True)
class LineMap:
    project_root: str
    title: str | None
    generated_at: str
    generator_version: str | None
    stage: str                    # NEEDS_SPEC | NEEDS_PLAN | BUILDING | MODULE_DONE | DONE
    active_module: str | None
    next_gate: str | None
    history: str                  # complete | shallow | unavailable；0.62 的输出没有这个字段，记为 unavailable
    totals: dict[str, int]
    head_sha: str | None
    head_branch: str | None
    unmerged_count: int | None    # None 表示判断不了，与 0 区分
    unmerged_base: str | None
    unpushed_count: int | None    # None 表示判断不了（例如分支没有上游）
    unpushed_upstream: str | None
    bottlenecks: tuple[Bottleneck, ...]        # (id, suspended_reason, blocks)
    awaiting_review: tuple[AwaitingReview, ...] # (id, kind, review)
    modules: tuple[ModuleFact, ...]            # 按 position 排序

@dataclass(frozen=True)
class ModuleFact:
    id: str
    position: int
    responsibility: str
    depends_on: tuple[str, ...]
    status: str                   # done | in_progress | suspended | blocked | ready | not_ready
    step: str | None              # spec | plan | build；只有 in_progress 才有
    progress_done: int
    progress_total: int
    suspended_reason: str | None
    blocked_on: tuple[str, ...]
    missing_deps: tuple[str, ...]
    blocks: tuple[str, ...]
    review_spec: str              # none | pending | approved | revised | invalid
    review_plan: str              # none | pending | approved | invalid
    last_tick_at: str | None
    first_tick_at: str | None
    tick_commits: int | None      # None：history 为 unavailable，或 0.62 的输出
    suspended_at: str | None
```

## 依赖

- 本插件模块：无。调用方传入仓库路径，名册由调用方去读。
- 外部组件：spec-guard ≥ 0.62.0 的 `hooks/map_view.py`，0.63.0 起才有停滞字段。契约是 spec-guard 仓库 `spec/map-view.md`、`spec/stall-signals.md`，均已发布，不缺接口。

## 项目结构

```text
decision_inbox/specguard.py      本模块
tests/test_specguard.py          单元测试
tests/fixtures/specguard/        假的安装记录、假的 map_view.py 脚本与 JSON 样例
```

## 命令

```bash
python3 -m unittest discover -s tests -v
```

## 代码风格

沿用前面的模块：只用标准库，代码和注释用英文，给用户看的文字用中文，结果用 `@dataclass(frozen=True)`。

## 测试策略

- 用临时目录做假的安装记录和假的 `map_view.py`。假脚本按参数输出指定的 JSON、退出码和 stderr，或者故意睡过超时，覆盖全部 8 种结果。
- JSON 样例取自本机实跑 spec-guard 0.63.0 的输出，模块表里只保留需要的几项。另加一份去掉停滞字段的样例，模拟 0.62 的输出。
- 另有一个集成测试：本机装了 spec-guard 时，真实调用它读本仓库，断言 `status == "ok"`、`generator_version` 不为空；没装时跳过。

## 边界

- **始终**：只读；参数列表固定、不经过 shell；带超时；如实区分 8 种结果。
- **先问**：接受 `schemaVersion` 不是 1 的输出；为 Codex 侧加查找逻辑；缓存结果。
- **绝不**：自己解析能力图或 todo；修改任何仓库或 spec-guard 的文件；把读不出当成「没有进度」。

## 验收标准

1. 安装记录里只有用户级的 spec-guard：`locate` 返回它的 `installPath/hooks/map_view.py` 和版本。同时有用户级和 `projectPath` 等于这条线仓库的项目级安装：返回项目级的那个。
2. 安装记录文件不存在、没有 spec-guard 条目、`map_view.py` 不存在：分别返回 `not-installed`，原因各不相同；不启动子进程。
3. 假脚本退出码 0、输出合法 JSON：`ok`；`LineMap` 的各字段与 JSON 一致；`modules` 按 `position` 排序；不认识的字段被忽略。
4. 退出码 2、3、4：分别得到 `bad-args`（原因取 stderr）、`no-map`（原因为「无能力图」）、`unreadable`（原因取 JSON 的 `detail`）。退出码 1：得到 `bad-output`，附 stderr 前 200 字。
5. 输出不是 JSON、`schemaVersion` 为 2：分别得到 `bad-output`、`schema-mismatch`。
6. 假脚本睡过超时：得到 `timeout`，`exit_code` 为 None。
7. 0.62 形状的输出（没有 `history` 和停滞字段）：`history` 为 `unavailable`；`last_tick_at`、`first_tick_at`、`tick_commits`、`suspended_at` 为 None；其余照常。
8. `unmerged` 或 `unpushed` 为 null：对应的数和名称都是 None，不记为 0。
9. 仓库路径不是存在的目录、或者不是绝对路径：不启动子进程，直接 `bad-args`。
10. 集成：本机装了 spec-guard 时，读本仓库得到 `ok`，`generator_version` 与安装记录里的版本一致；没装时这条测试跳过。
11. 测试中扫描断言：`specguard.py` 里调用子进程时不出现 `shell=True`。

## 假设

1. 第一版只在 Claude 桌面版的收件枢纽里运行，Claude 的安装记录能找到 spec-guard。各线的 Codex 会话不需要调用本模块。
2. 名册里每条开发线的 `repo` 就是它的仓库根目录，也就是 spec-guard 的项目根。

## 未决问题

无。顶层 `history` 的含义已经由本机实测确认：取值 `complete`，表示 git 历史是否完整，不是挂起历史。

## 文档建议

无。
