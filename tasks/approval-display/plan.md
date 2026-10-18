<!-- spec-guard: review approved -->

# Implementation Plan: approval-display

> 依据：`spec/approval-display.md`（用户 2026-10-19 批准）。任务清单：`tasks/approval-display/todo.md`。分支 `claude/approval-display`（叠在 #18 上）。
> 契约：session-protocol v2.1（c251e94，已提交）。module-crew：「验收标准与证据」一节与一项一个模块，2026-10-19 已发配合要求，未答复。

## Overview

八个任务：契约 v2.1 → 取原文 → 记录与背景 → 审批项展示 → 主视图排布与「看 N」 → 多模块分节 → R17 对照表 → R15、README 与解耦。每个任务先写失败的测试，再改代码。本模块不升版本号，版本在 glossary-rename、stall-and-patrol 做完后统一定，一起冻结。

## 和 Spec 对照：契约定稿带来的写法调整（不改行为）

1. 解析键名叫 `artifacts`（每条有 module、path、commit、previousCommit）和 `originals`（submission、conclusion 两组，每组每条有 module、path、fingerprint）。
2. 「产物」「交审原文」「审查原文」行写错时，报问题代码 `bad-artifact-line`、`bad-file-line`。按现有规则，整条【等待用户】退回给发件会话，和别的必填问题一样。
3. 「产物」行的 ＠ 全角、半角都认；提交号写 7～40 位小写十六进制，写成分支名（如 `main`）算不合格。

## Architecture Decisions

- **Task 1 契约 v2.1**（`protocol.py`、`tests/test_contract.py`）：
  - 复制 c251e94 的 `fixtures/` 到 `v2.1/`，删掉 `v2.0.1/`，`CONTRACT_VERSION = "2.1"`。
  - FIELDS 里，wait-user 在「要点」后面加「产物」「交审原文」「审查原文」。
  - 新增 `Artifact`、`OriginalRef` 两个数据类，`Message` 加 `artifacts`、`originals`。
  - 文件行沿用【交审】「文件」行的写法：路径 + 空格 + `sha256:` + 12～64 位小写十六进制，行首可带「- 」，可带「模块：」前缀。
  - 问题代码加进 PROBLEM_CODES，并在本 Spec 里登记（`CodeTableTest` 要求每个代码在 spec 里有记载）。
- **Task 2 取原文**（新增 `decision_inbox/sources.py`，只读）：
  - `read_artifact(path, commit, previous=None) -> Source`：
    - 用 `git -C <dirname> rev-parse --show-toplevel` 找仓库根，算出相对路径；
    - 用 `git -C <root> show <commit>:<rel>` 读全文；
    - 写了 previous 时，另取 `git -C <root> diff <previous> <commit> -- <rel>`。
  - `read_original(path, fingerprint) -> Source`：读字节，sha256 十六进制以指纹开头才算数，按 UTF-8 解码（解不出来按读不到处理）。
  - `Source` 字段：`ok`、`text`、`diff`、`reason`。reason 是中文短句：「文件不存在」「不在 git 仓库里」「提交 4c5d6e7 里没有这个文件」「指纹对不上（文件现在是 sha256:…）」「读取超时」。
  - 子进程固定 argv、不用 shell，超时 5 秒；不缓存，也不写状态目录。
- **Task 3 记录与背景**（`items.py`、新增 `decision_inbox/approval.py`）：
  - `_record` 存 `project`（「项目」字段）、`artifacts`、`originals`。
  - `approval.is_approval(it)`：有任一条 artifacts 或 originals。
  - `approval.background(g, it) -> dict`：
    - 项目：取「项目」字段，没写就用 /map 的 title；
    - 仓库：取第一条产物路径所在的仓库根；
    - 能力图：在仓库根跑 `specguard.read_line(root)`，按 position 列「模块 状态」，本模块标「← 本项」，它依赖的模块标「（依赖）」，读不到写原因；
    - 模块和节点：读交审原文（Task 2）后，用正则取「模块：」「节点：」两行。这不经过契约解析：本插件仍不解析【交审】；
    - 第几次交审：数同一 sender、同一模块、同一节点的历史事项；
    - 上次退回原因：上一项被答了非推荐选项的，取那次的原话；
    - 相关决定：同一 sender、同一模块过去已答事项的「#N（日期）你答：原话首行」，最多 5 条。
- **Task 4 审批项展示**（`view.py`）：
  - `render_approval(g, it, now) -> str`，按 Spec 的顺序分段，每段标题后标【决策收件箱补充】【原文】【对照】。
  - 原文段：取不到时整段写「原文取不到：<行> —— <原因>」。重交时先给差异，再给全文。
  - 「批准会发生什么」：用节点到固定文字的表，加上推荐选项的「选了会怎样」原话。
  - 「待你决定」沿用 review-nearby 的 `_decision_lines`。
  - 「选项与推荐」：逐个选项写「字母：文字 / 选了会怎样」，最后一行写「推荐 A：…；答复写法示例：24 A；D1 B」，纯文字，不放代码块。
- **Task 5 主视图排布与「看 N」**（`view.py`、`hub.py`）：
  - `_cards` 里的审批项按现有排序，第一项用 `render_approval` 完整展开，其余各一行：「━━ #N · 项目 · 模块 · 审 节点 · 等了 X · 回「看 N」看全文」。
  - 普通事项卡片不变。
  - `hub.reply` 新增 `^看\s*#?(\d+)$`：审批项返回 `render_approval`；普通事项返回原卡片；不存在时提示。
  - 「一次答完」跳过审批项（推荐不应一键照抄）。
- **Task 6 多模块分节**（`approval.py`、`hub.py`）：
  - artifacts 和 originals 按 module 分组，有两个以上不同模块时，原文段按模块分节。
  - 【登记回执】的写法提示加「按决定 47 应各自一项（这一项合了 alpha、beta）」。
- **Task 7 R17 对照表**（`approval.py`）：
  - 节点是 final 时：在第一条产物的仓库里，按 `spec/<模块>.md` 取产物那个提交上的 Spec，取「## 验收标准」一节里按编号开头的各条。
  - 交审原文里找「验收标准与证据」一节，按编号对行；没有对应行或写「无」的，标「⚠ 缺证据」。
  - 两者任一取不到，就写明是哪个取不到，不推断。
- **Task 8 R15、README、解耦**：
  - `onboard.py` 里开发线、审查者（owner）、跨线协调三种角色的规则加 R15 三句。约定块改了，README 升级一节写明要重新 join。
  - README 加「审批项怎么读」。
  - 解耦快照：没有新字段的事项，卡片和 0.0.21 逐字一致。

## Dependency Graph

```
Task 1 契约 ── Task 2 取原文 ── Task 3 记录与背景 ── Task 4 展示 ── Task 5 主视图与「看 N」
                                                     ├── Task 6 多模块分节
                                                     └── Task 7 R17 对照表
Task 8 R15、README、解耦 ── 依赖全部
```

## Task List

- **Task 1 契约 v2.1**（Spec 验收 1）。验证：指纹 188 行通过；解析样例全过（多出 3 份）；跳过数不变；原有测试全过。
- **Task 2 取原文**（验收 2、3）。用临时 git 仓库测：
  - 全文逐字一致，包括 150KB 的文件；
  - 上一版的差异；
  - 文件不存在、不在仓库里、提交里没有这个文件、提交不存在、指纹对不上、不是 UTF-8，各一条。
- **Task 3 记录与背景**（验收 4）。验证：
  - 用假的 /map 输出列出能力图，并标出本项和依赖；/map 读不到时写原因；
  - 从交审原文取模块和节点；
  - 第二次交审时写「第 2 次」，并带上上次的原话；
  - 相关决定最多 5 条。
- **Checkpoint A（report）**：前 3 个任务测试全过，记入 todo 后继续。
- **Task 4 审批项展示**（验收 2、5）。验证：
  - 段落顺序断言，最后一段是选项与推荐；
  - 没有 ``` 代码块；
  - 三段原文和源文件逐字一致（diff 为空）；
  - 读不到时写原因，不出现要点内容。
- **Task 5 主视图与「看 N」**（验收 6）。验证：
  - 两个审批项时，第一项展开，第二项只占一行；
  - 「看 N」展开第二项；
  - 「N 详情」照旧；
  - 「一次答完」跳过审批项。
- **Task 6 多模块分节**（验收 7）。验证：按模块分节，回执写法提示里有「按决定 47」。
- **Task 7 R17 对照表**（验收 8）。验证：
  - 三条验收标准里，有一条证据写「无」、有一条没有对应行，这两条都标「⚠ 缺证据」；
  - Spec 取不到时写明。
- **Checkpoint B（report）**：测试全过，记入 todo 后继续。
- **Task 8 R15、README、解耦**（验收 9、10）。验证：
  - 三种角色的规则都有 R15 三句；
  - 普通事项卡片的快照和 0.0.21 一致；
  - README 打包测试加关键词；
  - 全量测试通过。
- **Checkpoint C（gate）：模块最终验收**。列出改动的文件、每条验收标准的证据和测试数；用临时状态目录和临时 git 仓库实际渲染一个审批项给你看；Spec 验收 11 的实测放到冻结之后。

## 影响面

- 主视图的审批项卡片（只有带新字段的事项受影响）；
- 收件枢纽新增命令「看 N」；
- 协作规则段的文字（已接入的会话要重新 join）；
- 一致性测试整套换成 v2.1。

## 风险与对策

| 风险 | 对策 |
|---|---|
| 收件枢纽跑 `git show` 读别的仓库，会不会弹权限确认 | 走插件自己的命令（`decision-inbox view`，已在放行清单里），子进程在命令内部跑；实测时核对没有弹窗 |
| 原文很长，宿主显示被截断 | 主视图只展开一项；实测时看桌面版的表现，有问题回来定，比如另存文件加链接，但正文仍给全文 |
| 交审原文里的「模块：」「节点：」写法不统一 | 只按行首「模块：」「节点：」取，取不到写「未知」，不猜 |
| /map 很慢，拖慢主视图 | 只对展开的那一项跑一次，沿用 `read_line` 现有的超时 |
| module-crew 没写「验收标准与证据」一节 | 对照表全部标「⚠ 缺证据」，并注明交审原文里没有这一节 |

## Open Questions

1. module-crew 对「验收标准与证据」一节的写法答复（Task 7 先按我们提的写法实现，答复不同就在 Task 7 里改）。
