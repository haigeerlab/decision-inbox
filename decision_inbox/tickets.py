"""Wait tickets: one per open 【等待其他会话】 (see spec/wait-tickets.md).

Tickets close only for the four reasons of requirement 4.5; this module never
contacts anyone and never deletes a ticket.
"""

from __future__ import annotations

from dataclasses import dataclass

from decision_inbox import protocol, store
from decision_inbox.protocol import Issue

DOMAIN = "tickets"
USER_TARGETS = ("用户", "收件枢纽")


@dataclass(frozen=True)
class ReceiveResult:
    handled: bool
    opened: int | None = None
    closed: tuple[int, ...] = ()
    hints: tuple[Issue, ...] = ()
    problems: tuple[Issue, ...] = ()


def _doc(tx) -> dict:
    doc = tx.read_state(DOMAIN)
    doc.setdefault("tickets", {})
    return doc


def _close(tx, doc: dict, no, reason: int, basis: str, at: str, actor: str) -> None:
    t = doc["tickets"][str(no)]
    t["status"] = "closed"
    t["close"] = {"reason": reason, "basis": basis, "at": at}
    tx.append_event("tickets.closed", ref=int(no), actor=actor, data={"reason": reason, "basis": basis})


def _close_by_end_line(tx, doc, ids, sender, reason, basis, at, hints) -> list[int]:
    """Explicit 结束 lines only close the sender's own open tickets (spec 关键决策 2)."""
    closed = []
    for no in ids:
        t = doc["tickets"].get(str(no))
        if t is None:
            continue  # an item number: decision-queue's business
        if t["waiter"] != sender:
            hints.append(Issue("not-own-ticket", f"#{no} 不是你的等待单，没有关闭"))
        elif t["status"] == "open":
            _close(tx, doc, no, reason, basis, at, sender)
            closed.append(no)
    return closed


def receive(g: store.Group, text: str, sender: str, relay_id, sent_at: str) -> ReceiveResult:
    """Handle 【等待其他会话】, 【已恢复】 and the 结束 line of 【等待用户】."""
    msg = protocol.parse(text)
    if msg.kind not in ("wait-session", "resumed", "wait-user"):
        return ReceiveResult(False)
    if not msg.ok:
        return ReceiveResult(True, problems=msg.problems)
    hints: list[Issue] = []
    opened = None
    with g.transaction() as tx:
        doc = _doc(tx)
        if msg.kind == "resumed":
            closed = _close_by_end_line(tx, doc, msg.ends.ids, sender, 1, f"【已恢复】#{relay_id}", sent_at, hints)
        else:
            closed = _close_by_end_line(tx, doc, msg.ends.ids, sender, 2, f"新消息 #{relay_id}", sent_at, hints)
        if msg.kind == "wait-session":
            target = msg.fields["在等谁"].strip()
            entry = None if target in USER_TARGETS else store.find_session(g, short_name=target)
            if entry is None and target not in USER_TARGETS:
                hints.append(Issue("unknown-target", f"「在等谁」里的 {target} 不在会话名册里，不判断它是否在线"))
            opened = tx.allocate_number()
            doc["tickets"][str(opened)] = {
                "waiter": sender, "target": target,
                "targetRelay": entry["relayName"] if entry else None,
                "what": msg.fields["等什么"].strip(), "sentAt": sent_at, "relayId": relay_id,
                "status": "open", "close": None,
            }
            tx.append_event("tickets.opened", ref=opened, actor=sender, data={"relayId": relay_id})
        tx.write_state(DOMAIN, doc)
    return ReceiveResult(True, opened, tuple(closed), tuple(hints) + msg.hints)
