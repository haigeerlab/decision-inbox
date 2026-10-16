"""Reviewer registry, review-line labels and review rounds (see spec/review-registry.md).

The registry only records the user's approval evidence it is given; callers
invoke it after the user approved in the hub.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from decision_inbox import store
from decision_inbox.protocol import Issue

DOMAIN = "reviews"
NODES = ("spec", "plan", "interface", "final")
SUBMITTER_ROLES = ("dev", "coordinator")


class InvalidRegistration(ValueError):
    """A registry change breaks the rules; nothing is written."""


@dataclass(frozen=True)
class Registration:
    session: str
    reviewer: str
    nodes: tuple[str, ...]
    since: str
    until: str | None


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _check_role(g: store.Group, relay_name: str, roles: tuple[str, ...], what: str) -> None:
    entry = store.find_session(g, relay_name=relay_name)
    if entry is None or entry.get("role") not in roles:
        raise InvalidRegistration(f"{what}必须是名册里的{'／'.join(roles)}：{relay_name!r}")


def _registrations(doc: dict, session: str) -> list[dict]:
    return doc.setdefault("registrations", {}).setdefault(session, [])


def _close_current(history: list[dict], at: str) -> bool:
    if history and history[-1].get("until") is None:
        history[-1]["until"] = at
        return True
    return False


def register(g: store.Group, session: str, reviewer: str, nodes, approval_item: int | None,
             approval_note: str, at: str | None = None) -> None:
    """Register (or replace) the reviewer of `session`; the old record keeps its history."""
    nodes = tuple(nodes)
    if not nodes or any(n not in NODES for n in nodes):
        raise InvalidRegistration(f"节点只能是 {'、'.join(NODES)} 中的若干类：{nodes!r}")
    if not (approval_note or "").strip():
        raise InvalidRegistration("登记变更必须写明用户批准的依据")
    _check_role(g, session, SUBMITTER_ROLES, "送审方")
    _check_role(g, reviewer, ("owner",), "审查者")
    at = at or store.now()
    with g.transaction() as tx:
        doc = tx.read_state(DOMAIN)
        history = _registrations(doc, session)
        _close_current(history, at)
        history.append({"reviewer": reviewer, "nodes": list(nodes), "since": at, "until": None,
                        "approvalItem": approval_item, "approvalNote": approval_note})
        tx.append_event("reviews.registered", ref=approval_item, actor="user",
                        data={"session": session, "reviewer": reviewer, "nodes": list(nodes), "at": at,
                              "approvalNote": approval_note})
        tx.write_state(DOMAIN, doc)


def unregister(g: store.Group, session: str, approval_item: int | None, approval_note: str,
               at: str | None = None) -> None:
    if not (approval_note or "").strip():
        raise InvalidRegistration("登记变更必须写明用户批准的依据")
    at = at or store.now()
    with g.transaction() as tx:
        doc = tx.read_state(DOMAIN)
        if not _close_current(_registrations(doc, session), at):
            raise InvalidRegistration(f"{session} 现在没有登记审查者")
        tx.append_event("reviews.unregistered", ref=approval_item, actor="user",
                        data={"session": session, "at": at, "approvalNote": approval_note})
        tx.write_state(DOMAIN, doc)


def registration_at(g: store.Group, session: str, at: str) -> Registration | None:
    """The registration in force at `at` (since <= at < until), compared as instants."""
    moment = _instant(at)
    doc = store.read_state(g, DOMAIN)
    for r in reversed(doc.get("registrations", {}).get(session, [])):
        if _instant(r["since"]) <= moment and (r["until"] is None or moment < _instant(r["until"])):
            return Registration(session, r["reviewer"], tuple(r["nodes"]), r["since"], r["until"])
    return None


@dataclass(frozen=True)
class ReviewLabel:
    text: str
    warn: bool = False
    highlight: bool = False
    ref: str | None = None
    mentions: tuple[str, ...] = ()


_LABELS = {
    "passed": "已审：通过",
    "in-progress": "审查中，请勿先批",
    "not-applicable": "不需审：不属于审查节点",
    "waived": "用户豁免",
}


def _mentions(message) -> tuple[str, ...]:
    """Lines that talk about review, quoted as written (requirement 4.3 rule 2)."""
    found = []
    if message.review.raw is not None:
        found.append(message.review.raw.strip())
    for name, value in message.fields.items():
        if name == "架构审查":
            continue
        found += [line.strip() for line in value.split("\n") if "审查" in line]
    return tuple(found)


def display_label(g: store.Group, session: str, message, received_at: str) -> ReviewLabel:
    """Requirement 4.3: look only at the registration and the 架构审查 line, never infer."""
    if registration_at(g, session, received_at) is None:
        return ReviewLabel("不需审：本会话无审查者")
    review = message.review
    if review.status == "passed-with-advice":
        return ReviewLabel(f"已审：通过，附建议{review.advice_count}条", ref=review.ref)
    if review.status in _LABELS:
        return ReviewLabel(_LABELS[review.status], highlight=review.status == "in-progress", ref=review.ref)
    return ReviewLabel("⚠ 未标审查", warn=True, mentions=_mentions(message))


@dataclass(frozen=True)
class ConclusionResult:
    recorded: bool
    problems: tuple = ()
    hints: tuple = ()


@dataclass(frozen=True)
class RoundStats:
    closed: tuple[tuple[str, str, str, int], ...]
    open: tuple[tuple[str, str, str, int], ...]


def _issue(code: str, text: str) -> Issue:
    return Issue(code, text)


def record_conclusion(g: store.Group, message, sender: str, at: str | None = None) -> ConclusionResult:
    """Count one 【审查结论】 round; only the registered reviewer of the submitter counts."""
    at = at or store.now()
    c = message.conclusion if message.kind == "review-conclusion" and message.ok else None
    submitter = store.find_session(g, short_name=c.submitter) if c else None
    if c is None or submitter is None:
        return ConclusionResult(False, (_issue("bad-conclusion", "【审查结论】不合格或送审方不在名册里"),))
    session = submitter["relayName"]
    reg = registration_at(g, session, at)
    if reg is None or reg.reviewer != sender:
        return ConclusionResult(False, (_issue("not-registered-reviewer",
                                               f"{sender} 不是 {c.submitter} 登记的审查者"),))
    if c.node not in reg.nodes:
        return ConclusionResult(False, (_issue("node-not-registered", f"{c.submitter} 没有登记审查节点 {c.node}"),))
    hints = []
    with g.transaction() as tx:
        doc = tx.read_state(DOMAIN)
        review = doc.setdefault("reviews", {}).setdefault(
            c.ref, {"submitter": session, "reviewer": sender, "node": c.node, "rounds": [], "closed": False})
        if review["closed"]:
            review["closed"] = False
            hints.append(_issue("reopened", f"审查 {c.ref} 已结束后又收到结论，已重新打开"))
        review["rounds"].append({"at": at, "verdict": c.verdict, "adviceCount": c.advice_count})
        review["closed"] = c.verdict in ("passed", "passed-with-advice")
        tx.append_event("reviews.conclusion", ref=None, actor=sender,
                        data={"review": c.ref, "session": session, "node": c.node, "verdict": c.verdict, "at": at})
        tx.write_state(DOMAIN, doc)
    return ConclusionResult(True, (), tuple(hints))


def round_stats(g: store.Group) -> RoundStats:
    closed, open_ = [], []
    for ref, r in store.read_state(g, DOMAIN).get("reviews", {}).items():
        row = (ref, r["submitter"], r["node"], len(r["rounds"]))
        (closed if r["closed"] else open_).append(row)
    return RoundStats(tuple(closed), tuple(open_))
