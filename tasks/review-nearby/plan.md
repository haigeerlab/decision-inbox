<!-- spec-guard: review pending -->

# Implementation Plan: review-nearby

> 依据：`spec/review-nearby.md`（用户 2026-10-19 批准）。任务清单：`tasks/review-nearby/todo.md`。分支 `claude/review-nearby-1b7fdb`。
> 契约：session-protocol v2.0 工作稿（契约仓库未提交，契约 Spec 已批准，等它的最终验收）。module-crew：0.3.0 的 `review` 字段与合批摘要格式（2026-10-19 来信定稿）。

## Overview

九个任务。先做不依赖契约发布的四个（R11、doctor、R1 显示、R8 摘要），再改钉契约 v2.0，接着做依赖契约的三个（编号前缀、待用户决定、登记回执），最后做解耦回归和文档版本。每个任务先写失败的测试，再改代码。冻结 0.0.21（标签、固定副本、改安装）不在本 Plan 内，合并后另请用户批准。

## 和 Spec 对照：契约定稿带来的写法调整（不改行为）

1. 写法提示：契约定为「文字由收件枢纽自定，不进解析结果的 hints」，没有提示代码。Spec 第 4 条「提示代码按契约定稿」就按这个做：回执的「写法提示」直接用 rehearsal2-fixes 那四条中文。
2. 编号前缀：契约写明 C、R、D 编号前后不能紧挨英文字母或数字（所以 `4c5d6e7` 这类提交号不算）。回复解读照这个规则认前缀编号。
3. 【用户答复】「事项」以 C 编号开头时，`item` 为 null，另有 `localItem`。收件枢纽本来就不处理收到的【用户答复】，只是解析要跟契约一致。
4. 【审查结论】新增：「有须修改项N条」带条数，「须修改」「待用户决定」字段，`change-count-mismatch`、`change-count-missing`、`bad-decision-item`、`duplicate-decision`。收件枢纽解析【审查结论】，所以这些都要跟上。数轮次的逻辑不变（Spec 第 5 条）。
5. 【登记回执】的「取代」在契约里只有一个号。一次取代多项时怎么写，已于 2026-10-19 问契约负责人（建议改成列表）。Task 7 按回复实现；如果答复改了行为，回来改 Spec 并复审。

## Architecture Decisions

- **Task 1 R11**（`onboard.join`）：`--confirm` 写入后，往 `out.lines` 末尾追加「已写入：名册（<短名>，<角色>）」。登记了审查者时再加「审查者：<名字>（节点 spec、plan…）已重新登记」。规则文件没变化的「（没有变化）」照旧。预览（不带 confirm）不加。
- **Task 2 O-doctor-none**（`doctor._versions` 一带）：`claude` 为空并且 `codex_versions` 为空时，返回 `Check(name, "problem", INSTALL_SOURCE, "两边都没装 decision-inbox", 处理办法)`。处理办法写 Claude 的 `/plugin install` 和 Codex 的 `codex plugin add`。只装一边的分支不动。
- **Task 3 R1**（`crew.py`、`health.py`）：
  - `Module` 加 `review: tuple[str, int] | None`。`_parse` 读选填的 `review`：不存在或为 null 时记 None；是对象并且 state ∈ {reviewing, rework}、round 是非负整数时记下；其他形状一律当 None，不报错（选填字段宽容，避免 module-crew 小改就让整条线变「未知」）。
  - `health` 拼模块词：rework → 「返工中（审查第 N 轮）」；reviewing → round 为 0 写「审查中」，大于 0 写「审查中（第 N+1 轮）」。放在 stage 词的位置，取代「写 Spec／Plan」这类阶段词，忙闲词照旧。
  - 「有须修改项」的【审查结论】不产生事项：给 `hub.receive` 加一条测试，断言收下后 `items.pending` 为空、只多一条审查轮次。
- **Task 4 R8**（`view._item_card`）：
  - 判定「合批」：`decide` 里有两个以上「#数字」或「C数字」，或者事项带 `decisions`。
  - 合批卡片：「要你决定」只显示首行；接着显示「要点」的第一段（到第一个空行为止，最多 5 行），超出时写「…（共 N 行，回『{no} 详情』看全文）」；要点没有空行时，取前 5 行，规则相同。然后是选项、Dn（Task 6）和复制块。
  - 单项卡片逐字不变，用现有卡片测试加一份快照对比来保证。
  - 事项记录里本来没存要点，`_record` 加存 `brief`（要点原文）。旧记录没有这个字段时，卡片照旧显示。
- **Task 5 契约 v2.0**（`protocol.py`、`tests/test_contract.py`）：
  - 复制契约 v2.0 的 `fixtures/` 到 `tests/fixtures/session-protocol/v2.0/`，删掉 v1.7 副本，`CONTRACT_VERSION = "2.0"`，核对 SHA256SUMS。
  - 解析新增：类型 `hub-receipt`（字段原消息、事项、状态，选填取代、写法提示；`receipt` 键）；【等待用户】与【审查结论】的「待用户决定」（`decisions`，各条 id、question、options、lean、leanReason，以及两个问题代码）；【审查结论】「有须修改项N条」与「须修改」（`changeCount`、`changes`，以及两个代码）；【用户答复】的 C 编号事项（`item` null，`localItem`）。
  - 生成新增：`format_hub_receipt(original, item, supersedes, notes)`。契约没有回执的生成样例，测试改为「生成后再解析，结果和输入一致」。
  - `to_contract` 只在期望结果里有这些键时比较（契约规定的比较方式）。`NOT_PARSED` 照旧跳过 review-request、shared-change-request、coordination-notice、owner-handoff、`user-reply/relay-*`，跳过数写进测试。
  - 问题代码的排列顺序照契约第 7 节的 v2.0 附注。
- **Task 6 R6 编号前缀**（`items._segments`、`interpret_reply`）：
  - 新增 `_PREFIXED_RE`：`(?<![A-Za-z0-9])[CD]\d+(?![A-Za-z0-9])|(?<![A-Za-z0-9])R-?\d+(?![A-Za-z0-9])`。只用来认出「这一段不是在答别的事项」，原话不动。
  - `_SEGMENT_RE` 本来只认开头不带字母的数字，保留不改。新增测试钉住：C15、#C15、R-3、D1 开头的段不会被当成事项号。
  - `_LETTER_RE` 改成 `^([A-Z])(?:[\s，；,;、：:].*)?$`：字母后面跟标点也认。字母后面直接跟中文（如「A全部批准」）仍然不认，和现在一样。
  - 拆段时，以 C 或 R 前缀开头的片段并进前一个事项段，不拆成新段（例如「21 B，C15 退回，C16 批准」整句归 #21）。以 D 开头的片段同样并进前一段（Task 7 解读）。
- **Task 7 R2 待用户决定**（`items`、`view`）：
  - `_record` 存 `decisions`（来自契约解析结果）。
  - `interpret_reply`：对带 `decisions` 的事项，在它那一段里用 `D(\d+)\s*(?:[：:]|选)?\s*([A-Z])` 找答案（受前缀边界约束）。缺的、多出来不存在的、字母不在该 Dn 选项里的、同一 Dn 两个不同字母的，都返回 `ReplyParse(question=...)`，不产生 Answer。追问文字列出缺的 Dn、问题和选项，再给一句完整示例（主选项取推荐字母，各 Dn 取审查倾向，只当写法示例，不当默认值）。
  - 主选项也必须答：只写了 Dn、没写主字母时同样追问。
  - `Answer` 加 `decisions: tuple[tuple[str, str], ...]`，记进 `answers` 历史和事件；转发正文不变，仍是用户原话一字不改。
  - 卡片在选项后面逐条列「D1：问题」「  A. …　B. …」「  审查倾向：B（理由）」。复制块：`suggestedReply` 写了 Dn 时照原文给；没写时只给主选项，并在下面注明「还要答 D1、D2」。
  - 一次答完（`_combined`）跳过带 Dn 的事项，并注明「#21 带待用户决定，要单独回」。
- **Task 8 R10 登记回执**（`items.receive`、`hub._dispatch`）：
  - `ReceiveResult` 加 `superseded: tuple[int, ...]`（显式和默认取代合起来）。`_receive_wait_user` 已经算出这两类，直接带出来。
  - `hub._dispatch` 遇到 wait-user 收下、并且发件人不是旧格式会话（`store.legacy_relays`）时，生成回执正文：原消息 `m.id`、事项、状态「已登记」、取代、写法提示（`items.writing_notes` 的文字，加上自动取代那条「确实要两项都答，请写【与 #旧 并行】重发」）。
  - `_queue` 增加一种 kind「receipt」，`replyTo` 为 None。send view 加 `wake: false`，让收件枢纽发送时照着设置；收件枢纽约定块里发送步骤的写法同步补一句「wake 照 sends 里的值」。
  - 回执之外的发件队列行为不变。退回、【撤回】、【等待其他会话】不发回执。
  - 主视图的写法提示保留（Spec）。
- **Task 9 解耦与文档版本**：
  - 解耦：用现有端到端测试（普通开发线 + 负责人，不配 module-crew）跑一遍，断言事项、答复转发和 0.0.20 一致，唯一的区别是 sends 里多了 receipt。为此加一条专门的测试，对比 sends 的种类。
  - 约定块：开发线约定块加一句「收件枢纽会回【登记回执】，【取代】【撤回】用回执里的事项号」，再加「待用户决定」的写法（只给一个短例）；收件枢纽约定块加回执发送的 wake 设置。约定块文字改动会让已接入会话的 join 出现差异，README 的升级步骤写明要重新 join。
  - README：Dn 的答法、回执、编号前缀、0.0.21 的升级步骤；能力图外部依赖表的契约一行改成 v2.0（附提交号），module-crew 一行加 `review` 字段。
  - 两份 `plugin.json` 改成 0.0.21。

## Dependency Graph

```
Task 1 R11 ─┐
Task 2 doctor ─┤（互不依赖，先做）
Task 3 R1 ───┤
Task 4 R8 ───┘
Task 5 契约 v2.0 ── 要等契约发布提交
   ├── Task 6 R6 ── Task 7 R2（拆段规则先定）
   └── Task 8 R10
Task 9 解耦、文档、版本 ── 依赖全部
```

## Task List

### Phase 1：不依赖契约发布

- **Task 1 重新 join 回执**（Spec 验收 7）。文件：`onboard.py`、`tests/test_onboard.py`。验证：确认输出有「已写入：名册…」，有审查者时有「审查者…已重新登记」；预览没有；内容不变时仍写「（没有变化）」。
- **Task 2 doctor 两边都没装**（验收 8）。文件：`doctor.py`、`tests/test_doctor.py`。验证：两边都没装报 problem；只装一边、两边同版本、两边不同版本的现有用例结果不变。
- **Task 3 返工轮次显示**（验收 5）。文件：`crew.py`、`health.py`、`tests/test_crew.py`、`tests/test_health.py`、`tests/test_hub.py`。验证：rework、reviewing（round 0 和 >0）、null、缺字段、形状不对五种；有须修改项的【审查结论】不产生事项。
- **Task 4 合批摘要卡片**（验收 6）。文件：`items.py`（存 brief）、`view.py`、`tests/test_view.py`。验证：用 module-crew 新格式的样例，卡片显示摘要段并提示「回『N 详情』」；bodies/8.txt（没有空行）取前 5 行并提示；单项卡片的快照不变；「N 详情」照旧显示全文。

### Checkpoint A（report）：Phase 1 完成

全部测试通过，记入 todo 后继续。契约还没发布时停在这里等，不往下做。

### Phase 2：改钉契约 v2.0（等契约发布提交）

- **Task 5 契约 v2.0**（验收 1）。文件：`protocol.py`、`tests/test_contract.py`、`tests/fixtures/session-protocol/v2.0/`（删 v1.7）、能力图外部依赖表。验证：SHA256SUMS 核对通过；解析样例全部通过；回执生成后再解析一致；跳过的类型和数量写在测试里；原有测试全部通过。

### Phase 3：依赖契约

- **Task 6 编号前缀**（验收 3）。文件：`items.py`、`tests/test_items.py`。验证：「21 B，C15 退回」→ #21 选 B、原话整句；C15、#C15、R-3、D1、`4c5d6e7` 开头的段都不是事项号；「12 B」「#12 B」「12 B，13 A」「A」（只有一项待答）四种老写法结果不变。
- **Task 7 待用户决定**（验收 2）。文件：`items.py`、`view.py`、`tests/test_items.py`、`tests/test_view.py`。验证：「21 A」追问 D1、D2；「21 A；D1 B」追问 D2；「21 A；D1 B；D2 A」转发原话；「21 A；D1 Z」追问；「21 A；D1 B；D1 A」追问；「D1 B；D2 A」（没答主选项）追问；卡片逐条列 Dn 和审查倾向；一次答完跳过带 Dn 的事项。
- **Task 8 登记回执**（验收 4）。文件：`items.py`、`hub.py`、`onboard.py`（收件枢纽约定块的 wake 一句）、`tests/test_hub.py`。验证：收下后 sends 里有 kind receipt、replyTo None、wake false，正文解析为合格的【登记回执】；显式取代、默认取代写「取代」；bodies/8.txt 的回执里写法提示列四条；旧格式会话、被退回的、【撤回】都没有回执。

### Checkpoint B（report）：Phase 3 完成

全部测试通过，记入 todo 后继续。

- **Task 9 解耦、约定块、文档、版本**（验收 9、10）。文件：`onboard.py`（约定块）、`README.md`、`spec/CAPABILITY-MAP.md`（外部依赖表）、两份 `plugin.json`、`tests/test_hub.py`（解耦对比）、`tests/test_onboard.py`（约定块）。验证：解耦测试只多了 receipt；`python3 -m unittest discover -s tests` 全部通过；两份清单都是 0.0.21。

### Checkpoint C（gate）：模块最终验收

列出实际改动的文件（取自版本库）、每条验收标准的证据、测试数；Spec 验收 11 的实测放到冻结之后，开始前另问你。然后开 PR，由你合并。

## 影响面

- 收件枢纽的收件（多一条回执）、回复解读（Dn、前缀、字母后跟标点）、主视图卡片（合批摘要、Dn）。
- 约定块文字变化：开发线和收件枢纽都要重新 join，才能拿到新约定。
- 契约主版本变化：一致性测试整套换成 v2.0。

## 风险与对策

| 风险 | 影响 | 对策 |
|---|---|---|
| 契约发布晚于预期，或定稿和工作稿不一样 | Phase 2、3 等待或返工 | Phase 1 不依赖契约；定稿只改写法时在本 Plan 里对齐，改了行为时回去改 Spec 并复审 |
| 字母后跟标点也认，改变了某些老回复的记录 | 老回复多记一个字母 | 原话照旧整句转发，只影响记录；用四种老写法的回归测试钉住 |
| 回执 wake: false 依赖收件枢纽照着 sends 发送 | 回执可能把对方叫醒 | 约定块写明，sends 里明确给出 wake；实测时核对 agent-relay 的投递记录 |
| 带 Dn 的事项追问太多，用户觉得烦 | 体验 | 追问里给出完整示例，用户复制改一下就能用 |
| 合批判定靠「两个以上编号或带 Dn」，可能误判普通事项 | 普通事项被收成摘要 | 判定只在有 C 编号或多个 # 号时触发；单项快照测试保证普通卡片不变 |

## Open Questions

1. 回执「取代」一次写多项的写法（已问契约负责人）。
2. 契约 v2.0 的发布提交号（等契约负责人通知）。
