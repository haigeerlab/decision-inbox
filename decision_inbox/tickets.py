"""Wait tickets: one per open 【等待其他会话】 (see spec/wait-tickets.md).

Tickets close only for the four reasons of requirement 4.5; this module never
contacts anyone and never deletes a ticket.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from decision_inbox import protocol, store
from decision_inbox.protocol import Issue

DOMAIN = "tickets"
USER_TARGETS = ("用户", "决策收件箱", "收件枢纽")  # 收件枢纽: old name lines may still write
_NUM_RE = re.compile(r"#\s*(\d+)")
# Requirement 4.5 fixed fallback thresholds, in minutes.
WAITED_MINUTES = 15
STUCK_MINUTES = 60
OFFLINE = ("offline", "unreachable")
_NOTE_RE = re.compile(r"\s*[（(][^（）()]*[）)]\s*$")


def waits_on_user(g: store.Group, target: str) -> bool:
    """Whether 「在等谁」 names the user (wait-closed-item, I-11).

    Besides the user's own names, the hub's short and agent-relay names count, and a trailing note in
    brackets is dropped first, as in 「决策收件箱（di-p0-hub）」. A dev line is never the user.
    """
    hub = next((e for e in store.roster(g) if e["role"] == "hub"), None)
    names = set(USER_TARGETS) | ({hub["shortName"], hub["relayName"]} if hub else set())
    target = (target or "").strip()
    return target in names or _NOTE_RE.sub("", target).strip() in names


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


def _resolve_end(tx, doc, no: int, sender: str, hints, resumed: bool) -> int | None:
    """A 结束 number as a ticket number, or None when it is not one.

    The hub's own number wins; failing that, a line may write the agent-relay id of
    its own message, the only number it ever knew (e2e-round1-fixes F10). Item numbers
    and the sender's own item message ids are decision-queue's business; anything else
    is reported instead of silently skipped. An item named outside 【已恢复】 ends
    nothing, so that is reported too (relay-checkpoint-authority F13).
    """
    if str(no) in doc["tickets"]:
        return no
    own = [k for k, t in doc["tickets"].items() if t["relayId"] == no and t["waiter"] == sender]
    if own:
        return int(own[0])
    known = tx.read_state("items").get("items", {})
    if str(no) in known or any(it["relayId"] == no and it["sender"] == sender for it in known.values()):
        if not resumed:
            hints.append(Issue("end-is-item", f"#{no} 是待决事项，不是等待记录；结束待决事项要发【已恢复】"))
        return None
    hints.append(Issue("end-unknown", f"#{no} 既不是决策收件箱编号，也不是你发过的消息，没有关闭任何东西"))
    return None


def _close_by_end_line(tx, doc, ids, sender, reason, basis, at, hints) -> list[int]:
    """Explicit 结束 lines only close the sender's own open tickets (spec 关键决策 2)."""
    closed = []
    for written in ids:
        no = _resolve_end(tx, doc, written, sender, hints, resumed=reason == 1)
        if no is None:
            continue
        t = doc["tickets"][str(no)]
        if t["waiter"] != sender:
            hints.append(Issue("not-own-ticket", f"#{no} 不是你的等待记录，没有关闭"))
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
            # Short name first; lines also write the agent-relay name (e2e-round1-fixes F5).
            entry = None if target in USER_TARGETS else (store.find_session(g, short_name=target)
                                                         or store.find_session(g, relay_name=target))
            if entry is None and not waits_on_user(g, target):  # wait-closed-item: 「决策收件箱（…）」 is known
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


ANSWERED = ("forwarded", "picked", "acknowledged", "closed")


def close_answered(g: store.Group, at: str) -> tuple[int, ...]:
    """Reason 3: a ticket waiting on the user's answer to the waiter's own item, already sent by the hub."""
    item_doc = store.read_state(g, "items").get("items", {})
    closed = []
    with g.transaction() as tx:
        doc = _doc(tx)
        for key, t in doc["tickets"].items():
            if t["status"] != "open" or not waits_on_user(g, t["target"]):
                continue
            for no in _NUM_RE.findall(t["what"]):
                it = item_doc.get(no)
                if it and it["sender"] == t["waiter"] and it["status"] in ANSWERED and it["sent"]:
                    _close(tx, doc, key, 3, f"已转发 #{it['sent'][0]['relayId']}", at, "hub")
                    closed.append(int(key))
                    break
        tx.write_state(DOMAIN, doc)
    return tuple(closed)


def close_by_user(g: store.Group, ticket: int, reason: str | None, at: str) -> None:
    """Reason 4: the user said 「关掉 #编号」."""
    with g.transaction() as tx:
        doc = _doc(tx)
        t = doc["tickets"].get(str(ticket))
        if t is None or t["status"] != "open":
            raise ValueError(f"#{ticket} is not an open wait ticket")
        _close(tx, doc, ticket, 4, (reason or "").strip() or "用户关闭", at, "user")
        tx.write_state(DOMAIN, doc)


@dataclass(frozen=True)
class TicketView:
    no: int
    waiter: str
    target: str
    what: str
    minutes: int
    marks: tuple[str, ...]
    notes: tuple[str, ...]
    maybe_stale: int | None = None  # the waiter's later message id (wait-honesty-and-briefs A2)
    stale_item: int | None = None   # the waiter's own named item that has closed (wait-closed-item)


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _short(g: store.Group, relay_name: str) -> str:
    return (store.find_session(g, relay_name=relay_name) or {}).get("shortName", relay_name)


def stale_tickets(g: store.Group) -> dict[int, int]:
    """Open tickets whose waiter has since sent the hub another message: {ticket no: that message id}.

    A wait the sender has moved past without ending it is most likely forgotten
    (wait-honesty-and-briefs A2). Only the hub's own receipts count; receipts written
    before they carried the sender are read back from the hub.received events.

    A later 【等待其他会话】 opens another wait and moves past nothing; a module-crew
    coordinator speaks for several modules, so its waits are never inferred stale
    (crew-line-status revision 1).
    """
    senders: dict[int, str] = {}
    kinds: dict[int, str] = {}
    for e in store.read_events(g):
        if e.get("type") == "hub.received" and isinstance(e.get("data", {}).get("relayId"), int):
            senders[e["data"]["relayId"]] = e.get("actor")
            if e["data"].get("kind"):
                kinds[e["data"]["relayId"]] = e["data"]["kind"]
    for key, rec in store.read_state(g, "hub").get("received", {}).items():
        if rec.get("sender") and key.isdigit():
            senders[int(key)] = rec["sender"]
        if rec.get("kind") and key.isdigit():
            kinds[int(key)] = rec["kind"]
    coordinators = {e["relayName"] for e in store.roster(g) if e.get("crewCoordinator")}
    out = {}
    for key, t in store.read_state(g, DOMAIN).get("tickets", {}).items():
        if t["status"] != "open" or not isinstance(t.get("relayId"), int) or t["waiter"] in coordinators:
            continue
        later = [i for i, who in senders.items()
                 if who == t["waiter"] and i > t["relayId"] and kinds.get(i) != "wait-session"]
        if later:
            out[int(key)] = min(later)
    return out


CLOSED_ITEM = ("closed", "superseded", "withdrawn")


def closed_item_tickets(g: store.Group) -> dict[int, int]:
    """Open tickets naming the waiter's own item that has since closed: {ticket no: item no} (I-11).

    The wait itself says what it waits on, so module-crew coordinators are judged too; the wait may
    want more than that item, so it is only flagged for the user to close (user decision D1 A).
    """
    item_doc = store.read_state(g, "items").get("items", {})
    out = {}
    for key, t in store.read_state(g, DOMAIN).get("tickets", {}).items():
        if t["status"] != "open":
            continue
        for no in _NUM_RE.findall(t["what"]):
            it = item_doc.get(no)
            if it and it["sender"] == t["waiter"] and it["status"] in CLOSED_ITEM:
                out[int(key)] = int(no)
                break
    return out


def stale_numbers(g: store.Group) -> frozenset[int]:
    """Every open ticket that is maybe stale, for whichever reason (line state, all-waiting, counts)."""
    return frozenset(stale_tickets(g)) | frozenset(closed_item_tickets(g))


def open_tickets(g: store.Group, now: str, relay=None) -> list[TicketView]:
    """Open tickets with the requirement 4.5 marks; `relay` is a relay-reader AgentsSnapshot or None."""
    views = []
    stale, closed_items = stale_tickets(g), closed_item_tickets(g)
    moment = _instant(now)
    for key, t in store.read_state(g, DOMAIN).get("tickets", {}).items():
        if t["status"] != "open":
            continue
        minutes = int((moment - _instant(t["sentAt"])).total_seconds() // 60)
        waiter = _short(g, t["waiter"])
        marks, notes = [], []
        fact = relay.agents.get(t["targetRelay"]) if relay is not None and t["targetRelay"] else None
        if fact is not None and fact.presence in OFFLINE:
            marks.append("offline")
            if fact.waiting_count and fact.waiting_oldest_at:
                oldest = _instant(fact.waiting_oldest_at).astimezone().strftime("%H:%M")
                notes.append(f"⚠ 对方离线：{t['target']} 离线，有 {fact.waiting_count} 条消息送不进去，"
                             f"最早一条是 {oldest} 发的")
            else:
                notes.append(f"⚠ 对方离线：{t['target']} 离线")
        if minutes >= WAITED_MINUTES:
            marks.append("waited")
            notes.append(f"⚠ 已等 {minutes} 分钟")
        if minutes >= STUCK_MINUTES:
            marks.append("maybe-stuck")
            notes.append(f"可能卡住：{waiter} 在等 {t['target']} 的「{t['what']}」，"
                         f"请看一下 {t['target']} 是否已完成却没通知 {waiter}")
        views.append(TicketView(int(key), t["waiter"], t["target"], t["what"], minutes, tuple(marks), tuple(notes),
                                stale.get(int(key)), closed_items.get(int(key))))
    return sorted(views, key=lambda v: v.no)


def closed_on(g: store.Group, day: str) -> list[dict]:
    """Tickets closed on `day` (YYYY-MM-DD, local time zone), with reason and basis."""
    found = []
    for key, t in store.read_state(g, DOMAIN).get("tickets", {}).items():
        if t["status"] == "closed" and _instant(t["close"]["at"]).astimezone().date().isoformat() == day:
            found.append(dict(t, no=int(key)))
    return sorted(found, key=lambda t: _instant(t["close"]["at"]))


def counts(g: store.Group, day: str) -> dict:
    all_tickets = store.read_state(g, DOMAIN).get("tickets", {}).values()
    return {"open": sum(1 for t in all_tickets if t["status"] == "open"),
            "closed_today": len(closed_on(g, day))}
