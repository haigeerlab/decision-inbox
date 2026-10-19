"""Line states and stuck signals (see spec/line-health.md).

Pure read: everything comes in through `assess`'s arguments or read-only
store reads; the new progress snapshot is returned for patrol to save.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta

from decision_inbox import deps, items, reviews, store, tickets

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
    crew: object | None = None     # crew.CrewRead for a module-crew coordinator's line
    modules: tuple = ()            # (crew.Module, session word or None) for modules not merged yet
    crew_busy: bool = False        # a module that is not suspended is busy (crew-line-status)


# Stage words for module-crew's sessions output (crew-line-status); unknown stages show as given.
CREW_STAGES = {"spec-plan": "写 Spec／Plan", "build": "构建", "returned": "被退回", "wait-merge": "等合并"}
SUSPEND_CLIP = 20


def _busy(fact, now: datetime, also=()) -> bool:
    """agent-relay 0.8.1+ says busy outright; older ones fall back to recent activity."""
    activity = fact.activity if fact is not None else None
    if activity is not None:   # relay-presence-and-doubt
        return activity == "busy"
    window = timedelta(minutes=WORKING_MINUTES)
    last = _instant(fact.last_activity_at) if fact is not None else None
    return any(t is not None and now - t <= window for t in (last, *also))


def _module_word(fact, now: datetime) -> str:
    if fact is None:
        return "无记录"
    if fact.presence == "unreachable":
        return "掉线"
    if fact.presence == "offline":  # the app put the session away; its coordinator wakes it (rehearsal2-fixes)
        return "停着"
    return "在忙" if _busy(fact, now) else "停着"


def _unreachable(fact, entry: dict) -> bool:
    """掉线 only when nothing can reach the session (rehearsal2-fixes).

    Claude's app stops an idle session's process (agent-relay reports `stopped`); a desktop
    message wakes it, so it is 掉线 only without a desktop session or wake binding to wake it by.
    """
    if fact is None or fact.presence not in ("offline", "unreachable"):
        return False
    if fact.presence == "unreachable" or fact.host_app == "codex":
        return True
    return not (entry.get("desktopSession") or fact.wake_bound)


def _crew_modules(read, relay, now: datetime) -> tuple:
    if read is None or read.status != "ok":
        return ()
    agents = relay.agents if relay is not None else None
    return tuple((m, _module_word(agents.get(m.relay_name), now) if agents is not None else None)
                 for m in read.modules if m.stage != "merged")


def _facts(g, relay, maps, snap, crews=None, now: datetime | None = None) -> dict[str, _Facts]:
    ticket_doc = store.read_state(g, "tickets").get("tickets", {})
    pending = items.pending(g)
    out = {}
    left = store.left_relays(g)  # a session that left is no line any more (rehearsal2-fixes)
    for entry in store.roster(g):
        name = entry["relayName"]
        if entry["role"] == "hub" or name in left:
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
        crew_read = (crews or {}).get(name) if entry.get("crewCoordinator") else None
        modules = _crew_modules(crew_read, relay, now)
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
            crew=crew_read, modules=modules,
            crew_busy=any(word == "在忙" and m.suspended is None for m, word in modules),
        )
    return out


def _is_working(f: _Facts, now: datetime) -> bool:
    if f.fact is not None and f.fact.presence == "offline":  # its process is stopped (rehearsal2-fixes)
        return False
    return _busy(f.fact, now, (f.changed,))


def _has_open_work(f: _Facts) -> bool:
    """A coordinator's own activeModule says nothing while modules run in parallel (crew-line-status)."""
    if f.entry.get("crewCoordinator"):
        return False
    m = f.module
    return (m is not None and m.step == "build" and m.review_plan == "approved"
            and m.progress_done < m.progress_total)


def _target_name(f: _Facts, t: dict, names: dict[str, str]) -> str:
    """The waited-on session's short name when the roster knows it."""
    return names.get(t.get("targetRelay") or t["target"], t["target"])


def _state(f: _Facts, now: datetime, stale=frozenset(), names: dict | None = None) -> LineState:
    """The seven words, first match wins (requirement section 12 item 14).

    Possibly stale tickets do not make a line blocked (relay-presence-and-doubt).
    """
    presence = f.fact.presence if f.fact is not None else None
    if _unreachable(f.fact, f.entry):
        return LineState("offline", "掉线")
    if presence == "needs-user":
        return LineState("needs-user", "等你确认")
    if f.crew_busy:
        return LineState("working", "干活中")
    live = [t for t in f.tickets if t["no"] not in stale]
    if live:
        t = live[0]
        target = _target_name(f, t, names or {})
        return LineState("blocked", f"阻塞：等 {target}", target=target, since=t["sentAt"])
    if f.asks:
        it = f.asks[0]
        what = "等你去会话操作" if items.is_go_to_session(it) else "等你决定"  # loop-detection (go-to-session)
        return LineState("blocked", f"阻塞：{what} #{it['no']}", item=it["no"], since=it["receivedAt"])
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
    return LineState("idle", NO_RECORD)


NO_RECORD = "无活动记录（agent-relay 没有它的数据）"
NO_RELAY = "本次没有 agent-relay 状态，无法判断"  # not read this time, not missing (wait-honesty-and-briefs A3)


def _review_word(review) -> str | None:
    """module-crew's review state in place of the stage word (review-nearby R1)."""
    if review is None:
        return None
    state, rounds = review
    if state == "rework":
        return f"返工中（审查第 {rounds} 轮）"
    return f"审查中（第 {rounds + 1} 轮）" if rounds else "审查中"


def _crew_suffix(f: _Facts, state: LineState, stale, names: dict) -> str:
    """The module list after a coordinator line's state (crew-line-status)."""
    if f.crew is None:
        return ""
    if f.crew.status != "ok":
        return f"（模块状态未知：{f.crew.reason}）"
    parts = []
    for m, word in f.modules:
        if m.suspended is not None:
            reason = m.suspended if len(m.suspended) <= SUSPEND_CLIP else m.suspended[:SUSPEND_CLIP] + "…"
            parts.append(f"{m.module} 挂起：{reason}")
        else:
            stage = _review_word(m.review) or CREW_STAGES.get(m.stage, m.stage)
            parts.append(f"{m.module} {word}·{stage}" if word else f"{m.module} {stage}")
    text = "模块 " + "、".join(parts) if parts else "没有在用的模块会话"
    live = [t for t in f.tickets if t["no"] not in stale]
    if state.word == "working" and live:
        grouped: dict[str, list[int]] = {}
        for t in live:
            grouped.setdefault(_target_name(f, t, names), []).append(t["no"])
        text += "；还在等 " + "，".join(f"{who} " + "、".join(f"#{n}" for n in nos) for who, nos in grouped.items())
    return f"（{text}）"


def _short(f: _Facts) -> str:
    return f.entry["shortName"]


def _session_signals(facts: dict[str, _Facts], lines: dict[str, LineState], now: datetime,
                     stale=frozenset(), relay_read: bool = True) -> list[Signal]:
    """Signals 1, 2, 4, 5, 10 and 11: waiting chains, message backlogs and doubtful deliveries."""
    out = []
    open_count = sum(1 for f in facts.values() for t in f.tickets if t["no"] not in stale)
    # Without agent-relay this time nobody can be seen working, so no verdict (relay-presence-and-doubt).
    # A coordinator line whose modules cannot be read gives no verdict either (crew-line-status).
    crew_unknown = any(f.crew is not None and f.crew.status != "ok" for f in facts.values())
    if relay_read and not crew_unknown and open_count and all(state.word != "working" for state in lines.values()):
        out.append(Signal(1, "all-waiting", tuple(sorted(facts)),
                          f"全线互等：所有会话都没在干活，还有 {open_count} 条等待记录没关"))
    for name, f in facts.items():
        fact = f.fact
        for t in f.tickets:
            target = t.get("targetRelay")
            if (target and fact is not None and target in fact.waiting_from
                    and lines[name].word != "working"):
                out.append(Signal(2, "delivered-not-picked", (name, target),
                                  f"交付了没人接：{t['target']} 已发消息给 {_short(f)}，"
                                  f"{_short(f)} 还没去取（{_short(f)} 在等 {t['target']}）"))
        if fact is not None and fact.doubtful_ids:
            ids = "、".join(f"#{i}" for i in fact.doubtful_ids)
            out.append(Signal(11, "delivery-doubt", (name,), deps.sourced(
                f"{_short(f)} 有 {len(fact.doubtful_ids)} 条消息送达存疑（{ids}）", "agent-relay")))
        if fact is None or not fact.waiting_count:
            continue
        if fact.presence in ("offline", "unreachable"):
            text = (f"{_short(f)} 掉线，有 {fact.waiting_count} 条消息送不进去" if _unreachable(fact, f.entry)
                    else f"{_short(f)} 停着，有 {fact.waiting_count} 条消息等它")
            out.append(Signal(4, "offline-backlog", (name,), text))
        elif fact.activity == "idle":
            out.append(Signal(5, "idle-backlog", (name,), f"{_short(f)} 空闲，有 {fact.waiting_count} 条消息没读"))
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
                                  f"最早一条已等 {int(waited)} 分钟（来源：Codex 桌面版）"))
    return out


def _slow_threshold(m, history: str) -> float:
    """Minutes without progress before signal 8 (requirement section 12 item 3)."""
    if history == "complete" and (m.tick_commits or 0) >= 2 and m.first_tick_at and m.last_tick_at:
        average = (_instant(m.last_tick_at) - _instant(m.first_tick_at)).total_seconds() / 60 / (m.tick_commits - 1)
        return max(SLOW_FACTOR * average, SLOW_FLOOR_MINUTES)
    return SLOW_FALLBACK_MINUTES


def _progress_signals(g, facts: dict[str, _Facts], lines: dict[str, LineState], snap: dict,
                      now: datetime) -> list[Signal]:
    """Signals 3, 6, 7, 8 and 9: progress, suspension, rework and orphan waits."""
    out = []
    for name, f in facts.items():
        if lines[name].word == "stalled":
            m = f.module
            out.append(Signal(3, "silent-stop", (name,),
                              f"{_short(f)} {lines[name].text}：当前模块 {m.id} 还有 "
                              f"{m.progress_total - m.progress_done} 项没勾，也没在等任何人"))
        if f.read is None or f.read.status != "ok":
            continue
        line_map = f.read.map
        for b in line_map.bottlenecks:
            out.append(Signal(6, "suspended-blocks", (name,),
                              f"{_short(f)} 的 {b.id} 挂起（{b.suspended_reason or '未记原因'}）"
                              f"→ 挡住 {len(b.blocks)} 个：{'、'.join(b.blocks)}"))
        if lines[name].word == "offline":
            continue
        changed = snap["sessions"].get(name, {})
        for m in line_map.modules:
            if m.step != "build" or m.progress_done >= m.progress_total:
                continue
            times = [_instant(changed.get(m.id, {}).get("changedAt"))]
            if line_map.history == "complete":
                times.append(_instant(m.last_tick_at))
            times = [t for t in times if t is not None]
            if not times:
                continue
            idle = (now - max(times)).total_seconds() / 60
            if idle >= _slow_threshold(m, line_map.history):
                out.append(Signal(8, "slow-progress", (name,),
                                  f"{_short(f)} 的 {m.id} 已 {_duration(idle)}没有新进展，明显慢于平时"))
    stats = reviews.round_stats(g)
    closed = [rounds for _, _, _, rounds in stats.closed]
    limit = (statistics.median(closed) + REWORK_MARGIN if len(closed) >= REWORK_HISTORY_MIN
             else REWORK_FALLBACK_ROUNDS)
    for ref, submitter, node, rounds in stats.open:
        if rounds >= limit:
            who = facts[submitter].entry["shortName"] if submitter in facts else submitter
            out.append(Signal(7, "rework", (submitter,),
                              f"{who} 的审查 {ref}（{node}）已来回 {rounds} 轮，超过本组常见水平"))
    ticket_doc = store.read_state(g, "tickets").get("tickets", {})
    for key, t in ticket_doc.items():
        # A coordinator keeps one wait per module by design (crew-line-status revision 1).
        waiter = facts.get(t["waiter"])
        if t["status"] != "open" or waiter is not None and waiter.entry.get("crewCoordinator"):
            continue
        later = [int(k) for k, o in ticket_doc.items() if o["waiter"] == t["waiter"]
                 and _instant(o["sentAt"]) > _instant(t["sentAt"])]
        if later:
            who = facts[t["waiter"]].entry["shortName"] if t["waiter"] in facts else t["waiter"]
            out.append(Signal(9, "orphan-wait", (t["waiter"],),
                              f"{who} 的等待记录 W{key}（等 {t['target']}）还开着，但它后来又开了新的等待 "
                              f"W{min(later)}"))
    return out


def assess(g: store.Group, now: str, relay=None, maps: dict | None = None,
           previous: dict | None = None, crews: dict | None = None) -> Assessment:
    maps = maps or {}
    snap = _new_snapshot(now, maps, previous)
    moment = _instant(now)
    facts = _facts(g, relay, maps, snap, crews, moment)
    stale = tickets.stale_numbers(g)  # waits moved past (wait-honesty-and-briefs A2) or whose item closed (I-11)
    names = {e["relayName"]: e["shortName"] for e in store.roster(g)}
    lines = {name: _state(f, moment, stale, names) for name, f in facts.items()}
    if relay is None:
        lines = {name: LineState(s.word, NO_RELAY) if s.text == NO_RECORD else s for name, s in lines.items()}
    lines = {name: replace(s, text=s.text + _crew_suffix(facts[name], s, stale, names)) for name, s in lines.items()}
    signals = (_session_signals(facts, lines, moment, stale, relay_read=relay is not None)
               + _progress_signals(g, facts, lines, snap, moment))
    return Assessment(lines, tuple(sorted(signals, key=lambda x: (x.no, x.sessions))), snap)
