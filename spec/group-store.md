<!-- spec-guard: review approved a8696dc78b7f -->
# Spec: group-store

> 能力图模块 `group-store`。需求来源：`docs/requirements-record.md` 第 2 节第 9 条、3 个小问题第 1 条、第 10.1 节、第 12 节第 2、11 项。

## 目标

给后面 13 个模块打底：搭好插件骨架（Claude Code 与 Codex 两份清单），在 `~/.decision-inbox/<协作组>/` 下提供可靠的状态读写、编号分配、事件日志和会话名册。状态不能只存在会话上下文里，一压缩就丢（需求 10.1）；多个会话的停止钩子会同时读写，所以写入要互斥、读取不能读到半截文件。

使用者是本插件的其他模块（Python 调用）和接入命令；用户不直接用本模块，只通过只读的 `store show` 排查。

## 范围

**范围内**

- 插件骨架：`.claude-plugin/plugin.json`、`.codex-plugin/plugin.json`，插件名 `decision-inbox`（第 12 节第 2 项已定：保持全名，命令写作 `/decision-inbox:<命令>`）。本模块不注册任何命令、技能或钩子，清单只有元数据。
- Python 包 `decision_inbox`，本模块只含 `store.py` 与 CLI 入口。
- 协作组目录：定位、创建、协作组名校验。
- 状态文件：读、原子写、版本检查、损坏检测。
- 编号分配：每个协作组一条全局递增编号。
- 事件日志：只追加，供 `/item` 时间线和第二版统计使用。
- 会话名册：会话的短名、角色、所属线、宿主、仓库路径。
- 只读排查命令 `store show`；建组命令 `store init`（供 onboarding 调用）。

**范围外**

- 待答项、等待单、审查登记等的字段（由 decision-queue、wait-tickets、review-registry 各自的 Spec 定，本模块只提供存取它们的通用机制）。
- 读 agent-relay、读 spec-guard 产物、任何显示格式、接入流程本身。
- 任何删除、清理或归档功能（见关键决策 5）。

## 关键决策与取舍（请重点审）

1. **一个协作组一条编号序列，待答项和等待单共用。** 编号是从 1 开始的整数，永不复用。理由：实验里的故障之一是「两套编号混用」；共用一条序列后，任何 `#12` 在本组里只指一样东西，`结束：#12`、`12 B`、`/item 12` 都不会撞号。代价是待答项的编号不连续（中间夹着等待单的号），主视图上用户会看到跳号。
2. **状态分两类文件。** 当前状态存成「快照文件」（每个领域一个 JSON，整份原子替换）；变化历史存成「事件日志」（一个 JSONL，只追加）。查询读快照，追溯读日志。
3. **一次写事务 = 先追加事件，再替换快照**，全程持有组锁。快照里记 `lastSeq`：它反映到了**本领域**的哪条事件。事件属于类型里点号前的那个领域（`items.created` 属于 `items`），所以各领域模块的事件类型前缀必须与它的快照领域名相同。若进程在两步之间崩溃，日志比该领域快照多出事件；`store show` 和每次写事务开始时会检测到「快照落后于日志 N 条」并报告，**不自动修复**（修复要用各领域自己的规则重放，属于各领域模块）。之后的写入照常进行。
4. **读不加锁。** 快照靠「写临时文件 → fsync → 原子改名」保证读者只会读到完整的旧版或新版；日志最后一行若是被截断的半行，读者跳过它并报告，下一次追加先补换行再写；补换行后那半行会留在日志中间，所以日志里任何一行无法解析，读者都跳过并报告（警告，不算损坏），不因此拒绝读写。这样停止钩子的只读检查不会被收件枢纽的写入卡住。
5. **永久保留，不提供删除。**（第 12 节第 11 项，用户 2026-10-16 已定）本模块不含任何删除、截断、轮转代码。「今天已关闭」区每天清空是显示层的事，不删文件。
6. **文件权限收紧。** 状态目录 `0700`、文件 `0600`：里面有用户答复原话和各项目的事项摘要。
7. **测试可改根目录。** 环境变量 `DECISION_INBOX_HOME` 覆盖默认的 `~/.decision-inbox`，测试全部跑在临时目录里，不碰真实数据。

## 假设（用户 2026-10-16 已确认）

1. Python 3 标准库实现，不引入第三方依赖；钩子入口用 bash＋Python。最低支持 Python 3.10（本机为 3.10.7）。
2. 插件同时带 Claude Code 与 Codex 两份清单。
3. 一个协作组对应一个收件枢纽会话；协作组名在接入时由用户取。
4. 写入用文件锁加「临时文件＋原子改名」。
5. 事件日志只追加，`/item` 时间线从日志读；当前状态另存快照。

## 接口约定

### 目录与文件（第 12 节第 11 项的「存哪些文件」，随本 Spec 一起审）

```text
~/.decision-inbox/                 根目录（DECISION_INBOX_HOME 可覆盖）
└── <协作组>/                      0700
    ├── group.json                 组元数据：version、name、createdAt
    ├── roster.json                会话名册（快照）
    ├── counter.json               编号序列：{"version":1,"next":13}
    ├── events.jsonl               事件日志，只追加
    ├── state/<领域>.json          各领域快照，例如 state/items.json、state/tickets.json
    └── .lock                      组锁（fcntl.flock），内容为空
```

- 协作组名：小写字母、数字、连字符，1～40 个字符，不以连字符开头或结尾。其他一律拒绝（包括 `..`、`/`、空串、大写、中文），报错说明规则。
- 领域名同样规则；由调用方模块固定，不来自用户输入。
- 所有 JSON 文件顶层带 `"version": 1`。读到不认识的版本：读取报错、拒绝写入，不改文件。
- 读到无法解析的 JSON：报错并写明文件路径；拒绝写入，**原文件一个字节都不改**。
- 时间一律 ISO 8601、带本机时区偏移，精确到秒，例如 `2026-10-16T13:36:05+08:00`。

### 事件日志一行

```json
{"seq": 41, "at": "2026-10-16T13:36:05+08:00", "type": "items.created", "ref": 12, "actor": "前端", "data": {}}
```

- `seq`：本组内从 1 递增、不跳号不重复（与编号序列无关）。
- `type`：`<领域>.<动作>`，领域必须与该模块的快照领域名相同（见关键决策 3），动作由各领域模块定义；本模块只校验格式。
- `ref`：相关的编号（没有时为 `null`）；`actor`：名册里的短名，或 `user`、`system`。
- `data`：领域自定义内容，本模块原样存取。

### 会话名册条目

| 字段 | 含义 | 约束 |
|---|---|---|
| `relayName` | agent-relay 里登记的名字，作唯一键 | 必填，组内唯一 |
| `shortName` | 显示用短名，例如「前端」「后台负责人」 | 必填，组内唯一，1～12 个字符 |
| `role` | `hub` 收件枢纽／`coordinator` 总协调／`owner` 负责人／`dev` 开发线 | 必填；`hub` 每组恰好 0 或 1 个 |
| `line` | 所属线的短名（负责人填它负责的线，可多条，用数组） | `dev` 必填一条；`owner` 至少一条；`hub`、`coordinator` 为空 |
| `host` | `claude-desktop`／`codex-desktop` | 必填；`hub` 只能是 `claude-desktop`（需求假设第 4 条） |
| `repo` | 该会话工作的仓库绝对路径，供 spec-guard-reader 读 | `dev` 必填，其他选填 |

### Python 接口（其他模块只通过这些用）

```python
from decision_inbox import store

g = store.open_group("shop-redesign")          # 组不存在时抛 GroupNotFound
with g.transaction() as tx:                     # 持组锁；退出时先追加事件再替换快照
    n = tx.allocate_number()                    # 12
    items = tx.read_state("items")              # 不存在时返回 {"version": 1, "lastSeq": 0}
    items.setdefault("open", {})[str(n)] = {...}
    tx.append_event("items.created", ref=n, actor="前端", data={...})
    tx.write_state("items", items)

store.read_state(g, "items")                    # 不加锁的只读
store.read_events(g, ref=12)                    # 某编号的全部事件，按 seq 排序
store.roster(g)                                 # 名册条目列表
store.find_session(g, short_name="前端")         # 按 relayName 或 shortName 查一条，没有返回 None

with g.transaction() as tx:
    tx.add_session({...})                       # relayName 已存在则拒绝
    tx.replace_session({...})                   # 只能替换已有的同 relayName 条目
    tx.warnings                                 # 事务开始时发现的问题，例如「快照落后于日志 N 条：items」
```

- 事务内抛异常：什么都不写（事件和快照都不落盘），编号也不消耗。
- 事务里没调用任何写方法时，不改任何文件。

### 命令行

```bash
python3 -m decision_inbox store init <协作组>   # 建组；已存在时不改任何文件，退出码 0 并说明「已存在」
python3 -m decision_inbox store show <协作组>   # 只读：路径、各文件版本、下一个编号、名册人数、事件条数、一致性检查结果
```

退出码：`0` 成功；`2` 参数或协作组名不合法、组不存在；`3` 文件损坏、版本不认识或快照落后于日志（`show` 照常打印其余信息）。

## 项目结构

```text
.claude-plugin/plugin.json   Claude Code 清单（只有元数据）
.codex-plugin/plugin.json    Codex 清单（只有元数据）
decision_inbox/              Python 包，只用标准库
  __init__.py
  __main__.py                CLI 入口：python3 -m decision_inbox
  store.py                   本模块
tests/
  test_store.py              本模块的单元与并发测试
docs/requirements-record.md  需求记录（已有）
```

## 命令

```bash
python3 -m unittest discover -s tests -v
```

没有构建步骤。

## 代码风格

```python
class StoreCorrupt(StoreError):
    """A state file exists but cannot be trusted; never overwrite it."""

def _atomic_write_json(path: Path, doc: dict) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
```

- 代码、标识符、注释用英文；给用户看的输出与报错用中文。
- 只用标准库；类型标注写全；异常类集中在 `store.py` 顶部，都继承 `StoreError`。
- JSON 写出 `ensure_ascii=False`，中文原样保存。

## 测试策略

- 框架：标准库 `unittest`，全部测试设置 `DECISION_INBOX_HOME` 指向临时目录。
- 并发用 `multiprocessing` 起真实多进程，不用线程模拟。
- 崩溃用「事件已追加、快照未替换」的人工构造文件模拟。
- 不追求覆盖率数字；下面每条验收标准至少对应一个测试。

## 边界

- **始终**：写入前检查版本与可解析性；损坏文件原样保留；所有写入走组锁；测试不碰真实 `~/.decision-inbox`。
- **先问**：给状态文件加新的顶层文件类型；改编号或事件日志的格式；引入任何第三方依赖。
- **绝不**：删除、截断、轮转任何状态文件；自动修复损坏或不一致的文件；把状态写进任何项目仓库。

## 验收标准

1. `store init demo` 在临时根目录下建出 `demo/`（`0700`），含 `group.json`、`roster.json`、`counter.json`、`events.jsonl`（均 `0600`），`group.json` 的 `version` 为 1；再跑一次不改任何文件的内容和修改时间，退出码 0。
2. 协作组名 `../x`、`Demo`、`-a`、`a-`、空串、41 个字符、`前端` 全部被拒，退出码 2，根目录下不出现新目录。
3. 20 个进程各在独立事务里分配 50 个编号：得到 1～1000 共 1000 个号，无重复无遗漏；`events.jsonl` 若每次附带一条事件，则 `seq` 也是 1～1000 连续。
4. 事务内抛异常后：编号序列、事件日志、快照三者都与事务前逐字节相同。
5. 把 `state/items.json` 改成非法 JSON：`read_state` 抛 `StoreCorrupt` 且信息含该文件路径；开事务写它被拒；文件字节不变；`store show` 退出码 3 并点名该文件。
6. 把某文件的 `version` 改成 2：读取报错、写入被拒、文件不变。
7. 在 `events.jsonl` 末尾追加半行：`read_events` 返回其余完整事件并给出一条警告；下一次追加后，新事件独占完整一行，可被正常读出。
8. 构造「日志 `seq` 到 42、快照 `lastSeq` 为 41」：`store show` 报告「快照落后于日志 1 条」，退出码 3；随后的写事务仍可成功。
9. 名册：短名或 `relayName` 重名、第二个 `hub`、`hub` 的宿主是 `codex-desktop`、`dev` 没有 `line` 或 `repo`——都被拒，名册不变。
10. 不设 `DECISION_INBOX_HOME` 时根目录解析为 `~/.decision-inbox`（只断言路径，不实际写）。
11. 两份插件清单是合法 JSON，`name` 都是 `decision-inbox`，版本号一致。
12. `decision_inbox/` 下没有标准库以外的 import（测试里扫描断言）；代码里没有对状态文件调用 `unlink`、`rmtree`、`truncate`（测试里扫描断言）。

## 未决问题

无。第 12 节与本模块相关的第 2 项（前缀）、第 11 项（保留期限）已由用户定；第 11 项的「存哪些文件」以本 Spec 的目录约定为准，随本次评审确认。

## 文档建议

无。状态文件格式是本模块对其他模块的接口，已写在本 Spec「接口约定」里；README 留到 onboarding 模块（能力图评审时已记）。
