"""Read-only queries /lines, /flow and /item (see spec/query-commands.md).

Facts come from line-health, decision-queue, wait-tickets and relay-reader;
nothing here writes state, sends messages or wakes anyone.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from decision_inbox import items, store, tickets
from decision_inbox.view import ago


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _clock(value: str) -> str:
    return _instant(value).astimezone().strftime("%H:%M")


def _dev_lines(g: store.Group) -> list[dict]:
    return [e for e in store.roster(g) if e["role"] == "dev"]


@dataclass(frozen=True)
class _Edge:
    waiter: str      # relay name
    target: str      # relay name
    ticket: int
    sent_at: str


def _wait_graph(g: store.Group, now: str) -> list[_Edge]:
    """Open tickets between sessions on the roster; waits on the user stay out of the graph."""
    raw = store.read_state(g, tickets.DOMAIN).get("tickets", {})
    edges = []
    for t in tickets.open_tickets(g, now):
        entry = store.find_session(g, short_name=t.target)
        if entry is not None and store.find_session(g, relay_name=t.waiter) is not None:
            edges.append(_Edge(t.waiter, entry["relayName"], t.no, raw[str(t.no)]["sentAt"]))
    return edges


def _module_text(read) -> str:
    if read is None:
        return "当前模块：未读取"
    if read.status != "ok":
        return read.reason or read.status
    line_map = read.map
    current = next((m for m in line_map.modules if m.id == line_map.active_module), None)
    if current is not None:
        return f"当前模块 {current.id}（{current.progress_done}/{current.progress_total}）"
    return "全部模块已完成" if line_map.stage == "DONE" else "当前模块：无"


def _last_output(name: str, read, assessment, now: str) -> str:
    """Newest of the snapshot's changedAt and, with complete history, spec-guard's lastTickAt."""
    times = [v["changedAt"] for v in assessment.snapshot.get("sessions", {}).get(name, {}).values()
             if v.get("changedAt")]
    if read is not None and read.status == "ok" and read.map.history == "complete":
        times += [m.last_tick_at for m in read.map.modules if m.last_tick_at]
    if not times:
        return "最后产出：无记录"
    last = max(times, key=_instant)
    return f"最后产出 {_clock(last)}（{ago(now, last)}）"


def _unread(name: str, relay) -> str:
    fact = relay.agents.get(name) if relay is not None else None
    count = fact.waiting_count if fact is not None else None
    return f"未读 {count}" if count is not None else "未读 未知"


def _waiting_for(g: store.Group, name: str, now: str) -> str:
    parts = [f"你（#{it['no']}）" for it in items.pending(g) if it["sender"] == name and it["fullyStopped"]]
    for t in tickets.open_tickets(g, now):
        if t.waiter != name:
            continue
        if t.target in tickets.USER_TARGETS:
            if not parts:
                parts.append("你")
        elif t.target not in parts:
            parts.append(t.target)
    return "、".join(parts) or "—"


def _join(parts: list[str]) -> str:
    """Spec examples drop the space between a full-width ）and the next ·."""
    return " · ".join(parts).replace("） · ", "）· ")


def render_lines(g: store.Group, now: str, assessment, relay=None, maps: dict | None = None) -> str:
    """/lines: one row per development line (role dev), roster order."""
    maps = maps or {}
    rows = []
    for entry in _dev_lines(g):
        name = entry["relayName"]
        state = assessment.lines.get(name)
        read = maps.get(name)
        rows.append(_join([
            entry["shortName"], state.text if state else "无状态",
            _module_text(read), _last_output(name, read, assessment, now),
            _unread(name, relay), f"在等：{_waiting_for(g, name, now)}",
        ]))
    return "\n".join(rows)
