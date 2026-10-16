<!-- spec-guard: review approved ba6a21d75d97 -->
# Spec: stop-hook

> 能力图模块 `stop-hook`。需求来源：`docs/requirements-record.md` 第 9 节、第 13.1 节第 2 行、第 12 节第 4、5 项。
> 宿主依据：Codex 侧见需求第 9.2 节（本机实验记录）；Claude 侧见 Claude Code 官方文档 hooks 一节的 Stop 输入与 decision 控制（经 context7 查得，2026-10-16）。

## 目标

工作会话准备结束这一轮时拦一下：**有别的会话开着等待单在等它，它却要收工**，就拦下一次，把谁在等、等什么、该怎么做告诉它。让「交付了忘了通知、做不下去也不说」从靠自觉变成确定性检查。

本模块只读协作组的状态，不写任何文件，不发消息。装钩子、信任钩子归 onboarding。

## 已定事项（用户 2026-10-16 确认）

1. **第 12 节第 4 项：第一版只拦一种情况——有人在等你。**
   - 下面三种情况第一版不拦，由巡视的信号发现：
     - 用户已答复、你还没恢复；
     - 有未读消息：要靠 agent-relay 的只读命令行，它还没发布；
     - 提到在等却没报阻塞：只能靠关键词判断，会误拦。
2. **第 12 节第 4 项后半：钩子不看任务清单。** 按第 13.1 节第 2 行，停止钩子只管协作义务，不判断「还有没有已批准的任务」。所以装不装 spec-guard 都一样；「悄悄停下」由巡视的信号 3 发现。
3. **第 12 节第 5 项：Claude 桌面版在实现时实测。**
   - 规格按 Claude Code 文档写：Stop 钩子的输入带 `stop_hook_active`、`last_assistant_message`、`cwd`，输出 `{"decision": "block", "reason": "..."}`，和 Codex 的约定相同。
   - 实现时在一个临时项目里装上钩子，开一个桌面版会话，实测一次拦截和第二次放行，结果记进本规格。开会话之前先问用户。
4. **agent-relay 的只读命令行还没发布**：「有未读消息」这一条记为外部依赖，发布后再接。

## 关键决策与取舍（请重点审）

1. **一轮只拦一次**：输入里 `stop_hook_active` 为 true 时一律放行。
   - Codex 实测：第二次调用会带上这个字段。
   - Claude Code：同一个字段，另有「连续拦 8 次后强制结束」的上限；本钩子每轮最多拦 1 次，碰不到这个上限。
2. **怎么认出「我是谁」**：
   - 钩子命令带协作组名：`python3 -m decision_inbox hook stop --group <协作组>`，可选 `--session <身份名>`。
   - 给了 `--session` 就用它。没给时，用输入里的 `cwd` 匹配名册里有 `repo` 的条目：`cwd` 等于 `repo` 或在它下面，按真实路径比较。
   - 对不上，或者对上了不止一个：放行，不拦。
   - 命令要尽量稳定：Codex 改了钩子命令就要重新信任（需求第 9.2 节），所以协作组名和身份名都放在参数里，以后升级不改命令。
3. **「有人在等你」怎么判断**：开着的等待单里，被等方（「在等谁」）是本会话的短名。等用户的单不算。
4. **已经报了阻塞就放行**：本会话自己也开着等待单（在等别人），或者有「完全停住」的待答事项（在等用户）时，说明它已经按规矩报了「卡在哪」，这时收工是正当的，不拦。这一条是需求第 9.1 节「被挡住时必须报阻塞」的反面：报了就可以停。
5. **拦下时给的说明（`reason`）**，固定格式，中文：
   ```text
   【decision-inbox】收工前请先处理：有会话在等你。
   - #31 API 在等你：订单接口的 Mock 数据（已等 40 分钟）
   已经交付：发消息告诉对方，请它发【已恢复】，结束行写这张单的编号。
   还没做完：继续做；做不下去就抛【等待其他会话】或【等待用户】，说明卡在哪。
   ```
   - 等的人有几个就列几行，按单号排序；「已等」的写法和 hub-view 一致。
6. **出错一律放行**：读不出状态、协作组不存在、输入不是 JSON 时，都放行，并往 stderr 写一行原因。钩子出错不能把会话卡住。
7. **只读**：不写协作组的任何文件，也不记「拦过一次」。是否已拦过，只看宿主传入的 `stop_hook_active`。

## 范围

**范围内**

- `decision_inbox/stophook.py`：`decide(g, payload, session=None, now=...)` 返回放行或拦下及说明。
- 命令行 `python3 -m decision_inbox hook stop --group <组> [--session <身份名>]`：
  - 从 stdin 读宿主给的 JSON；
  - 拦下时往 stdout 打印 `{"decision": "block", "reason": "..."}`，放行时什么都不打印；
  - 退出码一律为 0。
- 实测 Claude 桌面版的拦截和放行，把结果记进本规格（已定事项 3）。

**范围外**

- 写钩子配置、提示 Codex 信任、升级时提示重新信任：归 onboarding。
- 用户已答复却没恢复、未读消息、提到在等却没报阻塞：第一版不拦（已定事项 1）。
- 「还有已批准的任务」：不看（已定事项 2）。
- 负责人、总协调等名册里没有 `repo` 的会话：只能靠 `--session` 认出来。onboarding 决定要不要给它们装钩子。

## 接口约定

```python
from decision_inbox import stophook

d = stophook.decide(g, payload={"cwd": "/r/fe", "stop_hook_active": False, ...}, session=None, now="...")
d.block      # True 时要拦下
d.reason     # 拦下时给宿主的说明；放行时为 None
d.note       # 放行的原因（例如「认不出本会话」），只写 stderr，供排查
```

## 依赖

- 本插件模块：group-store（名册、状态）、wait-tickets（`open_tickets`）、decision-queue（`pending`，用于关键决策 4）、hub-view（「已等」的写法）。
- 能力图里本模块原来的依赖是 message-protocol、relay-reader、wait-tickets，职责写的是三种拦截。按已定事项 1 收窄后，依赖改为 `group-store, wait-tickets, decision-queue`，职责改为「有人在等你时拦一次」，随本规格一起审。
- 外部组件：
  - Codex 与 Claude Code 的 `Stop` 钩子：Codex 已实测；Claude 桌面版在实现时实测。
  - agent-relay 只读命令行：未发布，第一版不用。

## 项目结构

```text
decision_inbox/stophook.py     本模块
decision_inbox/__main__.py     加 hook 子命令
tests/test_stophook.py         单元测试
```

## 命令

```bash
python3 -m unittest discover -s tests -v
```

## 代码风格

沿用前面的模块：只用标准库，代码和注释用英文，给用户和会话看的文字用中文。

## 测试策略

- 用 group-store 临时组构造名册、等待单和事项；输入 JSON 照 Codex 实测与 Claude Code 文档的字段构造；时间显式传入。
- 命令行用子进程跑一遍，从 stdin 喂 JSON，断言 stdout、stderr 和退出码。
- 实测（实现阶段）：在临时项目里装测试钩子，开一个 Claude 桌面版会话跑一轮，看到拦下后在同一轮继续，第二次放行。

## 边界

- **始终**：一轮最多拦一次；出错放行；只读；说明里只写单号、会话短名、「等什么」和已等多久。
- **先问**：增加拦截条件；开实测用的会话；改钩子命令的格式（会导致 Codex 要重新信任）。
- **绝不**：写协作组状态；替会话发消息；在钩子里看任务清单。

## 验收标准

1. 有人在等本会话、本会话没报阻塞：拦下，`reason` 与关键决策 5 的格式一致，多张单按单号排序。
2. `stop_hook_active` 为 true：放行。
3. 本会话自己开着等待单，或有完全停住的待答事项：放行。
4. 没人在等，或者等的是用户：放行。
5. 认出本会话：给了 `--session` 时用它；没给时 `cwd` 等于 `repo` 或在它下面能认出；对不上、对上多个时放行，并在 `note` 里写原因。
6. 出错放行：协作组不存在、输入不是 JSON、状态读不出时，退出码 0，stdout 为空，stderr 有一行原因。
7. 命令行：拦下时 stdout 是一个 JSON 对象，含 `decision` 和 `reason`；放行时 stdout 为空；退出码都为 0。
8. 运行前后协作组目录里的文件逐字节不变。
9. Claude 桌面版实测：拦下后同一轮继续，并收到了 `reason`；第二次 `stop_hook_active` 为 true，放行。结果写进本规格的「实测记录」一节。

## 假设

1. 开发线会话的工作目录在名册登记的 `repo` 里（同一仓库只登记一条开发线）。
2. Claude 桌面版的 Code 会话和 Claude Code 命令行用同一套钩子机制。验收标准 9 实测不成立时，回来改规格。

## 未决问题

无。

## 文档建议

无。钩子的安装、信任和排查写进 README（onboarding 模块已记）。
