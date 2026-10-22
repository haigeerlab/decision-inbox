"""Decision cards after the user's template (spec/decision-cards.md; DECISION-CARD-TEMPLATES.md).

A card gives conclusions only: what to decide, the content points picked from what the proposer sent,
who reviewed it, each option with what happens, the recommendation, and one copy block holding the
recommended answer. Originals stay behind 「看 N 全文」. Read-only.
"""

from __future__ import annotations

import re

from decision_inbox import approval, items, protocol, sources

MAX_LINES = 18          # non-empty lines of one card
MAX_POINTS = 6          # content lines kept from 要点
POINT_CHARS = 80
EXAMPLE_CHARS = 60
OPTION_CHARS = 40

# Phase 1 (session-protocol v2.2): the class comes from 类型 and 节点; v2.3 「类型」 joins here later.
KIND_NAMES = {"capability-map": "能力图审阅", "spec": "Spec", "plan": "Plan", "spec-plan": "Spec 与 Plan",
              "checkpoint": "中途检查点",
              "final": "最终验收", "interface": "接口提案", "stuck": "卡住选做法", "go-to-session": "去会话操作"}
_BY_NODE = {"Spec": "spec", "接口提案": "interface", "Plan": "plan", "最终验收": "final"}
APPROVALS = ("capability-map", "spec", "plan", "spec-plan", "checkpoint", "final", "interface")


def kind(it: dict) -> str:
    """One of the template's seven classes (go-to-session, the four nodes, else stuck)."""
    if items.is_go_to_session(it):
        return "go-to-session"
    if it.get("waitKind") in KIND_NAMES:  # session-protocol v2.3 「类型」
        return it["waitKind"]
    return _BY_NODE.get(it.get("approvalNode") or "", "stuck")


# ── content points ────────────────────────────────────────────────────────────

_CRITERIA_HEAD_RE = re.compile(r"^#*\s*验收标准(?:与证据)?\s*[：:]?\s*$")
_LIST_RE = re.compile(r"^(?:[-*•]\s*|\d+\s*[.．、]\s*)")
_NUMBERED_RE = re.compile(r"^[-*•]?\s*\d+\s*[\s.．、（(：:]")
_PASSED_RE = re.compile(r"✔|✅|通过|\bpass(?:ed)?\b", re.I)
_FULL_CHECK_RE = re.compile(r"^[-*•]?\s*完整检查")
_FIELD_LINES = ("产物：", "交审原文：", "审查原文：", "批准会发生什么", "选项与我的建议")


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def _criteria_line(section: list[str]) -> str:
    entries = [line for line in section if _LIST_RE.match(line)]
    criteria = [line for line in entries if _NUMBERED_RE.match(line)] or entries
    passed = [line for line in criteria if _PASSED_RE.search(line)]
    text = f"**验收结果**：验收标准 {len(criteria)} 条，标了通过的 {len(passed)} 条"
    full = next((line for line in entries if _FULL_CHECK_RE.match(line)), None)
    if full:
        text += "；" + _clip(_LIST_RE.sub("", full), 50)
    if criteria:
        text += "；例：" + _clip(_LIST_RE.sub("", criteria[0]), EXAMPLE_CHARS)
    return text


def points(it: dict) -> tuple[list[str], bool]:
    """Content lines picked from 要点 (decision-cards Spec section 2) and whether anything was left out."""
    decide = (it.get("decide") or "").strip()
    lines = [line.strip() for line in (it.get("brief") or "").split("\n")]
    lines = [line for line in lines if line and line != decide and not line.startswith(_FIELD_LINES)]
    out, cut, seen_criteria, i = [], False, False, 0
    while i < len(lines):
        line = lines[i]
        if _CRITERIA_HEAD_RE.match(line):
            section, i = [], i + 1
            while i < len(lines) and _LIST_RE.match(lines[i]):
                section.append(lines[i])
                i += 1
            if not seen_criteria:
                out.append(_criteria_line(section))
                seen_criteria = True
            cut = cut or bool(section)
            continue
        out.append("- " + _clip(_LIST_RE.sub("", line), POINT_CHARS))
        cut = cut or len(_LIST_RE.sub("", line)) > POINT_CHARS
        i += 1
    if len(out) > MAX_POINTS:
        out, cut = out[:MAX_POINTS], True
    return out, cut


_LIST_NAMES = ("验收标准", "验收结果")


def _point_line(name: str, text: str, no: int) -> str:
    """One v2.3 content point: its first line; what runs on is counted and left to 「看 N 全文」."""
    lines = text.split("\n")
    first, rest = _clip(lines[0].strip(), POINT_CHARS), [x.strip() for x in lines[1:] if x.strip()]
    if not rest:
        return f"**{name}**：{first}"
    if name in _LIST_NAMES:
        line = f"**{name}**：{first}" + ("" if f"共 {len(rest)} 条" in first else f"；共 {len(rest)} 条")
        return line + f"；例：{_clip(rest[0], EXAMPLE_CHARS)}" + (f"（其余见「看 {no} 全文」）" if len(rest) > 1 else "")
    return f"**{name}**：{first}（共 {len(lines)} 行，见「看 {no} 全文」）"


def point_lines(it: dict) -> list[str]:
    """v2.3 points in the template's order (section 4); a point written twice keeps both."""
    order = protocol.POINTS.get(kind(it), ())
    ranked = sorted(it.get("points") or (), key=lambda p: order.index(p[0]) if p[0] in order else len(order))
    return [_point_line(name, text, it["no"]) for name, text in ranked]


# ── conclusion and notes ──────────────────────────────────────────────────────

_SENTENCE_RE = re.compile(r"^(.+?[。；!！?？])")


def conclusion(it: dict) -> str:
    """Who reviewed, passed or not, review number, why; from the 审查原文 when it can be read."""
    for ref in (it.get("originals") or {}).get("conclusion", ()):
        got = sources.read_original(ref["path"], ref["fingerprint"])
        if not got.ok:
            continue
        msg = protocol.parse(got.text)
        if msg.kind != "review-conclusion" or msg.conclusion is None:
            continue
        c, fields = msg.conclusion, msg.fields
        who = fields.get("来自", "").strip() or "审查"
        text = f"{who}{'' if who.endswith('审查') else ' 审查'}{fields.get('结论', '').strip()}（{c.ref}）"
        if c.change_count:
            text += f"，须修改 {c.change_count} 条"
        brief = fields.get("要点", "").strip().split("\n")[0]
        if brief:
            m = _SENTENCE_RE.match(brief)
            text += "。" + _clip((m.group(1) if m else brief).rstrip("。；"), EXAMPLE_CHARS)
        return text
    review = it.get("review") or {}
    text = review.get("text") or "未审查"
    return f"**{text}**" if review.get("highlight") else text


def notes(it: dict) -> list[str]:
    """「注意」 as the proposer wrote it (v2.3, 「无」 included), else what the review label found (assumption 3).

    Writing hints go back to the proposer in its 【登记回执】; they are not the user's business (D1 B).
    """
    if it.get("note"):
        return [it["note"]]
    review = it.get("review") or {}
    return [f"正文提到：{m}" for m in review.get("mentions") or ()] if review.get("warn") else []


# ── copy block ────────────────────────────────────────────────────────────────

def _copy_line(no: int, letter: str, reply: str | None) -> str:
    from decision_inbox.view import copy_line
    return copy_line(no, letter, reply)


def recommended(it: dict) -> dict | None:
    return next((o for o in it["options"] if o["letter"] == it.get("recommended")), None)


def copy_text(it: dict) -> str:
    """The card's one copy block: the recommended answer, D answers by the review's lean in the same line."""
    rec = recommended(it)
    if rec is not None:
        line = _copy_line(it["no"], rec["letter"], it.get("suggestedReply"))
    else:
        line = f"{it['no']} {it['options'][0]['letter']}" if it["options"] else f"{it['no']} 原话：你的话"
    for d in it.get("decisions") or ():
        if d.get("lean") and not re.search(rf"(?<![A-Za-z0-9]){d['id']}(?![0-9])", line):
            line += f"；{d['id']} {d['lean']}"
    return line


def _copy_block(it: dict) -> list[str]:
    out = [] if recommended(it) is not None else ["提出方没写推荐，下面只是写法示例："]
    line = copy_text(it)
    out += ["```", line, "```"]
    missing = [d["id"] for d in it.get("decisions") or ()
               if not re.search(rf"(?<![A-Za-z0-9]){d['id']}(?![0-9])", line)]
    if missing:
        out.append(f"还要答 {'、'.join(missing)}，写在同一条回复里")
    return out


# ── cards ─────────────────────────────────────────────────────────────────────

def _option_lines(it: dict) -> list[str]:
    rec = recommended(it)
    out = []
    for o in sorted(it["options"], key=lambda o: o["letter"]):
        label = _clip(o["text"].split("\n")[0], OPTION_CHARS)
        line = f"**{o['letter']} {label}**：{o['consequence'] or '提出方未说明后果'}"
        if o is not rec:
            line += f"。答复写法：回 {it['no']} {o['letter']}" + ("：你的意见" if "意见" in o["text"] else "")
        out.append(line)
    return out


def _decision_lines(it: dict) -> list[str]:
    out = []
    for d in it.get("decisions") or ():
        choices = "　".join(f"{letter}. {text}" for letter, text in d["options"])
        lean = f"（审查倾向 {d['lean']}）" if d.get("lean") else ""
        out.append(f"**{d['id']}** {d['question']} {choices}{lean}")
    return out


def _recommend_line(it: dict) -> str | None:
    rec = recommended(it)
    if rec is None:
        return None
    leans = "".join(f"；{d['id']} 选 {d['lean']}" for d in it.get("decisions") or () if d.get("lean"))
    return f"**推荐 {rec['letter']}{leans}**" + (f"：{it['reason']}" if it.get("reason") else "")


def _topic(it: dict, k: str) -> str:
    if k in APPROVALS and it.get("approvalModule"):
        return f"{it['approvalModule']} 的 {KIND_NAMES[k]}，批不批"
    return _clip((it.get("decide") or "").split("\n")[0], 40)


def head(it: dict, k: str, waited: str, extra: str = "") -> str:
    line = f"**#{it['no']} · {_topic(it, k)}** · 等了 {waited}"
    if it.get("blocks"):
        line += f" · 挡住 {it['blocks']} 条线"
    return line + extra


# Points per template (session-protocol v2.3); v2.6 only renamed points or added two to the Plan, which a card
# that uses them brings along in its own points.
_TEMPLATE_SIZE = {"capability-map": 3, "spec": 5, "plan": 4, "spec-plan": 9, "checkpoint": 3, "final": 4,
                  "interface": 7, "stuck": 1}


def max_lines(k: str, points=()) -> int:
    """MAX_LINES, plus one line per point beyond five (Spec 与 Plan has nine, 接口提案 seven; more when written)."""
    return MAX_LINES + max(0, max(_TEMPLATE_SIZE.get(k, 0), len(points or ())) - 5)


def _fit(top: list[str], content: list[str], cut: bool, rest: list[str], no: int, limit: int = MAX_LINES) -> list[str]:
    """Drop content lines until the card fits `limit`; anything left out points to 「看 N 全文」."""
    more = f"其余见：回「看 {no} 全文」"
    while True:
        tail = [more] if cut else []
        card = top + content + tail + rest
        if len([x for x in card if x.strip()]) <= limit or not content:
            return card
        content, cut = content[:-1], True


def render(g, it: dict, waited: str, line_name: str) -> str:
    """One card of class 1～6 (class 7 goes through go_to_session)."""
    k = kind(it)
    content, cut = points(it)
    if k in APPROVALS:
        rounds, last = approval.rounds(g, it)
        where = [x for x in (it.get("project"), line_name) if x]
        # session-protocol v2.5: a light task's card names the task instead of a module
        where.append(f"任务 {it['task']}" if it.get("task") else f"模块 {it.get('approvalModule') or '未知'}")
        label = f"{KIND_NAMES[k]}（第 {rounds} 次交审" + (f"；上次你答：{last}" if last else "") + "）"
        top = [head(it, k, waited), " · ".join(where + [label]), ""]
        if it.get("points"):  # session-protocol v2.3: the template's own items replace the picked lines
            content, cut = point_lines(it), False
        else:
            content = (["**内容要点**："] if content else []) + content
        effect = [f"**批了会怎样**：{it['approveEffect']}"] if it.get("approveEffect") else []
        rest = [*effect, "", f"**结论**：{conclusion(it)}"]
    else:
        where = " · ".join(x for x in (it.get("project"), line_name) if x)
        top = [head(it, k, waited), *([where] if where else []), ""]
        content = (["**出了什么事**："] if content else []) + content
        review = it.get("review") or {}
        rest = [f"**结论**：{conclusion(it)}"] if review.get("ref") or review.get("highlight") or review.get("warn") \
            else []
    if found := notes(it):
        rest.append("**注意**：" + "；".join(found))
    rest += ["", *_decision_lines(it), *_option_lines(it)]
    if rec := _recommend_line(it):
        rest += ["", rec]
    rest += ["", *_copy_block(it)]
    return "\n".join(_fit(top, content, cut, rest, it["no"], max_lines(k, it.get("points"))))


def go_to_session(it: dict, waited: str, where: str, remind: bool) -> str:
    """Class 7: nothing to answer, so no copy block."""
    gts = it["goToSession"]
    title = f"**#{it['no']} · 去 {gts['session']} 点一下弹窗** · 等了 {waited}"
    if remind:
        title += "（再提醒一次）"
    first = next((x.strip() for x in (it.get("brief") or "").split("\n") if x.strip()), "")
    lines = [title, _clip(first, POINT_CHARS) if first else None, f"被拦的操作：{gts['blockedAction']}",
             f"点：{gts['button']}", f"为什么这里批不了：{gts['reason']}"]
    if gts.get("hostText"):
        lines.append(f"宿主原文：{gts['hostText']}")
    lines.append(where)
    if gts.get("relatedItem"):
        lines.append(f"你在 #{gts['relatedItem']} 已同意，只差宿主这一下")
    lines.append("点完不用回复，会自动结项。")
    return "\n".join(x for x in lines if x)


def combined(pending: list[dict]) -> str | None:
    """「一次答完」 over every card with a recommendation, approvals and D answers included (DI-2)."""
    answerable = [it for it in pending if not items.is_go_to_session(it)]
    picks = [copy_text(it) for it in answerable if recommended(it) is not None]
    if len(picks) < 2:
        return None
    # one line when no answer carries a separator, else one per line (the parser splits lines first)
    joined = "\n".join(picks) if any(re.search(r"[，；;,\n]", p) for p in picks) else "，".join(picks)
    out = ["一次答完（全按推荐）：", "```", joined, "```"]
    out += [f"#{it['no']} 没有推荐，要单独回" for it in answerable if recommended(it) is None]
    return "\n".join(out)
