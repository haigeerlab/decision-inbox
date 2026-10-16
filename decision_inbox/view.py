"""The hub's main view and expanded views (see spec/hub-view.md).

Layout only: states and signals come from line-health, items from
decision-queue, tickets from wait-tickets. Nothing here judges or writes.
"""

from __future__ import annotations

import re
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


_ADVICE = {
    3: "问 {who} 是否卡住，或让它继续或上抛",
    4: "打开 {who} 让它恢复",
    5: "先等它做完这一轮；要插队就去它的会话说明",
    6: "看挂起原因是否已经解决",
    7: "看一下这次审查的分歧点",
    8: "问 {who} 进展，或交负责人跟进",
    9: "确认旧等待是否还需要，不需要就说「关掉 #{ticket}」",
    10: "在 Codex 里点开 {who} 让它加载",
}


def _anomaly_row(g: store.Group, signal) -> str:
    """Signal advice table: who, where it is stuck, what to do."""
    who = _short(g, signal.sessions[0]) if signal.sessions else "?"
    if signal.no == 2:
        target = _short(g, signal.sessions[1])
        return (f"- {who}：交付了没人接——{target} 已发消息给 {who}，{who} 还没去取。"
                f"建议：提醒 {who} 去取{target}的交付")
    found = re.search(r"等待单 #(\d+)", signal.text)
    advice = _ADVICE[signal.no].format(who=who, ticket=found.group(1) if found else "编号")
    return f"- {who}：{signal.text}。建议：{advice}"


def _anomaly_section(g: store.Group, assessment) -> str | None:
    rows = [_anomaly_row(g, s) for s in _anomalies(assessment)]
    return "\n".join(["异常", *rows]) if rows else None


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
    sections = ["\n".join(head), _anomaly_section(g, assessment), *_cards(g, now, assessment, relay),
                _footer(g, now)]
    return "\n\n".join(s for s in sections if s)


CLOSE_REASONS = {1: "对方明说结束", 2: "被取代", 3: "所等的事已发生", 4: "用户关闭"}


def _one_line(text: str) -> str:
    return "".join(part.strip() for part in text.split("\n"))


def _clock(value: str) -> str:
    return _instant(value).astimezone().strftime("%H:%M")


def render_detail(g: store.Group, item: int) -> str:
    """「编号 详情」: full text, line scopes and agent-relay message ids."""
    it = items.get(g, item)
    if it is None:
        return f"#{item} 不存在"
    out = [f"#{item} 详情 · {_source(g, it)} · 收到于 {_clock(it['receivedAt'])}",
           f"agent-relay 消息编号：{it['relayId']}"]
    if it["sent"]:
        out.append("答复发送编号：" + "、".join(f"{_short(g, s['to'])} #{s['relayId']}" for s in it["sent"]))
    out += [f"各线范围：{name}：{_one_line(it['scopes'][name])}" for name in it["lines"] if name in it["scopes"]]
    return "\n".join(out + ["原文：", it["text"].rstrip("\n")])


def _ticket_head(g: store.Group, waiter: str, target: str, what: str) -> str:
    return f"{_short(g, waiter)} 等 {target}：{_one_line(what)}"


def render_waits(g: store.Group, now: str, relay=None) -> str:
    """「看等待」: one line per open ticket with wait-tickets' marks."""
    rows = []
    for t in tickets.open_tickets(g, now, relay):
        parts = [f"#{t.no} {_ticket_head(g, t.waiter, t.target, t.what)}"]
        if "waited" not in t.marks:
            parts.append(f"已等 {t.minutes} 分钟")
        rows.append(" · ".join(parts + [_one_line(n) for n in t.notes]))
    return "\n".join(rows) or "没有开着的等待单"


def render_closed(g: store.Group, day: str) -> str:
    """「看已关闭」: tickets closed on `day` with reason and basis."""
    rows = [f"#{t['no']} {_ticket_head(g, t['waiter'], t['target'], t['what'])} · "
            f"{CLOSE_REASONS.get(t['close']['reason'], t['close']['reason'])} · 依据：{t['close']['basis']} · "
            f"{_clock(t['close']['at'])} 关"
            for t in tickets.closed_on(g, day)]
    return "\n".join(rows) or f"{day} 没有关闭的等待单"


def render_invalidated(g: store.Group) -> str:
    """「看失效」: superseded and withdrawn items, one line each."""
    rows = []
    for it in items.by_status(g, *INVALIDATED):
        events = {e["type"]: e.get("data", {}) for e in items.history(g, it["no"])}
        if it["status"] == "superseded":
            state = f"已取代（被 #{events.get('items.superseded', {}).get('by', '?')} 取代）"
        else:
            reason = events.get("items.withdrawn", {}).get("reason")
            state = f"已撤回（{reason}）" if reason else "已撤回 "
        topic = clip(it["decide"].split("\n")[0], TOPIC_CHARS)
        rows.append(f"#{it['no']} {state}· {_source(g, it)} · {topic}")
    return "\n".join(rows) or "没有失效的事项"
