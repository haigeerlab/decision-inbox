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
}

# Field names each kind knows, in the order they are usually written.
FIELDS = {
    "wait-user": ("来自", "项目", "要你决定", "要点", "架构审查", "选项与我的建议", "你该回",
                  "是否完全停住", "适用会话", "各线范围"),
    "user-reply": ("事项", "用户原话", "选项原文", "适用于你的范围", "答复时间", "原事项全文"),
    "wait-session": ("在等谁", "等什么"),
    "resumed": (),
    "withdraw": ("事项", "原因"),
    "unknown": (),
}
# A terminal field takes every remaining line, whatever it looks like.
TERMINAL = {"原事项全文"}

_TAG_RE = re.compile(r"【([^】]*)】")
_COLON = "[：:]"
_END_RE = re.compile(rf"^结束\s*{_COLON}\s*(.*)$")
_REPLY_RE = re.compile(rf"^回复\s*{_COLON}\s*#\s*(\d+)\s*$")
_NUM_RE = re.compile(r"#\s*(\d+)")


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
class Message:
    kind: str
    markers: tuple[tuple[str, int], ...]
    ends: EndMark
    reply_to: int | None
    fields: dict[str, str]
    item: int | None
    problems: tuple[Issue, ...]
    hints: tuple[Issue, ...] = field(default=())

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

    if kind == "unknown":
        problems.append(Issue("unknown-kind", "认不出消息类型"))
    elif kind == "wait-session":
        if not end.present:
            problems.append(Issue("missing-end", "开头缺少「结束：#编号」或「结束：无」"))
        _require(fields, ("在等谁", "等什么"), problems)
    elif kind == "resumed":
        if not (end.ids or end.unnumbered_reason):
            problems.append(Issue("missing-end", "【已恢复】开头要写「结束：#编号」或「结束：无编号（原因）」"))
    elif kind == "withdraw":
        item = _item(fields.get("事项"))
        if item is None:
            problems.append(Issue("missing-field:事项", "缺少「事项：#编号」"))

    return Message(kind=kind, markers=tuple(markers), ends=end, reply_to=reply_to,
                   fields=fields, item=item, problems=tuple(problems))
