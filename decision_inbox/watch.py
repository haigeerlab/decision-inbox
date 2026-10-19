"""patrol-watch (stage-c-fixes DI-11): a launchd job that tells the user when the patrol has gone quiet.

It runs outside the hub and the patrol session, so it keeps working when both are idle. It only tells the
user (a macOS notification naming the patrol session and what to do); it never runs the patrol itself.
"""

from __future__ import annotations

import os
import re
import subprocess
from datetime import datetime

from decision_inbox import hub, store

DOMAIN = "patrol-watch"
TITLE = "决策收件箱：巡视停了"
REPEAT_MINUTES = 30
_SOURCE_RE = re.compile(r"（来源：[^）]*）$")


def desktop_notify(title: str, text: str) -> bool:
    """A macOS notification; the text is an argument, never script (rehearsal2-fixes)."""
    osascript = os.environ.get("DECISION_INBOX_OSASCRIPT", "osascript")
    script = ["-e", "on run argv", "-e", "display notification (item 1 of argv) with title (item 2 of argv)",
              "-e", "end run"]
    try:
        r = subprocess.run([osascript, *script, text, title], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return r.returncode == 0


def _minutes(now: str, then: str) -> float:
    def instant(v):
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    return (instant(now) - instant(then)).total_seconds() / 60


def check(g: store.Group, now: str, send=desktop_notify) -> str | None:
    """The notification text when one went out this run; at most one per REPEAT_MINUTES while the patrol is quiet."""
    alarm = hub.patrol_alarm(g, now)
    last = store.read_state(g, DOMAIN).get("lastNotifiedAt")
    if alarm is None:
        if last:
            with g.transaction() as tx:
                tx.write_state(DOMAIN, {})
                tx.append_event("patrol-watch.back", ref=None, actor="system", data={"at": now})
        return None
    if last and _minutes(now, last) < REPEAT_MINUTES:
        return None
    text = _SOURCE_RE.sub("", alarm.removeprefix("⚠ "))
    if not send(TITLE, text):
        return None
    with g.transaction() as tx:
        tx.write_state(DOMAIN, {"lastNotifiedAt": now})
        tx.append_event("patrol-watch.notified", ref=None, actor="system", data={"at": now})
    return text
