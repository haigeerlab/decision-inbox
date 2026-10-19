"""Which module each question belongs to, and whether that module is going round in circles.

loop-detection (R21 DI-5, DI-6; see spec/loop-detection.md). Items are tagged once with a module; each
module in progress then gets its facts: how often it asked the user against its baseline (Spec + Plan +
gates.total), how many answers left it where it was, and how long it really worked (time waiting for the
user or for another line taken out). Facts only; the hub shows them and never blocks a line.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime

from decision_inbox import items, store

GIT_TIMEOUT = 3.0
_ENDED = ("closed", "withdrawn", "superseded")
DOMAIN = "loops"


@dataclass(frozen=True)
class Segment:
    start: str              # this answer
    end: str | None         # the next answer; None runs to now
    worked_until: str       # the next time the module asked after this answer, else now
    moved: bool | None      # a commit or a ticked task in the segment; None when unread
    closed: bool            # the module came back and asked again after this answer


@dataclass(frozen=True)
class ModuleLoop:
    key: str                # "<line relay name>|<module>"
    line: str
    module: str
    project: str
    items: tuple            # this module's items, oldest first (every status)
    asked: int              # n: not counting go-to-session or superseded items
    baseline: int | None    # M = 2 + gates.total; None when spec-guard does not say
    over: int               # k
    segments: tuple | None
    still: int | None       # j: answers after which nothing moved
    worked_hours: float | None
    progress: tuple | None  # (done, total)
    last_progress: str | None
    unread: str | None      # why the progress could not be read
    ready: tuple = ()       # modules ready to start on that line (option A lists them)
    waits: tuple = ()       # (start, end) spans spent waiting for the user or another line
    hit: str | None = None  # why it looks like going round in circles


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _hours(start: str, end: str) -> float:
    return (_instant(end) - _instant(start)).total_seconds() / 3600


def read_commits(repo: str, since: str) -> list[str] | None:
    """Commit times on HEAD's first-parent chain since `since`, oldest first; None when git cannot say."""
    try:
        out = subprocess.run(["git", "-C", repo, "log", "--first-parent", "--format=%cI", f"--since={since}", "HEAD"],
                             capture_output=True, text=True, timeout=GIT_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return sorted(line for line in out.stdout.split() if line)


def _ok_map(maps: dict, name: str):
    read = (maps or {}).get(name)
    return read.map if getattr(read, "status", None) == "ok" else None


def _module_for(it: dict, entry: dict | None, maps: dict, crews: dict) -> str | None:
    if it.get("approvalModule"):
        return it["approvalModule"]
    if it.get("multi") or entry is None or entry.get("role") != "dev":
        return None
    if entry.get("crewCoordinator"):
        read = (crews or {}).get(entry["relayName"])
        first = (it.get("decide") or "").split("\n")[0].strip()
        for m in getattr(read, "modules", ()) if getattr(read, "status", None) == "ok" else ():
            if first and any((w.decide or "").strip() == first for w in m.waits):
                return m.module
        return None
    line_map = _ok_map(maps, entry["relayName"])
    return line_map.active_module if line_map is not None else None


def tag(g: store.Group, maps: dict, crews: dict) -> None:
    """Give each untagged item its module, once; a tag never changes afterwards."""
    with g.transaction() as tx:
        doc = tx.read_state(items.DOMAIN)
        changed = False
        for no, it in (doc.get("items") or {}).items():
            if "module" in it:
                continue
            it["module"] = _module_for(it, store.find_session(g, relay_name=it["sender"]), maps, crews)
            tx.append_event("items.module-tagged", ref=int(no), actor="system", data={"module": it["module"]})
            changed = True
        if changed:
            tx.write_state(items.DOMAIN, doc)


def _wait_end(it: dict, now: str) -> str:
    if it.get("answers"):
        return it["answers"][0]["at"]
    ended = [it["statusAt"][s] for s in _ENDED if s in it.get("statusAt", {})]
    return min(ended, key=_instant) if ended else now


def _worked(start: str | None, now: str, waits: list[tuple[str, str]]) -> float | None:
    """Hours from start to now with the union of the waiting spans taken out."""
    if start is None:
        return None
    spans = sorted((max(_instant(a), _instant(start)), min(_instant(b), _instant(now))) for a, b in waits)
    taken, reach = 0.0, _instant(start)
    for a, b in spans:
        a = max(a, reach)
        if b > a:
            taken += (b - a).total_seconds()
            reach = b
    return _hours(start, now) - taken / 3600


def _segments(answers: list[tuple[str, bool | None]], asks: list[str], now: str) -> tuple[Segment, ...]:
    out = []
    for i, (start, moved) in enumerate(answers):
        later = sorted((a for a in asks if _instant(a) > _instant(start)), key=_instant)
        end = answers[i + 1][0] if i + 1 < len(answers) else None
        out.append(Segment(start, end, later[0] if later else now, moved, bool(later)))
    return tuple(out)


def _moved_by_commits(starts: list[str], commits: list[str], now: str) -> list[bool]:
    ends = starts[1:] + [now]
    return [any(_instant(a) <= _instant(c) < _instant(b) for c in commits) for a, b in zip(starts, ends)]


def _crew_waits(m, now: str) -> list[tuple[str, str]]:
    """module-crew's own record of waiting: each ask until its answer, an open 【等待用户】 until now."""
    answered = {a.ref: a.at for a in m.answers or ()}
    spans = [(at, answered[ref]) for ref, at in m.ask_refs if ref in answered]
    spans += [(w.at, answered.get(w.ref) or now) for w in m.waits
              if w.at and (w.ref in answered or w.state == "open")]
    return spans


def worked_since(f: ModuleLoop, since: str, now: str) -> float:
    """Hours of work from `since` to now, waiting taken out (stall-and-patrol's stall time, loop-detection 7)."""
    return _worked(since, now, list(f.waits))


def _fact(line_map, module: str):
    return next((m for m in line_map.modules if m.id == module), None) if line_map is not None else None


def _build(key, line, module, project, own, fact, segments, unread, start, now, waits, last_progress, line_map):
    asked = len([it for it in own if not items.is_go_to_session(it) and it["status"] != "superseded"])
    baseline = 2 + fact.gates_total if fact is not None and fact.gates_total is not None else None
    still = None if segments is None or any(s.moved is None for s in segments) \
        else len([s for s in segments if s.moved is False])
    if segments is not None and still is None and unread is None:
        unread = "进度读不到"
    return ModuleLoop(key, line, module, project, tuple(own), asked, baseline,
                      max(0, asked - baseline) if baseline is not None else 0, segments, still,
                      _worked(start, now, waits), (fact.progress_done, fact.progress_total) if fact else None,
                      last_progress, unread,
                      tuple(m.id for m in line_map.modules if m.status == "ready") if line_map is not None else (),
                      tuple(waits))


def _later(*values):
    found = [v for v in values if v]
    return max(found, key=_instant) if found else None


def _hit(segments, cfg: dict) -> str | None:
    """① the last N answers the module came back after left it where it was; ② that idle work adds up."""
    if not segments or any(s.moved is None for s in segments):
        return None
    closed = [s for s in segments if s.closed]
    n = int(cfg["loopAnswers"])
    if len(closed) >= n and all(s.moved is False for s in closed[-n:]):
        return f"你答了 {n} 次进度没动"
    idle = sum(_hours(s.start, s.worked_until) for s in segments if s.moved is False)
    if idle >= cfg["loopHours"]:
        return f"没进展的出手时间累计 {int(idle)} 小时"
    return None


def quiet(g: store.Group, key: str, now: str, hours: float) -> None:
    """「继续等」: no hint for this module for `hours` (DI-6 C)."""
    from datetime import timedelta
    until = (_instant(now) + timedelta(hours=hours)).isoformat()
    with g.transaction() as tx:
        doc = tx.read_state(DOMAIN)
        doc.setdefault("quiet", {})[key] = until
        tx.append_event("loops.quiet", ref=None, actor="user", data={"module": key, "until": until})
        tx.write_state(DOMAIN, doc)


def _judged(g: store.Group, found: list[ModuleLoop], now: str) -> list[ModuleLoop]:
    from dataclasses import replace
    from decision_inbox import stall
    cfg = stall.settings(g)
    quiet_until = store.read_state(g, DOMAIN).get("quiet", {})
    out = []
    for f in found:
        until = quiet_until.get(f.key)
        hushed = until is not None and _instant(now) < _instant(until)
        out.append(replace(f, hit=None if hushed else _hit(f.segments, cfg)))
    return out


def facts(g: store.Group, now: str, maps: dict, crews: dict, git=read_commits) -> list[ModuleLoop]:
    """Every module in progress, judged: the facts below, then whether it looks like going round in circles."""
    return _judged(g, _facts(g, now, maps, crews, git), now)


def looping_items(found: list[ModuleLoop]) -> dict[int, ModuleLoop]:
    """Open items that carry the hint: every open, non go-to-session item of a module that is hit."""
    return {it["no"]: f for f in found if f.hit for it in f.items
            if it["status"] == "pending" and not items.is_go_to_session(it)}


def _facts(g: store.Group, now: str, maps: dict, crews: dict, git=read_commits) -> list[ModuleLoop]:
    """One ModuleLoop per module in progress: a plain dev line's activeModule, a crew's unmerged modules."""
    every = sorted((dict(it, no=int(no)) for no, it in store.read_state(g, items.DOMAIN).get("items", {}).items()),
                   key=lambda it: _instant(it["receivedAt"]))
    tickets = store.read_state(g, "tickets").get("tickets", {})
    left = store.left_relays(g)
    out = []
    for entry in store.roster(g):
        name = entry["relayName"]
        if entry.get("role") != "dev" or name in left:
            continue
        line_map = _ok_map(maps, name)
        project = (line_map.title if line_map is not None and line_map.title else entry["shortName"])
        if entry.get("crewCoordinator"):
            read = (crews or {}).get(name)
            for m in getattr(read, "modules", ()) if getattr(read, "status", None) == "ok" else ():
                if m.stage in ("merged",) or m.suspended:
                    continue
                own = [it for it in every if it["sender"] == name and it.get("module") == m.module]
                waits = [(it["receivedAt"], _wait_end(it, now)) for it in own] + _crew_waits(m, now)
                if m.answers is None:
                    segments, unread = None, "进度读不到（module-crew 早于 0.5.0）"
                else:
                    moved = [None if a.commits_after is None or a.ticks_after is None
                             else bool(a.commits_after or a.ticks_after) for a in m.answers]
                    asks = [a for _, a in m.ask_refs] + [w.at for w in m.waits if w.at]
                    segments, unread = _segments([(a.at, mv) for a, mv in zip(m.answers, moved)], asks, now), None
                out.append(_build(f"{name}|{m.module}", name, m.module, project, own, _fact(line_map, m.module),
                                  segments, unread, m.started_at, now, waits, m.last_commit_at, line_map))
            continue
        if line_map is None or line_map.stage == "DONE" or not line_map.active_module:
            continue
        module = line_map.active_module
        own = [it for it in every if it["sender"] == name and it.get("module") == module]
        start = own[0]["receivedAt"] if own else None
        waits = [(it["receivedAt"], _wait_end(it, now)) for it in own]
        waits += [(t["sentAt"], t["close"]["at"] if t.get("close") else now) for t in tickets.values()
                  if t.get("waiter") == name and t.get("sentAt")]
        asked_items = [it for it in own if not items.is_go_to_session(it)]
        starts = sorted((a["at"] for it in asked_items for a in it.get("answers", [])), key=_instant)
        commits = git(entry["repo"], start) if start and entry.get("repo") else None
        if not starts:
            segments, unread = (), None
        elif commits is None:
            segments, unread = None, "进度读不到（git 读不到）"
        else:
            moved = _moved_by_commits(starts, commits, now)
            segments, unread = _segments(list(zip(starts, moved)), [it["receivedAt"] for it in asked_items], now), None
        fact = _fact(line_map, module)
        last = _later(commits[-1] if commits else None, fact.last_tick_at if fact else None)
        out.append(_build(f"{name}|{module}", name, module, project, own, fact, segments, unread, start, now,
                          waits, last, line_map))
    return out

