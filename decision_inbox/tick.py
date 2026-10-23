"""patrol tick (patrol-launchd): one patrol round run by launchd, with no patrol session.

It reads agent-relay through its script commands, runs the same `patrol.plan`, mails wakes and owner alerts
as the group's script identity, pops notices itself and records the round. A group-wide lock keeps it and
the hub's own round (`patrol plan --from-hub`) from running the same round twice. Whatever happens, the old
patrol-watch check runs last, so a patrol that stopped for any reason is still told.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime

from decision_inbox import crew, deps, desktop, loops, patrol, relay, relayscript, specguard, store, watch

DOMAIN = "patrol-tick"
LOCK_STALE_MINUTES = 10   # two rounds: a holder that died between plan and record
REPEAT_MINUTES = 30       # spec 假设 4
NOTICE_TITLE = "decision-inbox"
_NOT_IDENTITY = "is not a script identity"


@dataclass
class TickResult:
    skipped: str | None = None    # "locked" | "relay"
    done: list = field(default_factory=list)
    failed: list = field(default_factory=list)


def _minutes(now: str, then: str) -> float:
    def instant(v):
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    return (instant(now) - instant(then)).total_seconds() / 60


# --- the group-wide lock (spec 假设 5) ---

def lock_path(g: store.Group):
    return g.path / "patrol.lock"


def acquire(g: store.Group, by: str, now: str) -> bool:
    """Take the lock for this round; a lock older than LOCK_STALE_MINUTES is a leftover and is taken over."""
    path = lock_path(g)
    for _ in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            try:
                held = json.loads(path.read_text(encoding="utf-8"))
                stale = _minutes(now, held["at"]) >= LOCK_STALE_MINUTES
            except (OSError, ValueError, KeyError, TypeError):
                stale = True
            if not stale:
                return False
            path.unlink(missing_ok=True)
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"by": by, "at": now}, f)
        return True
    return False


def release(g: store.Group, by: str) -> None:
    """Drop the lock if `by` holds it; someone else's lock stays."""
    path = lock_path(g)
    try:
        if json.loads(path.read_text(encoding="utf-8")).get("by") == by:
            path.unlink()
    except (OSError, ValueError, AttributeError):
        pass


# --- one round ---

def identity(g: store.Group) -> str | None:
    return store.read_state(g, "onboarding").get("patrolIdentity")


def _mailbox(action: dict) -> str | None:
    """Who a wake or an owner alert is mailed to: always a mailbox name, never a desktop session."""
    if action["kind"] == "owner-alert":
        return action["target"]
    kind, _, key = action["id"].partition(":")
    return key if kind == "wake" else key.partition("|")[0]


def _remember(g: store.Group, **changes) -> None:
    with g.transaction() as tx:
        state = tx.read_state(DOMAIN)
        for key, value in changes.items():
            if value is None:
                state.pop(key, None)
            else:
                state[key] = value
        tx.write_state(DOMAIN, state)


def _relay_down(g: store.Group, now: str, reason: str, notify) -> None:
    last = store.read_state(g, DOMAIN).get("relayDownAt")
    if last and _minutes(now, last) < REPEAT_MINUTES:
        return
    if notify(NOTICE_TITLE, f"巡视读不到 agent-relay：{reason}"):
        _remember(g, relayDownAt=now)


def _read(kind: str, parse, **args):
    """(parsed or None, raw text or None, error or None) for one script read."""
    r = relayscript.run_script(kind, **args)
    if r.code != 0:
        return None, None, r.error or f"{kind} 退出码 {r.code}"
    try:
        return parse(r.stdout), r.stdout, None
    except (relay.RelayDataError, desktop.DesktopDataError) as e:
        return None, r.stdout, str(e)


def _execute(g: store.Group, now: str, actions: list, notify) -> tuple[list, list]:
    name = identity(g)
    done, failed, refused, sent = [], [], name is None, False
    for a in actions:
        if a["kind"] == "notify":
            (done if notify(NOTICE_TITLE, a["text"]) else failed).append(a["id"])
            continue
        to = _mailbox(a)
        if name is None or not to:
            failed.append(a["id"])
            continue
        r = relayscript.run_script("send", agent=to, identity=name, body=a["text"])
        if r.code == 0:
            done.append(a["id"])
            sent = True
        else:
            failed.append(a["id"])
            refused = refused or _NOT_IDENTITY in r.error
    if refused and failed:  # one notice per episode (spec 假设 3), cleared by the next send that works
        if not store.read_state(g, DOMAIN).get("identityMissingAt"):
            if notify(NOTICE_TITLE, f"巡视发不出信：请在终端登记脚本身份 {name or _default_identity(g)}"):
                _remember(g, identityMissingAt=now)
    elif sent:
        _remember(g, identityMissingAt=None)
    return done, failed


def _default_identity(g: store.Group) -> str:
    hub = next((e["relayName"] for e in store.roster(g) if e["role"] == "hub"), "<决策收件箱邮箱名>")
    return f"{hub}-patrol"


def _round(g: store.Group, now: str, notify) -> TickResult:
    found = deps.find("agent-relay")
    version = found.version if isinstance(found, deps.Install) else None
    agents, raw_agents, error = _read("agents", lambda t: relay.parse_agents(t, relay_version=version))
    if agents is None:
        _relay_down(g, now, error, notify)
        return TickResult(skipped="relay")
    if store.read_state(g, DOMAIN).get("relayDownAt"):
        _remember(g, relayDownAt=None)
    hub = next((e["relayName"] for e in store.roster(g) if e["role"] == "hub"), None)
    outbox, raw_outbox = None, None
    if hub:  # an unreadable outbox only skips that check (stall-and-patrol R19)
        outbox, raw_outbox, _ = _read("outbox", lambda t: relay.parse_outbox(t, sender=hub), agent=hub)
    sessions, _, _ = _read("sessions", desktop.parse_sessions)
    patrol.save_snapshot(g.name, store.now(), {"agents": raw_agents, "outbox": raw_outbox})
    maps = {e["relayName"]: specguard.read_line(e["repo"]) for e in store.roster(g)
            if e["role"] == "dev" and e.get("repo")}
    crews = crew.crews(g)
    loops.tag(g, maps, crews)
    doc = patrol.plan(g, now=now, relay=agents, maps=maps, crews=crews, outbox=outbox,
                      loop_facts=loops.facts(g, now, maps, crews), sessions=sessions).to_json()
    done, failed = _execute(g, now, doc["actions"], notify)
    patrol.record(g, doc, done=done, failed=failed, now=store.now())
    return TickResult(done=done, failed=failed)


def tick(g: store.Group, now: str, notify=watch.desktop_notify) -> TickResult:
    """One launchd round: lock, read, plan, act, record, unlock; then the patrol-watch check."""
    if not acquire(g, "schedule", now):
        result = TickResult(skipped="locked")
    else:
        try:
            result = _round(g, now, notify)
        finally:
            release(g, "schedule")
    watch.check(g, now, send=notify)
    return result
