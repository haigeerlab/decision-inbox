"""The 待答表: items waiting for the user's decision (see spec/decision-queue.md).

This module only produces texts and recipients; the hub session sends them
through agent-relay and reports the message ids back.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from decision_inbox import protocol, reviews, store
from decision_inbox.protocol import Issue

DOMAIN = "items"
MULTILINE_ROLES = ("coordinator", "owner")
# Scope problems only matter when the sender may raise a multi-line item.
_SCOPE_CODES = ("scope-missing:", "scope-unknown:", "missing-field:各线范围")


@dataclass(frozen=True)
class ReceiveResult:
    handled: bool
    accepted: bool = False
    item: int | None = None
    problems: tuple[Issue, ...] = ()
    hints: tuple[Issue, ...] = ()
    return_text: str | None = None


FINAL = ("superseded", "withdrawn", "closed")


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _not_owner(no) -> Issue:
    return Issue("not-owner", f"#{no} 不存在，或不是你抛出的事项")


def _owned(doc: dict, no, sender: str) -> dict | None:
    it = doc["items"].get(str(no)) if no is not None else None
    return it if it is not None and it["sender"] == sender and it["status"] not in FINAL else None


def _doc(tx) -> dict:
    doc = tx.read_state(DOMAIN)
    doc.setdefault("items", {})
    return doc


def _return_text(problems) -> str:
    lines = ["退回：你的【等待用户】没有收进待答表，原因："]
    lines += [f"- {p.text}" for p in problems]
    lines.append("请补全后重新抛出。")
    return "\n".join(lines)


def _record(msg, sender: str, relay_id, received_at: str, multi: bool, label) -> dict:
    return {
        "sender": sender,
        "relayId": relay_id,
        "receivedAt": received_at,
        "text": None,
        "from": msg.fields.get("来自", "").strip(),
        "decide": msg.fields.get("要你决定", "").strip(),
        "options": [{"letter": o.letter, "text": o.text, "consequence": o.consequence} for o in msg.options],
        "recommended": msg.recommended,
        "suggestedReply": msg.suggested_reply,
        "fullyStopped": msg.fully_stopped,
        "multi": multi,
        "lines": list(msg.lines_in_scope) if multi else [],
        "scopes": dict(msg.scopes) if multi else {},
        "ends": {"ids": list(msg.ends.ids), "none": msg.ends.none},
        "review": {"text": label.text, "warn": label.warn, "highlight": label.highlight, "ref": label.ref,
                   "mentions": list(label.mentions)},
        "status": "pending",
        "statusAt": {"pending": received_at},
        "answers": [],
        "recipients": [],
        "sent": [],
    }


def _receive_wait_user(g, msg, text, sender, relay_id, received_at) -> ReceiveResult:
    entry = store.find_session(g, relay_name=sender) or {}
    problems = list(msg.problems)
    hints = list(msg.hints)
    multi = bool(msg.lines_in_scope)
    if multi and entry.get("role") not in MULTILINE_ROLES:
        multi = False
        problems = [p for p in problems if not p.code.startswith(_SCOPE_CODES)]
        hints.append(Issue("multiline-not-allowed", "只有总协调和负责人能抛多线事项，已按普通事项处理"))
    if multi:
        for name in msg.lines_in_scope:
            if store.find_session(g, short_name=name) is None:
                problems.append(Issue(f"scope-session-unknown:{name}", f"适用会话里的 {name} 不在会话名册里"))
    with g.transaction() as tx:
        doc = _doc(tx)
        superseded = []
        for kind, no in msg.markers:
            if kind == "supersede":
                if _owned(doc, no, sender) is None:
                    problems.append(_not_owner(no))
                else:
                    superseded.append(no)
        if problems:
            tx.append_event("items.returned", ref=None, actor=sender,
                            data={"relayId": relay_id, "codes": [p.code for p in problems]})
            tx.write_state(DOMAIN, doc)
            return ReceiveResult(True, False, None, tuple(problems), tuple(hints), _return_text(problems))
        no = tx.allocate_number()
        label = reviews.display_label(g, session=sender, message=msg, received_at=received_at)
        record = _record(msg, sender, relay_id, received_at, multi, label)
        record["text"] = text
        record["markers"] = [list(m) for m in msg.markers]
        doc["items"][str(no)] = record
        tx.append_event("items.received", ref=no, actor=sender, data={"relayId": relay_id})
        for old in superseded:
            _set_status(doc, old, "superseded", received_at)
            tx.append_event("items.superseded", ref=old, actor=sender, data={"by": no})
        tx.write_state(DOMAIN, doc)
    return ReceiveResult(True, True, no, (), tuple(hints))


def _set_status(doc: dict, no, status: str, at: str) -> None:
    it = doc["items"][str(no)]
    it["status"] = status
    it["statusAt"][status] = at


def _receive_withdraw(g, msg, sender, relay_id, received_at) -> ReceiveResult:
    problems = list(msg.problems)
    with g.transaction() as tx:
        doc = _doc(tx)
        if not problems and _owned(doc, msg.item, sender) is None:
            problems.append(_not_owner(msg.item))
        if problems:
            tx.append_event("items.returned", ref=None, actor=sender,
                            data={"relayId": relay_id, "codes": [p.code for p in problems]})
            tx.write_state(DOMAIN, doc)
            return ReceiveResult(True, False, None, tuple(problems), (), _return_text(problems))
        _set_status(doc, msg.item, "withdrawn", received_at)
        tx.append_event("items.withdrawn", ref=msg.item, actor=sender,
                        data={"relayId": relay_id, "reason": msg.fields.get("原因", "").strip()})
        tx.write_state(DOMAIN, doc)
    return ReceiveResult(True, True, msg.item)


def _blocks(it: dict) -> int:
    """How many lines the item holds up (spec 关键决策 3)."""
    if it["multi"]:
        return len(it["lines"])
    return 1 if it["fullyStopped"] else 0


def pending(g: store.Group) -> list[dict]:
    """Items waiting for the user: most lines held up first, then oldest first."""
    found = []
    for key, it in store.read_state(g, DOMAIN).get("items", {}).items():
        if it["status"] == "pending":
            found.append(dict(it, no=int(key), blocks=_blocks(it)))
    return sorted(found, key=lambda it: (-it["blocks"], _instant(it["receivedAt"])))


def get(g: store.Group, item: int) -> dict | None:
    it = store.read_state(g, DOMAIN).get("items", {}).get(str(item))
    return None if it is None else dict(it, no=int(item))


def by_status(g: store.Group, *statuses: str) -> list[dict]:
    """Items in any of `statuses`, by number (hub-view's detail, recent and invalidated views)."""
    found = [dict(it, no=int(key)) for key, it in store.read_state(g, DOMAIN).get("items", {}).items()
             if it["status"] in statuses]
    return sorted(found, key=lambda it: it["no"])


@dataclass(frozen=True)
class Answer:
    item: int
    letter: str | None
    original: str


@dataclass(frozen=True)
class ReplyParse:
    answers: tuple[Answer, ...] = ()
    question: str | None = None


_SEGMENT_RE = re.compile(r"^\s*#?(\d+)\s*(.*)$", re.S)
_LETTER_RE = re.compile(r"^([A-Z])(?:\s+.*)?$", re.S)
_SPLIT_RE = re.compile(r"[，；;,]")
ANSWERED = ("forwarded", "picked", "acknowledged")


def _segments(text: str, known: dict) -> list[str]:
    """Split only when every piece starts with an existing item number (spec 关键决策 4)."""
    def numbered(piece: str) -> bool:
        m = _SEGMENT_RE.match(piece)
        return bool(m) and m.group(1) in known

    lines = [line for line in text.split("\n") if line.strip()]
    if len(lines) > 1:
        return [line.strip() for line in lines] if all(numbered(l) for l in lines) else [text]
    pieces = [x.strip() for x in _SPLIT_RE.split(text) if x.strip()]
    if len(pieces) > 1 and all(numbered(x) for x in pieces):
        return pieces
    return [text]


def interpret_reply(g: store.Group, text: str) -> ReplyParse:
    """The user's reply as answers, or a question when anything does not match (requirement 6.4)."""
    text = text.strip()
    known = store.read_state(g, DOMAIN).get("items", {})
    waiting = [k for k, it in known.items() if it["status"] == "pending"]
    answers: list[Answer] = []
    for segment in _segments(text, known):
        m = _SEGMENT_RE.match(segment)
        if m:
            key, rest = m.group(1), m.group(2).strip()
        elif len(waiting) == 1:
            key, rest = waiting[0], segment
        else:
            return ReplyParse(question="没看出这句是答哪一项的，请在开头写上编号，例如「12 B」。")
        it = known.get(key)
        if it is None:
            return ReplyParse(question=f"#{key} 不在待答表里，请确认编号。")
        if it["status"] in ANSWERED:
            return ReplyParse(question=f"#{key} 已经转达过，要改答复请先说明以哪次为准。")
        if it["status"] != "pending":
            return ReplyParse(question=f"#{key} 已经不在待答状态（已失效或已结束），请确认。")
        letter = None
        lm = _LETTER_RE.match(rest) if m else None
        if lm:
            letter = lm.group(1)
            if letter not in {o["letter"] for o in it["options"]}:
                return ReplyParse(question=f"#{key} 没有选项 {letter}，请确认。")
        answer = Answer(int(key), letter, segment)
        same = [a for a in answers if a.item == answer.item]
        if same and (same[0].letter != letter or (letter is None and same[0].original != segment)):
            return ReplyParse(question=f"#{key} 这次回复里有两个不同的答复，请说明以哪个为准。")
        if not same:
            answers.append(answer)
    return ReplyParse(answers=tuple(answers))


@dataclass(frozen=True)
class Outgoing:
    to: str
    text: str
    item: int


def answer(g: store.Group, answers, answered_at: str) -> tuple[Outgoing, ...]:
    """Record the user's answers and build the 【用户答复】 texts; the hub sends them."""
    out: list[Outgoing] = []
    with g.transaction() as tx:
        doc = _doc(tx)
        for a in answers:
            it = doc["items"].get(str(a.item))
            if it is None or it["status"] != "pending":
                raise ValueError(f"#{a.item} is not waiting for an answer")
            option = next((o for o in it["options"] if o["letter"] == a.letter), None)
            option_text = f"{option['letter']}：{option['text']}" if option else None
            batch = [Outgoing(it["sender"], protocol.format_user_reply(
                item=a.item, original=a.original, answered_at=answered_at, option_text=option_text,
                source_relay_id=it["relayId"]), a.item)]
            if it["multi"]:
                sender = (store.find_session(g, relay_name=it["sender"]) or {}).get("shortName", it["sender"])
                texts = protocol.format_multiline_replies(item=a.item, sender=sender, original=a.original,
                                                          answered_at=answered_at, wait_user_text=it["text"],
                                                          source_relay_id=it["relayId"])
                for short, text in texts.items():
                    batch.append(Outgoing(store.find_session(g, short_name=short)["relayName"], text, a.item))
            it["answers"].append({"letter": a.letter, "original": a.original, "at": answered_at})
            it["recipients"] = [o.to for o in batch]
            _set_status(doc, a.item, "forwarded", answered_at)
            tx.append_event("items.answered", ref=a.item, actor="user",
                            data={"letter": a.letter, "original": a.original, "recipients": it["recipients"]})
            out += batch
        tx.write_state(DOMAIN, doc)
    return tuple(out)


PROGRESS = ("forwarded", "picked", "acknowledged")


def record_sent(g: store.Group, item: int, to: str, relay_id, at: str) -> None:
    """Remember the agent-relay id of a reply the hub sent, so /item can prove who sent it."""
    with g.transaction() as tx:
        doc = _doc(tx)
        doc["items"][str(item)]["sent"].append({"to": to, "relayId": relay_id, "at": at,
                                                "state": None, "ackAt": None})
        tx.append_event("items.sent", ref=item, actor="hub", data={"to": to, "relayId": relay_id})
        tx.write_state(DOMAIN, doc)


def _progress(it: dict) -> str:
    """The slowest recipient decides (spec 假设 2)."""
    level = {}
    for sent in it["sent"]:
        level[sent["to"]] = 2 if sent["ackAt"] else 1 if sent["state"] == "accepted" else 0
    return PROGRESS[min(level.get(r, 0) for r in it["recipients"])] if it["recipients"] else "forwarded"


def update_delivery(g: store.Group, facts: dict, at: str) -> None:
    """facts: agent-relay message id -> (deliveryState, acknowledgedAt). Status only moves forward."""
    with g.transaction() as tx:
        doc = _doc(tx)
        for key, it in doc["items"].items():
            if it["status"] not in PROGRESS:
                continue
            for sent in it["sent"]:
                if sent["relayId"] in facts:
                    sent["state"], sent["ackAt"] = facts[sent["relayId"]]
            new = _progress(it)
            if PROGRESS.index(new) > PROGRESS.index(it["status"]):
                _set_status(doc, key, new, at)
                tx.append_event("items.delivery", ref=int(key), actor="relay", data={"status": new})
        tx.write_state(DOMAIN, doc)


def on_resumed(g: store.Group, message, sender: str, at: str) -> tuple[int, ...]:
    """【已恢复】 from the proposer closes its own answered items named in 结束."""
    closed = []
    with g.transaction() as tx:
        doc = _doc(tx)
        for written in message.ends.ids:
            no = written
            if str(no) not in doc["items"]:  # the proposer's own message id (e2e-round1-fixes F10)
                no = next((int(k) for k, it in doc["items"].items()
                           if it["relayId"] == written and it["sender"] == sender), written)
            it = doc["items"].get(str(no))
            if it is not None and it["sender"] == sender and it["status"] in PROGRESS:
                _set_status(doc, no, "closed", at)
                tx.append_event("items.closed", ref=no, actor=sender, data={})
                closed.append(no)
        tx.write_state(DOMAIN, doc)
    return tuple(closed)


def history(g: store.Group, item: int) -> list[dict]:
    return [e for e in store.read_events(g, ref=item) if str(e.get("type", "")).startswith("items.")]


def receive(g: store.Group, text: str, sender: str, relay_id, received_at: str) -> ReceiveResult:
    """Take one incoming message; only 【等待用户】 and 【撤回】 belong here."""
    msg = protocol.parse(text)
    if msg.kind == "wait-user":
        return _receive_wait_user(g, msg, text, sender, relay_id, received_at)
    if msg.kind == "withdraw":
        return _receive_withdraw(g, msg, sender, relay_id, received_at)
    return ReceiveResult(False)
