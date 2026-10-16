"""The hub's main view and expanded views (see spec/hub-view.md).

Layout only: states and signals come from line-health, items from
decision-queue, tickets from wait-tickets. Nothing here judges or writes.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime

from decision_inbox import items, store, tickets

RECENT_MINUTES = 10
OPTION_CHARS = 30
TOPIC_CHARS = 20
FORWARDED = ("forwarded", "picked", "acknowledged", "closed")
INVALIDATED = ("superseded", "withdrawn")


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _minutes(now: str, then: str) -> int:
    return max(0, int((_instant(now) - _instant(then)).total_seconds() // 60))


def ago(now: str, then: str) -> str:
    minutes = _minutes(now, then)
    if minutes < 60:
        return f"{minutes} 分钟前"
    if minutes < 24 * 60:
        return f"{minutes // 60} 小时前"
    return f"{minutes // (24 * 60)} 天前"


def clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def copy_line(no: int, letter: str, reply: str | None) -> str:
    """Decided format 8: never repeat the letter the reply already starts with."""
    if not reply:
        return f"{no} {letter}"
    if reply.startswith(letter) and reply[len(letter):len(letter) + 1] in ("", " ", ":", "："):
        return f"{no} {reply}"
    return f"{no} {letter} {reply}"


def _short(g: store.Group, relay_name: str) -> str:
    return (store.find_session(g, relay_name=relay_name) or {}).get("shortName", relay_name)


def _today(now: str) -> str:
    return _instant(now).astimezone().date().isoformat()


def _push_line(g: store.Group, now: str, assessment) -> str | None:
    """Decided format 5: the session waited on most that itself waits for nobody."""
    if not any(s.no == 1 for s in assessment.signals):
        return None
    open_ = tickets.open_tickets(g, now)
    if not open_:
        return None
    on_sessions = [t for t in open_ if t.target not in tickets.USER_TARGETS]
    waiting = {_short(g, t.waiter) for t in on_sessions}
    counts = Counter(t.target for t in on_sessions if t.target not in waiting)
    ranked = counts.most_common(2)
    if ranked and (len(ranked) == 1 or ranked[0][1] > ranked[1][1]):
        where = f"卡在 {ranked[0][0]}"
    else:
        where = "卡在哪见 /flow"
    return f"⚠ 全线停住 {max(t.minutes for t in open_)} 分钟：{where}"


def _lines_row(g: store.Group, assessment) -> str | None:
    parts = []
    for entry in store.roster(g):
        state = assessment.lines.get(entry["relayName"])
        if state is not None:
            parts.append(f"{entry['shortName']} {state.text.replace('阻塞：等 ', '阻塞：等')}")
    return " · ".join(parts) or None


def _needs_user(g: store.Group, assessment) -> list[str]:
    return [e["relayName"] for e in store.roster(g)
            if getattr(assessment.lines.get(e["relayName"]), "word", None) == "needs-user"]


def _anomalies(assessment) -> list:
    return [s for s in assessment.signals if s.no != 1]


def _overview(g: store.Group, now: str, assessment) -> str:
    decide = len(items.pending(g)) + len(_needs_user(g, assessment))
    text = f"等你决定 {decide} 项 · 异常 {len(_anomalies(assessment))}"
    recent = [it for it in items.by_status(g, *FORWARDED)
              if _minutes(now, it["statusAt"]["forwarded"]) <= RECENT_MINUTES]
    if recent:
        recent.sort(key=lambda it: _instant(it["statusAt"]["forwarded"]))
        text += " · 刚转达：" + "、".join(
            f"{it['no']} → {'＋'.join(_short(g, r) for r in it['recipients'])}" for it in recent)
    return text


def _footer(g: store.Group, now: str) -> str:
    count = tickets.counts(g, _today(now))
    invalid = len(items.by_status(g, *INVALIDATED))
    return f"等待中 {count['open']} 单 · 已失效 {invalid} 项 · 今天已关 {count['closed_today']} 单"


def _confirm_card(g: store.Group, now: str, relay_name: str, relay) -> str:
    """Decided format 4: a host permission prompt waiting in the session itself."""
    short = _short(g, relay_name)
    fact = relay.agents.get(relay_name) if relay is not None else None
    title = f"━━ 去原会话确认 · {short}"
    if fact is not None and fact.presence_since:
        title += f" · {ago(now, fact.presence_since)}"
    detail = f"（{fact.presence_detail}）" if fact is not None and fact.presence_detail else ""
    return f"{title}\n要你做：打开「{short}」会话，确认它弹出的请求{detail}"


def _source(g: store.Group, it: dict) -> str:
    return f"多线：{'＋'.join(it['lines'])}" if it["multi"] else _short(g, it["sender"])


def _review_lines(it: dict) -> list[str]:
    review = it["review"]
    label = f"**{review['text']}**" if review.get("highlight") else review["text"]
    out = [f"审查：{label} · 详情：{it['no']} 详情"]
    if review.get("warn"):
        out += [f"  正文提到：{m}" for m in review.get("mentions", [])]
    return out


def _item_card(g: store.Group, now: str, it: dict) -> str:
    no = it["no"]
    topic = clip(it["decide"].split("\n")[0], TOPIC_CHARS)
    title = f"━━ {no} · {_source(g, it)} · {topic} · {ago(now, it['receivedAt'])}"
    if it["blocks"]:
        title += f" · 挡住 {it['blocks']} 条线"
    out = [title, f"要你决定：{it['decide']}"]
    options = it["options"]
    rec = next((o for o in options if o["letter"] == it["recommended"]), None)
    if rec is not None:
        options = [rec] + [o for o in options if o is not rec]
    for o in options:
        first = clip(o["text"].split("\n")[0], OPTION_CHARS)
        out.append(f"推荐 {o['letter']}：{first}" if o is rec else f"{o['letter']}：{first}")
        out.append(f"  选了会怎样：{o['consequence'] or '提出方未说明后果'}")
        if o is rec:
            out += ["```", copy_line(no, o["letter"], it["suggestedReply"]), "```"]
        else:
            out.append(f"  回 {no} {o['letter']}")
    return "\n".join(out + _review_lines(it))


def _cards(g: store.Group, now: str, assessment, relay) -> list[str]:
    confirms = [_confirm_card(g, now, name, relay) for name in _needs_user(g, assessment)]
    return confirms + [_item_card(g, now, it) for it in items.pending(g)]


def render(g: store.Group, now: str, assessment, relay=None) -> str:
    """Main view, fixed order (requirement 6.1): push, lines, overview, anomalies, cards, counts."""
    head = [line for line in (_push_line(g, now, assessment), _lines_row(g, assessment)) if line]
    head.append(_overview(g, now, assessment))
    sections = ["\n".join(head), *_cards(g, now, assessment, relay), _footer(g, now)]
    return "\n\n".join(sections)
