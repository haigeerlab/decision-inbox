<!-- spec-guard: review approved -->

# Implementation Plan: loop-detection

> 依据：`spec/loop-detection.md`（用户 2026-10-19 批准，同日修订「换方案」待复审）。任务清单：`tasks/loop-detection/todo.md`。分支 `claude/loop-detection`（从 main d02c61d 开出，main 已含 R21 前三个模块）。

需要的外部条件：无（不装依赖、不联网；只用仓库已有的 `python3`、`git` 与测试）。

## Overview

五个任务，各自先写失败的测试再改：读新事实 → 打标与每个模块的事实 → 打转判断与答复写法 → 展示 → 停滞判断调整与文档。最后做一次最终验收。不升版本号。

## Architecture Decisions

- **`decision_inbox/loops.py`**（新）：
  - `tag(g, maps, crews)`：给没打标的事项写 `module`，记事件 `items.module-tagged`；一次事务。
  - `facts(g, now, maps, crews, git=read_commits)` → 每个在做的模块一个 `ModuleLoop`（线、模块、项目、事项列表、n、M、k、各段、j、开工时长、进度、最后一次进展、命中原因或 None、读不到的说明）。纯计算，git 读取作为参数传入，测试不碰真仓库。
  - `read_commits(repo, since)`：`git -C <repo> log --first-parent --format=%cI --since=<since> HEAD`，3 秒超时，失败返回 None（算「读不到」）。
  - `quiet(g, key, until)`：记「继续等」的安静期，状态域 `loops`。
- **事实来源**：`specguard.ModuleFact` 加 `gates_total`、`gates_done`（没有键为 None）；`crew.Module` 加 `answers`（ref、at、commitsAfter、ticksAfter）和 `waits`（ref、decide、at、state），形状不对的条目丢掉、不连坐。
- **答复**：`items.interpret_reply` 认「N 挂起」「N 换方案：…」「N 继续等」，只在这一项的模块正处于打转提示时认；`Answer` 加 `loop_option`，`items.answer` 把选项原文作为 `option_text` 写进【用户答复】。`hub.reply` 在转发后对「继续等」调 `loops.quiet`；新增「看模块 <id>」。
- **展示**：`view` 的卡片抬头、折叠历史、打转提示都从 `ModuleLoop` 取；`hub.main_view` 在去会话操作一栏后加打转提醒行，`view.render` 在线状态行后加「在做的模块」一段。`main_view` 与 `patrol.plan` 多收一个 `loops` 参数（默认 None：不显示这些新内容，旧调用方不受影响）。
- **打标调用**：`__main__` 的主视图、答复、巡视三处在读好 `maps`、`crews` 后先 `loops.tag`，再算 `loops.facts` 传下去。
- 阈值放 `stall.DEFAULTS`：`loopAnswers` 2、`loopHours` 12、`loopQuietHours` 12，仍可在 group.json 的 `stall` 下覆盖。

## Task List

- **Task 1 读新事实**（Spec「数据来源」）：先写 `tests/test_specguard.py`（有 gates、没有 gates、gates 为 null）与 `tests/test_crew.py`（answers 与 waitUser 明细、null、形状不对）的用例，再改 `specguard.py`、`crew.py`。验证：先失败后通过；原有用例不变。
- **Task 2 打标与每个模块的事实**（Spec 第 1、2 节；验收 4、5 的计算部分）：先写 `tests/test_loops.py`：三种打标来源与对不上；n 不算去会话操作与被取代的；M、k、基准未知；module-crew 与单模块线的分段、j、读不到；开工时长扣等用户（含去会话操作）、扣等待记录、重叠只扣一次；进度与最后一次进展。再写 `loops.py` 的 `tag`、`facts`、`read_commits`。验证：先失败后通过。
- **Task 3 打转判断与答复写法**（Spec 第 3、4 节的判断与答复；验收 1、2、3、7）：先写测试：①只看「后面又来问过」的段、中间有提交不判；②累计满 12 小时、等用户时间不算；有读不到不判；安静期内不判；「N 挂起／换方案：…／继续等」转发并带选项原文，不在提示中的事项不认这些词，与字母答复写在同一段时追问。再改 `loops.py`、`items.py`、`hub.py`（含「看模块」）。验证：先失败后通过；原有答复用例不变。
- **Task 4 展示**（Spec 第 4 节提示与提醒、第 5、6、8 节；验收 4、5、6、8 的展示部分、10）：先写 `tests/test_view.py`、`tests/test_hub.py`、`tests/test_health.py` 用例：抬头各字段与「模块未知」写法；交审全文第一行换成新抬头、其余照旧；折叠最多 5 行和「看模块」提示；打转提示与三个选项在普通卡片和交审全文顶上、不在去会话操作上；主视图顶部提醒行与「在做的模块」段；线状态「等你去会话操作」。再改 `view.py`、`hub.py`、`health.py`。验证：先失败后通过；用本分支代码对 di-p0 状态目录的**临时副本**出一次主视图（不写真实状态目录），看抬头、模块段，结果写进 todo。
- **Task 5 停滞判断、叫法与文档**（Spec 第 7、9 节；验收 8、9、11）：先写 `tests/test_stall.py`、`tests/test_patrol.py` 用例：有开着的【等待用户】或正在审查的模块也被看到；等用户的时段不算停滞时长；打转命中且不在安静期的模块不发 R14 叫醒；R14 叫醒文字、逾期行、规则段里是「换方案」。再改 `stall.py`、`patrol.py`、`onboard.py`（规则段一句）、`__main__.py`（打标与 facts 调用），README 三节。验证：旧称扫描、全量测试通过。

## Checkpoint（gate）：模块最终验收

列出改动的文件、每条验收标准的证据和测试数，然后开 PR（base main）。

## 影响面

- 主视图多出「在做的模块」一段、打转提醒行，卡片抬头变长；交审全文第一行格式变了，其余不变。
- 事项记录多一个 `module` 字段，第一次出主视图时给已有的待决与历史事项补打标（单模块线的旧事项按当时的 `activeModule` 打，可能不准；交审事项按交审里写的模块，准）。
- 巡视：R14 按模块的停滞判断不再跳过等用户与审查中的模块；打转期间不对该模块叫醒。
- 协作规则段只改停滞询问那一句的叫法；不改契约。已接入的线不重跑接入也能用，重跑后规则段才换成「换方案」。

## 风险

| 风险 | 对策 |
|---|---|
| 旧事项补打标打错模块（接入前就有的事项） | 只影响次数显示；Spec 未要求回溯，测试覆盖「打完不改」；验收时在副本上看一遍 |
| 主视图每次多读 git（每条单模块线一次） | 3 秒超时、失败算读不到；只读在做的模块的那条线 |
| crew 事项靠「要你决定」首行对模块，措辞改了就对不上 | 对不上记「模块未知」不计数；交审事项不受影响 |
| 抬头太长 | 读不到的项整段省略，只留「…读不到」一个词 |
| 改了 `main_view`／`plan` 的签名 | 新参数有默认值；全量测试兜底 |
