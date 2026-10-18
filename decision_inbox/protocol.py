"""Parse and validate the hand-written inbox messages (see spec/message-protocol.md).

Writing is lenient (either colon width, values spanning lines); judging is
strict (a required field that cannot be found is a problem, never guessed).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

KIND_TAGS = {
    "等待用户": "wait-user",
    "用户答复": "user-reply",
    "等待其他会话": "wait-session",
    "已恢复": "resumed",
    "撤回": "withdraw",
    "审查结论": "review-conclusion",
}

# Field names each kind knows, in the order they are usually written.
FIELDS = {
    "wait-user": ("来自", "项目", "要你决定", "要点", "架构审查", "选项与我的建议", "你该回",
                  "是否完全停住", "适用会话", "各线范围"),
    "user-reply": ("事项", "用户原话", "选项原文", "适用于你的范围", "答复时间", "原事项全文"),
    "wait-session": ("在等谁", "等什么"),
    "resumed": (),
    "withdraw": ("事项", "原因"),
    "review-conclusion": ("审查编号", "节点", "模块", "送审方", "结论", "来自", "要点"),
    "unknown": (),
}
# A terminal field takes every remaining line, whatever it looks like.
TERMINAL = {"原事项全文"}

# Stable issue codes (spec 关键决策 5): only ever added to. A trailing ":" takes a suffix.
PROBLEM_CODES = ("unknown-kind", "missing-end", "missing-field:", "missing-options", "bad-stop-flag",
                 "scope-missing:", "scope-unknown:", "bad-node", "bad-verdict")
REVIEW_NODES = {"Spec": "spec", "Plan": "plan", "接口提案": "interface", "最终验收": "final"}
HINT_CODES = ("no-consequence:", "no-recommendation", "brief-thin")

_TAG_RE = re.compile(r"【([^】]*)】")
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


def _verdict(raw: str) -> tuple[str, int | None] | None:
    value = raw.strip().replace(",", "，").replace("(", "（").replace(")", "）")
    if value == "通过":
        return "passed", None
    if value == "有须修改项":
        return "changes-required", None
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

    if kind == "unknown":
        problems.append(Issue("unknown-kind", "认不出消息类型"))
    elif kind == "wait-user":
        if not end.present:
            problems.append(Issue("missing-end", "开头缺少「结束：#编号」或「结束：无」"))
        _require(fields, ("来自", "要你决定"), problems)
        brief = fields.get("要点", "")
        if (len([x for x in brief.splitlines() if x.strip()]) < 2
                or any(word in brief for word in THIN_BRIEF_WORDS)):
            hints.append(Issue("brief-thin", "要点太简略，用户可能没法直接决定，见约定块里的要点写法"))
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
    elif kind == "wait-session":
        if not end.present:
            problems.append(Issue("missing-end", "开头缺少「结束：#编号」或「结束：无」"))
        _require(fields, ("在等谁", "等什么"), problems)
    elif kind == "resumed":
        if not (end.ids or end.unnumbered_reason):
            problems.append(Issue("missing-end", "【已恢复】开头要写「结束：#编号」或「结束：无编号（原因）」"))
    elif kind == "user-reply":
        item = _item(fields.get("事项"))
        if item is None:
            problems.append(Issue("missing-field:事项", "缺少「事项：#编号」"))
        _require(fields, ("用户原话", "答复时间"), problems)
        if "多线事项" in fields.get("事项", ""):
            _require(fields, ("适用于你的范围", "原事项全文"), problems)
    elif kind == "review-conclusion":
        before = len(problems)
        _require(fields, ("审查编号", "节点", "送审方", "结论"), problems)
        node = REVIEW_NODES.get(fields.get("节点", "").strip())
        if fields.get("节点", "").strip() and node is None:
            problems.append(Issue("bad-node", "「节点」只能是 Spec、Plan、接口提案、最终验收之一"))
        verdict = _verdict(fields.get("结论", "")) if fields.get("结论", "").strip() else None
        if fields.get("结论", "").strip() and verdict is None:
            problems.append(Issue("bad-verdict", "「结论」只能是 通过、通过，附建议N条、有须修改项之一"))
        if len(problems) == before:
            conclusion = Conclusion(fields["审查编号"].strip(), node, fields["送审方"].strip(), *verdict,
                                    module=fields.get("模块", "").strip() or None)
    elif kind == "withdraw":
        item = _item(fields.get("事项"))
        if item is None:
            problems.append(Issue("missing-field:事项", "缺少「事项：#编号」"))

    return Message(kind=kind, markers=tuple(markers), ends=end, reply_to=reply_to,
                   fields=fields, item=item, problems=tuple(problems), hints=tuple(hints),
                   options=options, recommended=recommended,
                   suggested_reply=fields.get("你该回") or None, fully_stopped=stopped,
                   lines_in_scope=in_scope, scopes=scopes,
                   review=_review(fields.get("架构审查")) if kind == "wait-user" else ReviewLine("absent"),
                   conclusion=conclusion)


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
