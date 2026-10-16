"""The hub session's main loop: receive, reply, record sends (see spec/hub-loop.md).

The hub session only calls agent-relay and carries out what these functions
return; every judgement and every record lives here or in the modules they
call. The `hub` domain is written only by this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from decision_inbox import items, protocol, reviews, store, tickets

DOMAIN = "hub"
BRIDGE = "bridge"  # agent-relay's automated notices (never answered)
KIND_LABELS = {"wait-session": "等待其他会话", "resumed": "已恢复", "review-conclusion": "审查结论"}


@dataclass
class Receipt:
    sends: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    ack: list = field(default_factory=list)
    unread: list = field(default_factory=list)
    more: bool = False


def _doc(tx) -> dict:
    doc = tx.read_state(DOMAIN)
    for key in ("received", "outgoing", "unknown"):
        doc.setdefault(key, {})
    doc.setdefault("nextOut", 1)
    return doc


def _short(g: store.Group, relay_name: str) -> str:
    return (store.find_session(g, relay_name=relay_name) or {}).get("shortName", relay_name)


def _first_line(text: str) -> str:
    return next((line.strip() for line in text.split("\n") if line.strip()), "")


def _return_text(label: str, problems) -> str:
    """Same wording as decision-queue's return note, for the other message kinds."""
    lines = [f"退回：你的【{label}】没有处理，原因："]
    lines += [f"- {p.text}" for p in problems]
    lines.append("请补全后重新发送。")
    return "\n".join(lines)


def _queue(g: store.Group, tx, doc: dict, to: str, text: str, reply_to, kind: str, item, at: str) -> dict:
    """Keep one message to send; its body goes to a file the hub sends unchanged (bodyFile)."""
    n = doc["nextOut"]
    doc["nextOut"] = n + 1
    folder = g.path / "outgoing"
    folder.mkdir(mode=0o700, exist_ok=True)
    path = folder / f"{n}.txt"
    store._atomic_write_bytes(path, text.encode("utf-8"))
    out_id = f"out:{n}"
    doc["outgoing"][out_id] = {"to": to, "replyTo": reply_to, "kind": kind, "item": item, "createdAt": at,
                               "relayId": None, "failed": False}
    tx.append_event("hub.queued", ref=item, actor="hub", data={"id": out_id, "to": to, "kind": kind})
    return _send_view(g, out_id, doc["outgoing"][out_id])


def _send_view(g: store.Group, out_id: str, entry: dict) -> dict:
    n = out_id.partition(":")[2]
    return {"id": out_id, "to": entry["to"], "bodyFile": str(g.path / "outgoing" / f"{n}.txt"),
            "replyTo": entry["replyTo"], "kind": entry["kind"]}


def _hints(g: store.Group, sender: str, hints) -> list[str]:
    return [f"{_short(g, sender)}：{h.text}" for h in hints]


def _dispatch(g: store.Group, m, at: str) -> tuple[str, list, list[str], dict | None]:
    """Hand one message to its module. Returns (kind, return problems or text, notes, unknown record)."""
    if m.sender == BRIDGE:
        return "bridge", [], [f"agent-relay 通知：{_first_line(m.body)}"], None
    msg = protocol.parse(m.body)
    short = _short(g, m.sender)
    if msg.kind in ("wait-user", "withdraw"):
        r = items.receive(g, m.body, sender=m.sender, relay_id=m.id, received_at=at)
        notes = _hints(g, m.sender, r.hints)
        if msg.kind == "wait-user" and r.accepted:
            notes += _hints(g, m.sender, tickets.receive(g, m.body, sender=m.sender, relay_id=m.id, sent_at=at).hints)
        return msg.kind, [r.return_text] if r.return_text else [], notes, None
    if msg.kind in ("wait-session", "resumed"):
        r = tickets.receive(g, m.body, sender=m.sender, relay_id=m.id, sent_at=at)
        if r.problems:
            return msg.kind, [_return_text(KIND_LABELS[msg.kind], r.problems)], [], None
        if msg.kind == "resumed":
            items.on_resumed(g, msg, sender=m.sender, at=at)
        return msg.kind, [], _hints(g, m.sender, r.hints), None
    if msg.kind == "review-conclusion":
        r = reviews.record_conclusion(g, msg, sender=m.sender, at=at)
        texts = [_return_text(KIND_LABELS[msg.kind], r.problems)] if r.problems else []
        return msg.kind, texts, _hints(g, m.sender, r.hints), None
    if msg.kind == "user-reply":
        return msg.kind, [], [f"{short} 发来一条【用户答复】，收件枢纽不处理"], None
    note = f"{short} 称：{_first_line(m.body)}（说「{m.id} 原文」看全文）"
    return "unknown", [], [note], {"sender": m.sender, "text": m.body, "at": at}


def receive(g: store.Group, inbox, now: str) -> Receipt:
    """Take one bridge_inbox page; each message is recorded as soon as it is handled."""
    result = Receipt(more=inbox.has_more)
    result.notes += list(inbox.warnings)
    for m in inbox.messages:
        if m.truncated:
            result.unread.append(m.id)
            result.notes.append(f"#{m.id} 正文没读全：用 bridge_inbox 把 maxChars 调大（最多 400000）重读后再交")
            continue
        result.ack.append(m.id)
        if str(m.id) in store.read_state(g, DOMAIN).get("received", {}):
            continue
        at = m.created_at or now
        kind, texts, notes, unknown = _dispatch(g, m, at)
        result.notes += notes
        with g.transaction() as tx:
            doc = _doc(tx)
            for text in texts:
                result.sends.append(_queue(g, tx, doc, m.sender, text, m.id, "return", None, now))
            if unknown is not None:
                doc["unknown"][str(m.id)] = unknown
            doc["received"][str(m.id)] = {"at": now, "kind": kind, "returned": bool(texts)}
            tx.append_event("hub.received", ref=None, actor=m.sender, data={"relayId": m.id, "kind": kind})
            tx.write_state(DOMAIN, doc)
    if inbox.has_more:
        result.notes.append("还有未读消息：确认已读（bridge_ack）后再读一页")
    return result
