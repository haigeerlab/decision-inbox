"""Reviewer registry, review-line labels and review rounds (see spec/review-registry.md).

The registry only records the user's approval evidence it is given; callers
invoke it after the user approved in the hub.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from decision_inbox import store

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
