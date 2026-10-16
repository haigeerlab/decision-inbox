"""Line states and stuck signals (see spec/line-health.md).

Pure read: everything comes in through `assess`'s arguments or read-only
store reads; the new progress snapshot is returned for patrol to save.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from decision_inbox import items, store

# Thresholds decided by the user on 2026-10-16 (requirement section 12 item 3).
REWORK_FALLBACK_ROUNDS = 3
REWORK_HISTORY_MIN = 3
REWORK_MARGIN = 2
SLOW_FALLBACK_MINUTES = 120
SLOW_FACTOR = 3
SLOW_FLOOR_MINUTES = 30
BUSY_MINUTES = 10
BACKLOG_MINUTES = 10
ESCALATE_MINUTES = 30
WORKING_MINUTES = 10  # spec 关键决策 2


@dataclass(frozen=True)
class LineState:
    word: str
    text: str
    target: str | None = None
    item: int | None = None
    since: str | None = None


@dataclass(frozen=True)
class Signal:
    no: int
    code: str
    sessions: tuple[str, ...]
    text: str


@dataclass(frozen=True)
class Assessment:
    lines: dict[str, LineState]
    signals: tuple[Signal, ...]
    snapshot: dict = field(default_factory=dict)


def _instant(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def _new_snapshot(now: str, maps: dict, previous: dict | None) -> dict:
    """Done counts per module; changedAt moves only when the count changes (spec 验收 11)."""
    before = (previous or {}).get("sessions", {})
    sessions = {}
    for name, result in maps.items():
        if result.status != "ok":
            continue
        old = before.get(name, {})
        modules = {}
        for m in result.map.modules:
            prev = old.get(m.id)
            if prev is None:
                changed = None
            elif prev["done"] == m.progress_done:
                changed = prev["changedAt"]
            else:
                changed = now
            modules[m.id] = {"done": m.progress_done, "changedAt": changed}
        sessions[name] = modules
    return {"version": 1, "at": now, "sessions": sessions}


def _duration(minutes: float) -> str:
    minutes = max(0, int(minutes))
    return f"{minutes // 60} 小时" if minutes >= 60 else f"{minutes} 分钟"


@dataclass
class _Facts:
    entry: dict
    fact: object | None            # relay-reader AgentFact
    read: object | None            # spec-guard-reader ReadResult
    tickets: list                  # open tickets this session waits on, by number
    asks: list                     # this session's fully stopped pending items
    pending: list                  # all of this session's pending items
    module: object | None          # active ModuleFact
    activity: datetime | None
    progress: datetime | None      # last progress: newest of changedAt and (complete history) lastTickAt
    changed: datetime | None       # newest snapshot changedAt


def _facts(g, relay, maps, snap) -> dict[str, _Facts]:
    ticket_doc = store.read_state(g, "tickets").get("tickets", {})
    pending = items.pending(g)
    out = {}
    for entry in store.roster(g):
        name = entry["relayName"]
        if entry["role"] == "hub":
            continue
        fact = relay.agents.get(name) if relay is not None else None
        read = maps.get(name)
        line_map = read.map if read is not None and read.status == "ok" else None
        module = None
        if line_map is not None and line_map.active_module:
            module = next((m for m in line_map.modules if m.id == line_map.active_module), None)
        changed = [_instant(v["changedAt"]) for v in snap["sessions"].get(name, {}).values() if v["changedAt"]]
        progress = list(changed)
        if line_map is not None and line_map.history == "complete":
            progress += [_instant(m.last_tick_at) for m in line_map.modules if m.last_tick_at]
        out[name] = _Facts(
            entry=entry, fact=fact, read=read,
            tickets=sorted((dict(t, no=int(k)) for k, t in ticket_doc.items()
                            if t["status"] == "open" and t["waiter"] == name), key=lambda t: t["no"]),
            asks=[it for it in pending if it["sender"] == name and it["fullyStopped"]],
            pending=[it for it in pending if it["sender"] == name],
            module=module,
            activity=_instant(fact.last_activity_at) if fact is not None else None,
            progress=max(progress) if progress else None,
            changed=max(changed) if changed else None,
        )
    return out


def _is_working(f: _Facts, now: datetime) -> bool:
    window = timedelta(minutes=WORKING_MINUTES)
    return any(t is not None and now - t <= window for t in (f.activity, f.changed))


def _has_open_work(f: _Facts) -> bool:
    m = f.module
    return (m is not None and m.step == "build" and m.review_plan == "approved"
            and m.progress_done < m.progress_total)


def _state(f: _Facts, now: datetime) -> LineState:
    """The seven words, first match wins (requirement section 12 item 14)."""
    presence = f.fact.presence if f.fact is not None else None
    if presence in ("offline", "unreachable"):
        return LineState("offline", "掉线")
    if presence == "needs-user":
        return LineState("needs-user", "等你确认")
    if f.tickets:
        t = f.tickets[0]
        return LineState("blocked", f"阻塞：等 {t['target']}", target=t["target"], since=t["sentAt"])
    if f.asks:
        it = f.asks[0]
        return LineState("blocked", f"阻塞：等你决定 #{it['no']}", item=it["no"], since=it["receivedAt"])
    if _is_working(f, now):
        return LineState("working", "干活中")
    last = f.progress or f.activity
    if _has_open_work(f) and last is not None:
        return LineState("stalled", f"停住 {_duration((now - last).total_seconds() / 60)}",
                         since=last.isoformat())
    if not f.pending and f.read is not None and f.read.status == "ok" and f.read.map.stage == "DONE":
        return LineState("done", "已结项（空闲）")
    if f.activity is not None:
        return LineState("idle", f"{_duration((now - f.activity).total_seconds() / 60)}无活动",
                         since=f.activity.isoformat())
    return LineState("idle", "无活动记录（agent-relay 没有它的数据）")


def _short(f: _Facts) -> str:
    return f.entry["shortName"]


def _session_signals(facts: dict[str, _Facts], lines: dict[str, LineState], now: datetime) -> list[Signal]:
    """Signals 1, 2, 4, 5 and 10: waiting chains and message backlogs."""
    out = []
    open_count = sum(len(f.tickets) for f in facts.values())
    if open_count and all(state.word != "working" for state in lines.values()):
        out.append(Signal(1, "all-waiting", tuple(sorted(facts)),
                          f"全线互等：所有会话都没在干活，还有 {open_count} 张等待单没关"))
    for name, f in facts.items():
        fact = f.fact
        for t in f.tickets:
            target = t.get("targetRelay")
            if (target and fact is not None and target in fact.waiting_from
                    and lines[name].word != "working"):
                out.append(Signal(2, "delivered-not-picked", (name, target),
                                  f"交付了没人接：{t['target']} 已发消息给 {_short(f)}，"
                                  f"{_short(f)} 还没去取（{_short(f)} 在等 {t['target']}）"))
        if fact is None or not fact.waiting_count:
            continue
        if fact.presence in ("offline", "unreachable"):
            out.append(Signal(4, "offline-backlog", (name,),
                              f"{_short(f)} 掉线，有 {fact.waiting_count} 条消息送不进去"))
        elif fact.presence_since is not None:
            busy = (now - _instant(fact.presence_since)).total_seconds() / 60
            if busy >= BUSY_MINUTES:
                out.append(Signal(5, "busy-backlog", (name,),
                                  f"{_short(f)} 已忙 {int(busy)} 分钟，还有 {fact.waiting_count} 条消息在等它"))
        if fact.host_app == "codex" and fact.presence_raw != "running" and fact.waiting_oldest_at:
            waited = (now - _instant(fact.waiting_oldest_at)).total_seconds() / 60
            if waited >= BACKLOG_MINUTES:
                out.append(Signal(10, "codex-backlog", (name,),
                                  f"{_short(f)}（Codex）没被加载，有 {fact.waiting_count} 条消息积压，"
                                  f"最早一条已等 {int(waited)} 分钟"))
    return out


def assess(g: store.Group, now: str, relay=None, maps: dict | None = None,
           previous: dict | None = None) -> Assessment:
    maps = maps or {}
    snap = _new_snapshot(now, maps, previous)
    moment = _instant(now)
    facts = _facts(g, relay, maps, snap)
    lines = {name: _state(f, moment) for name, f in facts.items()}
    signals = _session_signals(facts, lines, moment)
    return Assessment(lines, tuple(sorted(signals, key=lambda x: (x.no, x.sessions))), snap)
