"""The 待答表: items waiting for the user's decision (see spec/decision-queue.md).

This module only produces texts and recipients; the hub session sends them
through agent-relay and reports the message ids back.
"""

from __future__ import annotations

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
        "review": {"text": label.text, "warn": label.warn, "highlight": label.highlight, "ref": label.ref},
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


def receive(g: store.Group, text: str, sender: str, relay_id, received_at: str) -> ReceiveResult:
    """Take one incoming message; only 【等待用户】 and 【撤回】 belong here."""
    msg = protocol.parse(text)
    if msg.kind == "wait-user":
        return _receive_wait_user(g, msg, text, sender, relay_id, received_at)
    if msg.kind == "withdraw":
        return _receive_withdraw(g, msg, sender, relay_id, received_at)
    return ReceiveResult(False)
