"""Parse and validate the hand-written inbox messages (see spec/message-protocol.md).

Writing is lenient (either colon width, values spanning lines); judging is
strict (a required field that cannot be found is a problem, never guessed).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

CONTRACT_VERSION = "2.6"  # session-protocol version this plugin is pinned to (tests/test_contract.py)

KIND_TAGS = {
    "等待用户": "wait-user",
    "用户答复": "user-reply",
    "等待其他会话": "wait-session",
    "已恢复": "resumed",
    "撤回": "withdraw",
    "审查结论": "review-conclusion",
    "登记回执": "hub-receipt",  # v2.0: the hub tells the sender which item it became (review-nearby)
}

# Field names each kind knows, in the order they are usually written.
FIELDS = {
    "wait-user": ("来自", "项目", "要你决定", "要点", "任务", "模块", "类型", "会话", "链接", "被拦的操作", "点哪个按钮", "为什么批不了",
                  "宿主原文", "关联事项", "注意", "推荐理由", "批了会怎样", "产物", "交审原文", "审查原文", "待用户决定", "架构审查", "选项与我的建议", "你该回",
                  "是否完全停住", "适用会话", "各线范围"),
    "user-reply": ("事项", "用户原话", "选项原文", "适用于你的范围", "答复时间", "原事项全文"),
    "wait-session": ("在等谁", "等什么"),
    "resumed": (),
    "withdraw": ("事项", "原因"),
    "review-conclusion": ("审查编号", "节点", "模块", "送审方", "结论", "来自", "要点", "任务", "须修改", "待用户决定"),
    "hub-receipt": ("原消息", "事项", "状态", "取代", "写法提示"),
    "unknown": (),
}
# A terminal field takes every remaining line, whatever it looks like.
TERMINAL = {"原事项全文"}

# Stable issue codes (spec 关键决策 5): only ever added to. A trailing ":" takes a suffix.
PROBLEM_CODES = ("unknown-kind", "missing-end", "missing-field:", "missing-options", "bad-stop-flag",
                 "scope-missing:", "scope-unknown:", "bad-node", "bad-verdict",
                 # v2.0 (review-nearby)
                 "change-count-mismatch", "bad-decision-item:", "duplicate-decision:", "bad-receipt-status",
                 # v2.1 (approval-display)
                 "bad-artifact-line", "bad-file-line",
                 # v2.5 (light-task-field)
                 "bad-task-ref", "module-task-both")
REVIEW_NODES = {"Spec": "spec", "Plan": "plan", "接口提案": "interface", "最终验收": "final"}
HINT_CODES = ("no-consequence:", "no-recommendation", "brief-thin", "change-count-missing")

_TAG_RE = re.compile(r"【([^】]*)】")
_TASK_RE = re.compile(r"^T\d+$")  # v2.5
_COLON = "[：:]"
_END_RE = re.compile(rf"^结束\s*{_COLON}\s*(.*)$")
_REPLY_RE = re.compile(rf"^回复\s*{_COLON}\s*#\s*(\d+)\s*$")
_NUM_RE = re.compile(r"#\s*(\d+)")
_OPTION_RE = re.compile(r"^(推荐\s*)?([A-Z])\s*[：:.、)）]\s*(.*)$")
_RECOMMEND_RE = re.compile(rf"^推荐\s*{_COLON}?\s*([A-Z])\s*$")
_CONSEQUENCE_RE = re.compile(rf"^选了会怎样\s*{_COLON}\s*(.*)$")
_SCOPE_RE = re.compile(rf"^[-*•·]?\s*([^\s：:]+)\s*{_COLON}\s*(.*)$")
_SESSION_SEP = re.compile(r"[、,，+＋\s]+")
_REVIEW_REF_RE = re.compile(r"（\s*(#?[A-Za-z]*-?\d+)\s*）$")
# Requirement 4.3: only these wordings count; anything else is "unrecognized".
_REVIEW_FORMS = (
    (re.compile(r"^通过$"), "passed"),
    (re.compile(r"^通过，附建议(\d+)条(（.*）)?$"), "passed-with-advice"),
    (re.compile(r"^进行中，请勿先批$"), "in-progress"),
    (re.compile(r"^不适用（不属于审查节点）$"), "not-applicable"),
    (re.compile(r"^用户豁免$"), "waived"),
)


@dataclass(frozen=True)
class Issue:
    code: str
    text: str


@dataclass(frozen=True)
class EndMark:
    ids: tuple[int, ...] = ()
    none: bool = False
    unnumbered_reason: str | None = None
    present: bool = False


@dataclass(frozen=True)
class Option:
    letter: str
    text: str
    consequence: str | None


@dataclass(frozen=True)
class ReviewLine:
    status: str
    advice_count: int | None = None
    ref: str | None = None
    raw: str | None = None


def _review(raw: str | None) -> ReviewLine:
    if raw is None:
        return ReviewLine("absent")
    value = raw.strip().replace(",", "，").replace("(", "（").replace(")", "）")
    ref = None
    m = _REVIEW_REF_RE.search(value)
    if m:
        ref, value = m.group(1), value[:m.start()].rstrip()
    for pattern, status in _REVIEW_FORMS:
        hit = pattern.match(value)
        if hit:
            advice = int(hit.group(1)) if status == "passed-with-advice" else None
            return ReviewLine(status, advice, ref, raw)
    return ReviewLine("unrecognized", None, None, raw)


@dataclass(frozen=True)
class Conclusion:
    ref: str
    node: str
    submitter: str
    verdict: str
    advice_count: int | None = None
    module: str | None = None   # optional 模块 field (map-view), verbatim without surrounding spaces
    # v2.0 有须修改项N条 and 须修改; both None for the v1 form that writes neither (contract sample basic)
    change_count: int | None = None
    changes: tuple[str, ...] | None = None


@dataclass(frozen=True)
class Decision:
    """One 「待用户决定」 question (v2.0): D-number, question, lettered options, the reviewer's lean."""
    id: str
    question: str
    options: tuple[tuple[str, str], ...]
    lean: str | None
    lean_reason: str | None


@dataclass(frozen=True)
class Artifact:
    """「产物」 (v2.1): a file at a commit, shown in full by the hub (approval-display)."""
    module: str | None
    path: str
    commit: str
    previous: str | None = None


@dataclass(frozen=True)
class OriginalRef:
    """「交审原文」「审查原文」 (v2.1): a file holding the text verbatim, pinned by a sha256 prefix."""
    module: str | None
    path: str
    fingerprint: str


@dataclass(frozen=True)
class Receipt:
    """【登记回执】 (v2.0): the sender's own mail id, and the items the new one replaced."""
    original: int | None
    status: str | None
    supersedes: tuple[int, ...] = ()


def _verdict(raw: str) -> tuple[str, int | None] | None:
    value = raw.strip().replace(",", "，").replace("(", "（").replace(")", "）")
    if value == "通过":
        return "passed", None
    if value == "有须修改项":
        return "changes-required", None
    m = re.match(r"^有须修改项(\d+)条$", value)
    if m:
        return "changes-required", int(m.group(1))
    m = re.match(r"^通过，附建议(\d+)条(（.*）)?$", value)
    return ("passed-with-advice", int(m.group(1))) if m else None


@dataclass(frozen=True)
class Message:
    kind: str
    markers: tuple[tuple[str, int], ...]
    ends: EndMark
    reply_to: int | None
    fields: dict[str, str]
    item: int | None
    problems: tuple[Issue, ...]
    hints: tuple[Issue, ...] = field(default=())
    options: tuple[Option, ...] = field(default=())
    recommended: str | None = None
    suggested_reply: str | None = None
    fully_stopped: bool | None = None
    lines_in_scope: tuple[str, ...] = ()
    scopes: dict[str, str] = field(default_factory=dict)
    review: ReviewLine = field(default_factory=lambda: ReviewLine("absent"))
    conclusion: Conclusion | None = None
    decisions: tuple[Decision, ...] = ()
    receipt: Receipt | None = None
    local_item: str | None = None  # v2.0: a coordinator's own C-number in 【用户答复】「事项」
    artifacts: tuple[Artifact, ...] = ()
    originals: dict[str, tuple[OriginalRef, ...]] = field(default_factory=dict)  # submission / conclusion
    wait_kind: str | None = None  # v2.2: "go-to-session" when 类型 is 去会话操作; v2.3 adds the approval classes
    points: tuple[tuple[str, str], ...] = ()  # v2.3: (point name, text) of the class, in writing order
    go_to_session: dict | None = None  # v2.2: the 去会话操作 fields under the contract's keys (go-to-session)
    module: str | None = None  # v2.4: 「模块」 as written (stripped), "无" for a line-level item
    task: str | None = None  # v2.5: 「任务」 when it is a T-number, e.g. "T3"

    @property
    def ok(self) -> bool:
        return not self.problems


def _field_re(name: str) -> re.Pattern:
    if name == "选项原文":
        return re.compile(rf"^选项\s*[A-Z]\s*原文\s*{_COLON}\s*(.*)$")
    return re.compile(rf"^{re.escape(name)}\s*{_COLON}\s*(.*)$")


def _parse_end(value: str) -> EndMark:
    value = value.strip()
    m = re.match(r"^无编号\s*[（(](.*)[）)]\s*$", value)
    if m:
        return EndMark(unnumbered_reason=m.group(1).strip(), present=True)
    if value == "无":
        return EndMark(none=True, present=True)
    ids = tuple(int(x) for x in _NUM_RE.findall(value))
    return EndMark(ids=ids, present=True)


def _split(text: str):
    """Header (tags, 结束, 回复) first, then the field area."""
    lines = text.replace("\r\n", "\n").split("\n")
    tags: list[str] = []
    end = EndMark()
    reply_to = None
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        found = _TAG_RE.findall(line)
        if found and not _TAG_RE.sub("", line).strip():
            tags += found
        elif _END_RE.match(line):
            end = _parse_end(_END_RE.match(line).group(1))
        elif _REPLY_RE.match(line):
            reply_to = int(_REPLY_RE.match(line).group(1))
        else:
            break
        i += 1
    return tags, end, reply_to, lines[i:]


THIN_BRIEF_WORDS = ("详见", "已明确", "同上")  # a brief the user cannot decide from (wait-honesty-and-briefs B2)


def _fields(kind: str, body: list[str]) -> dict[str, str]:
    patterns = [(name, _field_re(name)) for name in FIELDS[kind]]
    values: dict[str, list[str]] = {}
    current = None
    for line in body:
        if current in TERMINAL:
            values[current].append(line)
            continue
        for name, pattern in patterns:
            m = pattern.match(line.strip())
            if m and name not in values:
                current = name
                values[name] = [m.group(1)] if m.group(1) else []
                break
        else:
            if current is not None:
                values[current].append(line)
    out = {}
    for name, chunk in values.items():
        while chunk and not chunk[-1].strip():
            chunk.pop()
        out[name] = "\n".join(chunk)
    return out


def _item(value: str | None) -> int | None:
    m = _NUM_RE.search(value or "")
    return int(m.group(1)) if m else None


_DECISION_HEAD_RE = re.compile(rf"^(D\d+|C\d+-\d+)\s*{_COLON}\s*(.*)$")  # v2.6: or a C pending number, C15-1
_DECISION_OPTION_RE = re.compile(r"^([A-Z])\s*[：:.、]\s*(.*)$")
_LEAN_RE = re.compile(rf"^倾向\s*{_COLON}\s*([A-Z])\s*(?:[（(](.*)[）)])?\s*$")
_CHANGE_RE = re.compile(r"^\d+\s*[.．、]\s*(.*)$")
LOCAL_ITEM_RE = re.compile(r"^\s*(C\d+)(?![A-Za-z0-9])")


def _decisions(block: str, problems: list[Issue]) -> tuple[Decision, ...]:
    """「待用户决定」 (v2.0): bad items first in writing order, then duplicates."""
    found: list[dict] = []
    for line in block.split("\n"):
        text = line.strip()
        head = _DECISION_HEAD_RE.match(text)
        if head:
            found.append({"id": head.group(1), "question": head.group(2).strip(), "options": [],
                          "lean": None, "reason": None})
            continue
        if not found or not text:
            continue
        lean = _LEAN_RE.match(text)
        option = _DECISION_OPTION_RE.match(text)
        if lean:
            found[-1]["lean"] = lean.group(1)
            found[-1]["reason"] = (lean.group(2) or "").strip() or None
        elif option:
            found[-1]["options"].append((option.group(1), option.group(2).strip()))
    out = tuple(Decision(d["id"], d["question"], tuple(d["options"]), d["lean"], d["reason"]) for d in found)
    for d in out:
        if len(d.options) < 2 or d.lean is None:
            problems.append(Issue(f"bad-decision-item:{d.id}", f"「待用户决定」（待你决定）里的 {d.id} 少于两个选项或没写倾向"))
    seen: set[str] = set()
    for d in out:
        if d.id in seen:
            problems.append(Issue(f"duplicate-decision:{d.id}", f"「待用户决定」（待你决定）里 {d.id} 重复"))
        seen.add(d.id)
    return out


_MODULE_PREFIX = r"(?:-\s*)?(?:([^\s：:/]+)\s*[：:]\s*)?"
_ARTIFACT_RE = re.compile(rf"^{_MODULE_PREFIX}(/.+?)\s*[＠@]\s*([0-9a-f]{{7,40}})\s*(?:（上一版\s*([0-9a-f]{{7,40}})\s*）)?\s*$")
_FILE_LINE_RE = re.compile(rf"^{_MODULE_PREFIX}(/.+?)\s+(sha256:[0-9a-f]{{12,64}})\s*$")


def _artifacts(block: str, problems: list[Issue]) -> tuple[Artifact, ...]:
    found, bad = [], False
    for line in (x.strip() for x in block.split("\n")):
        if not line:
            continue
        m = _ARTIFACT_RE.match(line)
        if m:
            found.append(Artifact(m.group(1), m.group(2), m.group(3), m.group(4)))
        else:
            bad = True
    if bad:
        problems.append(Issue("bad-artifact-line", "「产物」有一行不是「绝对路径 ＠ 提交」"))
    return tuple(found)


def _original_refs(name: str, block: str, problems: list[Issue]) -> tuple[OriginalRef, ...]:
    found, bad = [], False
    for line in (x.strip() for x in block.split("\n")):
        if not line:
            continue
        m = _FILE_LINE_RE.match(line)
        if m:
            found.append(OriginalRef(m.group(1), m.group(2), m.group(3)))
        else:
            bad = True
    if bad:
        problems.append(Issue("bad-file-line", f"「{name}」有一行不是「绝对路径 sha256:指纹」"))
    return tuple(found)


def _require(fields: dict, names, problems: list[Issue]) -> None:
    for name in names:
        if not fields.get(name, "").strip():
            problems.append(Issue(f"missing-field:{name}", f"缺少「{name}」"))


def _options(block: str) -> tuple[tuple[Option, ...], str | None]:
    """Split 选项与我的建议 into lettered options; never merge or complete them."""
    options: list[dict] = []
    recommended = None
    for raw in block.split("\n"):
        line = raw.strip()
        if not line:
            continue
        rec = _RECOMMEND_RE.match(line)
        opt = _OPTION_RE.match(line)
        cons = _CONSEQUENCE_RE.match(line)
        if rec:
            recommended = rec.group(1)
        elif opt:
            options.append({"letter": opt.group(2), "text": [opt.group(3)], "consequence": None})
            if opt.group(1):
                recommended = opt.group(2)
        elif cons and options:
            options[-1]["consequence"] = [cons.group(1)]
        elif options:
            target = options[-1]["consequence"] or options[-1]["text"]
            target.append(line)
    return tuple(
        Option(o["letter"], "\n".join(o["text"]).strip(),
               "\n".join(o["consequence"]).strip() if o["consequence"] else None)
        for o in options
    ), recommended


def _scopes(block: str) -> dict[str, str]:
    """各线范围: one 「会话：范围」 entry per line, later lines continue the entry."""
    scopes: dict[str, list[str]] = {}
    last = None
    for raw in block.split("\n"):
        line = raw.strip()
        if not line:
            continue
        m = _SCOPE_RE.match(line)
        if m:
            last = m.group(1)
            scopes.setdefault(last, []).append(m.group(2).strip())
        elif last is not None:
            scopes[last].append(line)
    return {k: "\n".join(v) for k, v in scopes.items()}


WAIT_KINDS = {"去会话操作": "go-to-session",
              # v2.3: the approval classes of the decision-card template
              "能力图审阅": "capability-map", "Spec": "spec", "Plan": "plan", "Spec 与 Plan": "spec-plan",
              "中途检查点": "checkpoint", "最终验收": "final", "接口提案": "interface", "卡住选做法": "stuck"}
_SPEC_POINTS = ("目标", "做／不做", "要你确认的假设", "验收标准", "附带的小决定")
_PLAN_POINTS = ("分几步", "会改哪些文件", "风险", "中途会停下来问你的地方")
# v2.3: the fixed content points of each class, in writing order, written as 「小项名：内容」 lines in 要点
POINTS = {"capability-map": ("拆成哪些模块", "先后顺序", "文档建议"), "spec": _SPEC_POINTS, "plan": _PLAN_POINTS,
          "spec-plan": _SPEC_POINTS + _PLAN_POINTS, "checkpoint": ("做到哪了", "为什么停在这", "接下来要做的那一步"),
          "final": ("做了什么", "验收结果", "改了哪些文件", "Spec 中途改过吗"),
          "interface": _SPEC_POINTS + ("改了哪个接口", "哪些模块要跟着改"), "stuck": ("出了什么事",)}


def _points(kind: str | None, brief: str) -> tuple[tuple[str, str], ...]:
    """v2.3: this class's content points in 要点, each running on to the next point name or the end."""
    names = POINTS.get(kind or "")
    if not names:
        return ()
    pattern = re.compile("^(" + "|".join(re.escape(n).replace("／", "[／/]") for n in names) + rf")\s*{_COLON}\s*(.*)$")
    out: list[list[str]] = []
    for line in brief.split("\n"):
        m = pattern.match(line.strip())
        if m:
            name = next(n for n in names if re.fullmatch(re.escape(n).replace("／", "[／/]"), m.group(1)))
            out.append([name, m.group(2)])
        elif out:
            out[-1][1] += "\n" + line
    return tuple((name, text.strip()) for name, text in out)


# v2.2 go-to-session: contract key -> field, required ones first and in the order their problems are reported.
_GO_TO_SESSION = (("session", "会话", True), ("blockedAction", "被拦的操作", True), ("button", "点哪个按钮", True),
                  ("reason", "为什么批不了", True), ("hostText", "宿主原文", False), ("link", "链接", False),
                  ("relatedItem", "关联事项", False))


def _go_to_session(fields: dict, problems: list[Issue]) -> tuple[str | None, dict | None]:
    """「类型」(v2.2 去会话操作, v2.3 approval classes) and the 去会话操作 fields; an unknown 类型 is bad-wait-kind."""
    written = fields.get("类型", "").strip()
    if not written:
        return None, None
    kind = WAIT_KINDS.get(written)
    if kind is None:
        problems.append(Issue("bad-wait-kind", f"「类型」只能写{'、'.join(f'「{k}」' for k in WAIT_KINDS)}，现在是「{written}」"))
        return None, None
    if kind != "go-to-session":
        return kind, None
    out = {}
    for key, name, required in _GO_TO_SESSION:
        value = fields.get(name, "").strip()
        if required and not value:
            problems.append(Issue(f"missing-field:{name}", f"去会话操作缺少「{name}」"))
        out[key] = (_item(value) if key == "relatedItem" else value) or None
    return kind, out


def parse(text: str) -> Message:
    tags, end, reply_to, body = _split(text or "")
    kind = "unknown"
    markers: list[tuple[str, int]] = []
    problems: list[Issue] = []
    for tag in tags:
        tag = tag.strip()
        if tag in KIND_TAGS and kind == "unknown":
            kind = KIND_TAGS[tag]
        elif tag.startswith("取代"):
            n = _item(tag)
            markers.append(("supersede", n)) if n else problems.append(
                Issue("missing-field:取代编号", "「取代」标签缺少 #编号"))
        elif tag.startswith("与") and tag.endswith("并行"):
            n = _item(tag)
            markers.append(("parallel", n)) if n else problems.append(
                Issue("missing-field:并行编号", "「并行」标签缺少 #编号"))
    fields = _fields(kind, body)
    item = None
    hints: list[Issue] = []
    conclusion = None
    options: tuple[Option, ...] = ()
    recommended = None
    stopped = None
    in_scope: tuple[str, ...] = ()
    scopes: dict[str, str] = {}
    decisions: tuple[Decision, ...] = ()
    receipt = None
    local_item = None
    artifacts: tuple[Artifact, ...] = ()
    originals: dict[str, tuple[OriginalRef, ...]] = {}
    wait_kind, go_to_session, points = None, None, ()

    if kind == "unknown":
        problems.append(Issue("unknown-kind", "认不出消息类型"))
    elif kind == "wait-user":
        if not end.present:
            problems.append(Issue("missing-end", "开头缺少「结束：#编号」或「结束：无」"))
        _require(fields, ("来自", "要你决定"), problems)
        brief = fields.get("要点", "")
        if (len([x for x in brief.splitlines() if x.strip()]) < 2
                or any(word in brief for word in THIN_BRIEF_WORDS)):
            hints.append(Issue("brief-thin", "要点太简略，用户可能没法直接决定，见协作规则段里的要点写法"))
        options, recommended = _options(fields.get("选项与我的建议", ""))
        if not options:
            problems.append(Issue("missing-options", "「选项与我的建议」里没有带字母的选项"))
        flag = fields.get("是否完全停住", "").strip()
        if not flag:
            problems.append(Issue("missing-field:是否完全停住", "缺少「是否完全停住」"))
        elif flag in ("是", "否"):
            stopped = flag == "是"
        else:
            problems.append(Issue("bad-stop-flag", f"「是否完全停住」只能写「是」或「否」，现在是「{flag}」"))
        for o in options:
            if o.consequence is None:
                hints.append(Issue(f"no-consequence:{o.letter}", f"选项 {o.letter} 没写「选了会怎样」"))
        if options and recommended is None:
            hints.append(Issue("no-recommendation", "提出方没写推荐哪个"))
        if fields.get("适用会话", "").strip():
            in_scope = tuple(x for x in _SESSION_SEP.split(fields["适用会话"].strip()) if x)
            if not fields.get("各线范围", "").strip():
                problems.append(Issue("missing-field:各线范围", "写了「适用会话」却没写「各线范围」"))
            else:
                scopes = _scopes(fields["各线范围"])
                for name in in_scope:
                    if not scopes.get(name, "").strip():
                        problems.append(Issue(f"scope-missing:{name}", f"「各线范围」缺少写给 {name} 的一条"))
                for name in scopes:
                    if name not in in_scope:
                        problems.append(Issue(f"scope-unknown:{name}", f"「各线范围」里的 {name} 不在「适用会话」中"))
        artifacts = _artifacts(fields.get("产物", ""), problems)
        originals = {"submission": _original_refs("交审原文", fields.get("交审原文", ""), problems),
                     "conclusion": _original_refs("审查原文", fields.get("审查原文", ""), problems)}
        wait_kind, go_to_session = _go_to_session(fields, problems)
        points = _points(wait_kind, fields.get("要点", ""))
        if "待用户决定" in fields:
            decisions = _decisions(fields["待用户决定"], problems)
    elif kind == "wait-session":
        if not end.present:
            problems.append(Issue("missing-end", "开头缺少「结束：#编号」或「结束：无」"))
        _require(fields, ("在等谁", "等什么"), problems)
    elif kind == "resumed":
        if not (end.ids or end.unnumbered_reason):
            problems.append(Issue("missing-end", "【已恢复】开头要写「结束：#编号」或「结束：无编号（原因）」"))
    elif kind == "user-reply":
        local = LOCAL_ITEM_RE.match(fields.get("事项", ""))
        if local:  # v2.0: no hub, the coordinator's own C-number; the mail id in brackets is not an item
            local_item = local.group(1)
        item = None if local else _item(fields.get("事项"))
        if item is None and local is None:
            problems.append(Issue("missing-field:事项", "缺少「事项：#编号」"))
        _require(fields, ("用户原话", "答复时间"), problems)
        if "多线事项" in fields.get("事项", ""):
            _require(fields, ("适用于你的范围", "原事项全文"), problems)
    elif kind == "review-conclusion":
        before = len(problems)
        verdict = _verdict(fields.get("结论", "")) if fields.get("结论", "").strip() else None
        counted = verdict is not None and verdict[0] == "changes-required" and verdict[1] is not None
        _require(fields, ("审查编号", "节点", "送审方", "结论") + (("须修改",) if counted else ()), problems)
        base_ok = not any(p.code.removeprefix("missing-field:") in ("审查编号", "节点", "送审方", "结论")
                          for p in problems[before:])
        node = REVIEW_NODES.get(fields.get("节点", "").strip())
        if fields.get("节点", "").strip() and node is None:
            problems.append(Issue("bad-node", "「节点」只能是 Spec、Plan、接口提案、最终验收之一"))
        if fields.get("结论", "").strip() and verdict is None:
            problems.append(Issue("bad-verdict", "「结论」只能是 通过、通过，附建议N条、有须修改项之一"))
        changes = None
        if verdict is not None and verdict[0] == "changes-required" and (counted or "须修改" in fields):
            changes = tuple(m.group(1).strip() for m in (_CHANGE_RE.match(x.strip())
                                                         for x in fields.get("须修改", "").split("\n")) if m)
            if counted and "须修改" in fields and len(changes) != verdict[1]:
                problems.append(Issue("change-count-mismatch",
                                      f"「有须修改项{verdict[1]}条」与「须修改」的 {len(changes)} 条对不上"))
            if not counted:
                hints.append(Issue("change-count-missing", "「有须修改项」没写条数，写成「有须修改项N条」"))
        if "待用户决定" in fields:
            decisions = _decisions(fields["待用户决定"], problems)
        if base_ok and node is not None and verdict is not None:
            conclusion = Conclusion(fields["审查编号"].strip(), node, fields["送审方"].strip(), verdict[0],
                                    None if verdict[0] == "changes-required" else verdict[1],
                                    module=fields.get("模块", "").strip() or None,
                                    change_count=verdict[1] if verdict[0] == "changes-required" else None,
                                    changes=changes)
    elif kind == "withdraw":
        item = _item(fields.get("事项"))
        if item is None:
            problems.append(Issue("missing-field:事项", "缺少「事项：#编号」"))
    elif kind == "hub-receipt":
        _require(fields, ("原消息", "事项", "状态"), problems)
        item = _item(fields.get("事项"))
        status = fields.get("状态", "").strip()
        if status and status != "已登记":
            problems.append(Issue("bad-receipt-status", f"「状态」只能写「已登记」，现在是「{status}」"))
        receipt = Receipt(_item(fields.get("原消息")), "registered" if status == "已登记" else None,
                          tuple(int(x) for x in _NUM_RE.findall(fields.get("取代", ""))))

    task = None
    if kind in ("wait-user", "review-conclusion") and "任务" in fields:  # v2.5, reported after the kind's own codes
        written = fields["任务"].strip()
        if _TASK_RE.match(written):
            task = written
        else:
            problems.append(Issue("bad-task-ref", f"「任务」要写成大写 T 加数字（如 T3），现在是「{written}」"))
        if fields.get("模块", "").strip() not in ("", "无"):
            problems.append(Issue("module-task-both", "「模块」「任务」只能写一个：轻任务写「任务」，「模块」不写或写「无」"))

    return Message(kind=kind, markers=tuple(markers), ends=end, reply_to=reply_to,
                   fields=fields, item=item, problems=tuple(problems), hints=tuple(hints),
                   options=options, recommended=recommended,
                   suggested_reply=fields.get("你该回") or None, fully_stopped=stopped,
                   lines_in_scope=in_scope, scopes=scopes,
                   review=_review(fields.get("架构审查")) if kind == "wait-user" else ReviewLine("absent"),
                   conclusion=conclusion, decisions=decisions, receipt=receipt, local_item=local_item,
                   artifacts=artifacts, originals=originals, wait_kind=wait_kind, go_to_session=go_to_session,
                   points=points, module=(fields.get("模块") or "").strip() or None if kind == "wait-user" else None,
                   task=task)


def _source(relay_id) -> str:
    """The proposer's own agent-relay id: it only knows that one, not the hub's item number (e2e-round1-fixes F1)."""
    return "" if relay_id is None else f"原消息 #{relay_id}"


def format_user_reply(item: int, original: str, answered_at: str, option_text: str | None = None,
                      source_relay_id=None) -> str:
    """【用户答复】 to the proposer; the user's words are copied unchanged (requirement 6.4)."""
    head = f"事项：#{item}" if source_relay_id is None else f"事项：#{item}（你的{_source(source_relay_id)}）"
    lines = ["【用户答复】", head, f"用户原话：{original}"]
    if option_text is not None:
        m = _OPTION_RE.match(option_text.strip())
        if not m:
            raise ValueError(f"option_text must start with an option letter: {option_text!r}")
        lines.append(f"选项 {m.group(2)} 原文：{option_text}")
    lines.append(f"答复时间：{answered_at}")
    return "\n".join(lines) + "\n"


def format_hub_receipt(original, item: int, supersedes=(), notes=()) -> str:
    """【登记回执】 (v2.0): sent silently, never as a reply, so the sender's request stays open."""
    lines = ["【登记回执】", f"原消息：#{original}", f"事项：#{item}", "状态：已登记"]
    if supersedes:
        lines.append("取代：" + "、".join(f"#{n}" for n in supersedes))
    if notes:
        lines.append("写法提示：" + "；".join(notes))
    return "\n".join(lines) + "\n"


def legacy_head(text: str, item: int, relay_id, multi_sender: str | None = None) -> str:
    """Swap the 事项 line for the numbering the old hand-written hub used (transition-compat).

    Lines not migrated yet only check the first number against their own message id.
    """
    origin = f"多线事项，发起方 {multi_sender}；hub 编号 {item}" if multi_sender else f"hub 编号 {item}"
    lines = text.split("\n")
    at = next(i for i, line in enumerate(lines) if line.startswith("事项："))
    lines[at] = f"事项：#{relay_id}（{origin}）"
    return "\n".join(lines)


def format_answer_notice(item: int, owner_short: str, original: str, answered_at: str,
                         source_relay_id=None) -> str:
    """【答复告知】 to an owner's dev lines: information only, never an approval (answer-handoff-gaps)."""
    origin = f"由{owner_short}抛出" + ("" if source_relay_id is None else f"，{_source(source_relay_id)}")
    return "\n".join(["【答复告知】", f"事项：#{item}（{origin}）", f"用户原话：{original}",
                      f"答复时间：{answered_at}",
                      "说明：这条只是告知，不是批准，不作执行依据；等负责人转交后，按转交的范围执行。"]) + "\n"


def format_multiline_replies(item: int, sender: str, original: str, answered_at: str,
                             wait_user_text: str, source_relay_id=None) -> dict[str, str]:
    """One 【用户答复】 per session in 适用会话, each with its own scope (requirement 4.4)."""
    source = parse(wait_user_text)
    if source.kind != "wait-user" or not source.ok or not source.lines_in_scope:
        raise ValueError("wait_user_text must be a valid multi-line 【等待用户】")
    full = wait_user_text.rstrip("\n")
    origin = f"多线事项，发起方：{sender}" + ("" if source_relay_id is None else f"，{_source(source_relay_id)}")
    return {
        line: "\n".join([
            "【用户答复】",
            f"事项：#{item}（{origin}）",
            f"用户原话：{original}",
            f"适用于你的范围：{source.scopes[line]}",
            f"答复时间：{answered_at}",
            "原事项全文：",
            full,
        ]) + "\n"
        for line in source.lines_in_scope
    }
