"""Line states and stuck signals (see spec/line-health.md).

Pure read: everything comes in through `assess`'s arguments or read-only
store reads; the new progress snapshot is returned for patrol to save.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from decision_inbox import store

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


def assess(g: store.Group, now: str, relay=None, maps: dict | None = None,
           previous: dict | None = None) -> Assessment:
    maps = maps or {}
    return Assessment({}, (), _new_snapshot(now, maps, previous))
