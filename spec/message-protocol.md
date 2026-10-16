<!-- spec-guard: review approved 96ba1b43a6dd -->
# Spec: message-protocol

> 能力图模块 `message-protocol`。需求来源：`docs/requirements-record.md` 第 4.1～4.4、4.7 节，第 3.3.2、3.3.5 节，第 6.3 节，第 12 节第 6 项。

## 目标

各会话之间的消息是普通文本，按约定块里的格式手写。本模块把这些文本解析成结构化结果，并按约定校验：合格，或者缺了哪个必填字段、哪里写错了。还负责生成收件枢纽发出的【用户答复】文本。

使用方：
- decision-queue：收单时据此退回不合格的事项、转达答复；
- wait-tickets：登记等待、按「结束」写法关单；
- review-registry：读审查状态行；
- stop-hook 和 line-health：识别阻塞报告。

本模块只处理文本，不读写状态文件，不调用 agent-relay，也不决定退不退回（那是 decision-queue 的事）。

## 已定事项

1. **第 12 节第 6 项（用户 2026-10-16 定）**：字段的必填和选填按下面「字段表」执行。缺了必填字段算「问题」，调用方据此退回；缺了选填字段只算「提示」，供显示时标出，不退回。
2. **多线事项**写了「适用会话」，就必须写「各线范围」，而且每个适用会话恰好对应一条（需求第 2 节假设第 8 条，第 4.4 节）。
3. **架构审查状态行**从不因为缺失或写法不对而判为「问题」。本模块只解析出它是哪一种，显示规则（例如「⚠ 未标审查」）归 review-registry（需求第 4.3 节）。

## 范围

**范围内**

- 识别消息类型：【等待用户】、【用户答复】、【等待其他会话】、【已恢复】、【撤回】，以及附在【等待用户】上的【取代 #N】、【与 #N 并行】。
- 解析消息开头的「结束：…」「回复：#N」两种行。
- 按字段表解析字段，并校验必填项。
- 解析选项：字母、方案、「选了会怎样」、哪个是推荐，以及「你该回」。
- 解析多线事项的「适用会话」和「各线范围」，并校验两者一一对应。
- 解析「架构审查：…」行，得到五种写法之一，或者「认不出」。
- 生成【用户答复】文本，包括多线事项给各适用会话的那一版。

**范围外**

- 退回、转达、排序、编号分配（decision-queue）；等待单与关单（wait-tickets）；审查者登记与显示（review-registry）。
- 负责人每轮回复第一行的模式标签【讨论】【审查结论】等：这些写在负责人自己的会话里，不是发往收件枢纽的消息，归 onboarding 的约定块。
- 防伪造【用户答复】（第 12 节第 12 项）：等写 decision-queue 时再问。
- 第二版的统计。

## 关键决策与取舍（请重点审）

1. **阻塞报告不另设消息类型。** 开发线报「阻塞：等谁交付」，用的就是【等待其他会话】：在等谁、等什么。line-health 把它显示为「阻塞：等某某交付」。不新增标签，约定块里少一种写法，等待单也能直接复用。
2. **【取代 #N】和【与 #N 并行】附在新的【等待用户】上**，是同一条消息开头多出来的一行标签；**【撤回】单独成一条消息**，正文写「事项：#N」。需求第 4.1 节只列了这三种标记，没说怎么写，这是本 Spec 定下的写法。
3. **开头的标签行、「结束：」行、「回复：」行顺序不限**，只要都在第一个字段之前。需求里有两处都写了「第一行」：第 4.1 节说「结束：」写在第一行，第 4.7 节说「回复：」写在第一行。两者同时出现时不可能都在第一行，所以放宽成「都在字段之前」。
4. **字段写法宽松，判定从严。**
   - 宽松：字段名后的冒号全角、半角都认；字段值可以跨多行，直到下一个已知字段名为止；选项字母后面跟 `：` `:` `.` `、` `)` 都认。
   - 从严：必填字段找不到，或者值为空，就是问题；「是否完全停住」只认「是」或「否」，写别的也算问题。不靠猜来补全。
5. **问题和提示用固定代码表达**，例如 `missing-field:要你决定`、`scope-missing:API`，另附一句中文说明。调用方按代码分支，不解析中文。代码集合写进本 Spec，只增不改。
6. **【用户答复】由本模块生成，不由调用方拼字符串。** 用户原话一字不改地放进去；多线事项给每个适用会话一版，各自附上「适用于你的范围」（从「各线范围」原样摘出）和原事项全文（需求第 4.4 节第 4 条）。

## 字段表（第 12 节第 6 项）

**【等待用户】**

| 字段 | 必填 | 缺了时 |
|---|---|---|
| 「结束：#N」或「结束：无」 | 是 | 问题 `missing-end` |
| 来自 | 是 | 问题 `missing-field:来自` |
| 要你决定 | 是 | 问题 `missing-field:要你决定` |
| 选项与我的建议（至少一个带字母的选项） | 是 | 问题 `missing-options` |
| 是否完全停住（是／否） | 是 | 问题 `missing-field:是否完全停住`，或 `bad-stop-flag` |
| 每个选项的「选了会怎样」 | 否 | 提示 `no-consequence:B` |
| 推荐、你该回 | 否 | 提示 `no-recommendation` |
| 项目、要点 | 否 | 不提示 |
| 架构审查：… | 不判为问题 | 解析结果为 `absent` 或 `unrecognized` |
| 适用会话 | 否；写了就触发下一行的校验 | — |
| 各线范围 | 写了「适用会话」时必填，每个适用会话恰好一条 | 问题 `scope-missing:<会话>`，范围里出现不在「适用会话」中的会话是 `scope-unknown:<会话>`，整节缺失是 `missing-field:各线范围` |

**其他消息**

| 消息 | 必填（缺了就是问题） | 选填 |
|---|---|---|
| 【用户答复】 | 事项（#N）、用户原话、答复时间；多线事项另加「适用于你的范围」「原事项全文」 | — |
| 【等待其他会话】 | 「结束：…」、在等谁、等什么 | — |
| 【已恢复】 | 「结束：#N」（可以列多个），或「结束：无编号（原因）」 | — |
| 【撤回】 | 事项（#N） | 原因 |
| 【取代 #N】／【与 #N 并行】 | 标签里的 #N | — |

## 接口约定

```python
from decision_inbox import protocol

msg = protocol.parse(text)
msg.kind            # "wait-user" | "user-reply" | "wait-session" | "resumed" | "withdraw" | "unknown"
msg.markers         # ("supersede", 12) / ("parallel", 12) 的元组
msg.ends            # EndMark(ids=(12, 15), none=False, unnumbered_reason=None)
msg.reply_to        # 「回复：#N」里的 N，或 None
msg.fields          # {"来自": "前端", "要你决定": "...", ...}，原样保留字段值
msg.options         # (Option(letter="A", text="...", consequence="..." | None), ...)
msg.recommended     # "A" | None
msg.suggested_reply # 「你该回」的原文 | None
msg.fully_stopped   # True | False | None
msg.lines_in_scope  # ("前端", "API")，没有就是 ()
msg.scopes          # {"前端": "...", "API": "..."}
msg.review          # ReviewLine(status="passed"|"passed-with-advice"|"in-progress"|"not-applicable"|"waived"|"absent"|"unrecognized", advice_count=N|None, ref="R-3"|None, raw="...")
msg.problems        # (Issue(code="missing-field:要你决定", text="缺少「要你决定」"), ...)
msg.hints           # (Issue(code="no-consequence:B", text="..."), ...)
msg.ok              # 没有 problems 时为 True

text = protocol.format_user_reply(item=12, original="12 B", answered_at="2026-10-16 14:05",
                                  option_text="B：...")              # 普通事项
texts = protocol.format_multiline_replies(item=12, sender="前端负责人", original="...",
                                          answered_at="...", wait_user_text=原事项全文)
                                          # {"前端": "...", "API": "..."}，每个适用会话一版
```

- 认不出类型的消息 `kind="unknown"`，`problems` 里给 `unknown-kind`；不会抛异常。
- 审查状态行与五种写法的对应关系按需求第 4.3 节的表；冒号后的内容不是这五种之一，就是 `unrecognized`，`raw` 保留原文，供 review-registry 原样摘出。

## 依赖

无外部依赖：只做文本处理，只用 Python 标准库，不调用 agent-relay 或 spec-guard。

## 项目结构

```text
decision_inbox/protocol.py           本模块
tests/test_protocol.py               单元测试
tests/fixtures/protocol/*.txt        消息样例（按需求第 4、6 节的写法构造）
```

## 命令

```bash
python3 -m unittest discover -s tests -v
```

## 代码风格

沿用前两个模块：只用标准库，代码和注释用英文，给用户看的说明用中文，结果用 `@dataclass(frozen=True)`。

## 测试策略

- 每种消息至少一个合格样例、每个必填字段至少一个缺失样例；问题代码逐个断言。
- 生成【用户答复】后再用 `parse` 解析回来，往返一致（用户原话逐字相同）。
- 样例文件用中文原文，覆盖全角和半角冒号、跨行字段值、各种选项字母写法。

## 边界

- **始终**：用户原话一字不改；认不出的内容保留原文；不靠猜来补全字段。
- **先问**：新增消息类型或字段；改变某个字段是否必填；改问题代码。
- **绝不**：改写、合并或补全选项；判断审查该不该做；在本模块里决定退回。

## 验收标准

1. 一条完整的【等待用户】（含三个选项、推荐 A、你该回、完全停住「是」）：`kind="wait-user"`，`ok` 为真，选项、推荐、`suggested_reply`、`fully_stopped` 都与原文一致。
2. 分别删去「来自」「要你决定」「选项」「是否完全停住」「结束」：各自得到对应问题代码，`ok` 为假；「是否完全停住：大概」得到 `bad-stop-flag`。
3. 选项 B 没写「选了会怎样」、全文没有推荐：`ok` 仍为真，`hints` 含 `no-consequence:B` 与 `no-recommendation`。
4. 多线事项：写了「适用会话：前端、API」，「各线范围」只有前端，得到 `scope-missing:API`；多出一条「后台」，得到 `scope-unknown:后台`；完全没写「各线范围」，得到 `missing-field:各线范围`。两条都写齐时 `ok` 为真，`scopes` 原样保留每条范围。
5. 审查状态行：五种写法分别解析为对应状态，带括号里的审查编号；「通过，附建议2条（…）」的 `advice_count` 为 2；「架构审查：已看过」为 `unrecognized`，`raw` 保留原文；没有这一行为 `absent`。所有情况都不产生问题。
6. 开头三行「回复：#40」「【等待其他会话】」「结束：#31」顺序打乱后结果相同；字段之后再出现「结束：」不算开头的结束行。
7. 【已恢复】的「结束：#12、#15」解析成 `ids=(12, 15)`；「结束：无编号（对方没给编号）」解析成 `unnumbered_reason`；缺结束行得到 `missing-end`。
8. 【等待用户】开头带【取代 #8】：`markers=(("supersede", 8),)`；【撤回】单独一条、正文「事项：#8」：`kind="withdraw"`。
9. `format_user_reply` 的结果用 `parse` 解析：`kind="user-reply"`，`ok` 为真，用户原话逐字相同（含换行和标点）。
10. `format_multiline_replies` 为每个适用会话生成一版：各版「适用于你的范围」等于原事项里写给它的那一条，并附原事项全文。
11. 全角冒号和半角冒号、跨多行的字段值、选项字母写成 `A：` `A.` `A、` `A)`，都能正确解析。
12. 认不出类型的文本：`kind="unknown"`、`problems` 含 `unknown-kind`，不抛异常。

## 假设

1. 各会话按约定块写消息，标签用全角方括号【】、编号用 `#` 加数字。约定块的具体内容（第 12 节第 9 项）在 onboarding 定；如果到时改了写法，再回到本模块返工。
2. 样例按需求第 4、6 节的格式构造，不取实验期间的真实消息。要不要用真实消息回放来验收，是第 12 节第 13 项，还没定，不在本模块决定。

## 未决问题

无。第 12 节第 6 项已定；第 12 项（防伪造答复）留到 decision-queue 再问。

## 文档建议

无。消息格式就写在本 Spec 的「字段表」里；面向各会话的写法说明会在 onboarding 写进约定块。
