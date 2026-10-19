"""patrol-watch (stage-c-fixes DI-11): a launchd job that tells the user when the patrol has gone quiet.

It runs outside the hub and the patrol session, so it keeps working when both are idle. It only tells the
user (a macOS notification naming the patrol session and what to do); it never runs the patrol itself.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from decision_inbox import hub, store
from decision_inbox import install as install_mod

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


# --- the launchd job (stage-c-fixes assumption 5): previewed by onboard watch, removed by teardown ---

INTERVAL_SECONDS = 300
PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{cli}</string>
    <string>patrol-watch</string>
    <string>{group}</string>
  </array>
  <key>StartInterval</key>
  <integer>{interval}</integer>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>{log}</string>
  <key>StandardErrorPath</key>
  <string>{log}</string>
</dict>
</plist>
"""


@dataclass
class Plan:
    path: Path
    content: str
    changed: bool
    error: str | None = None


def label(group: str) -> str:
    return f"com.haigeerlab.decision-inbox.patrol-watch.{group}"


def plist_path(group: str) -> Path:
    base = os.environ.get("DECISION_INBOX_LAUNCH_AGENTS")
    return (Path(base) if base else Path.home() / "Library" / "LaunchAgents") / f"{label(group)}.plist"


def _launchctl(*args: str) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run([os.environ.get("DECISION_INBOX_LAUNCHCTL", "launchctl"), *args],
                              capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return None


def _domain() -> str:
    return f"gui/{os.getuid()}"


def install(group: str, confirm: bool) -> Plan:
    """Preview, and with confirm write and load, the launchd job that runs patrol-watch every five minutes."""
    store.validate_name(group)
    path = plist_path(group)
    content = PLIST.format(label=label(group), cli=install_mod.cli(), group=group, interval=INTERVAL_SECONDS,
                           log=store.root_dir() / group / "patrol-watch.log")
    old = path.read_text(encoding="utf-8") if path.is_file() else None
    plan = Plan(path, content, old != content)
    if confirm:
        path.parent.mkdir(parents=True, exist_ok=True)
        store._atomic_write_bytes(path, content.encode("utf-8"))
        _launchctl("bootout", f"{_domain()}/{label(group)}")  # a rerun reloads it; not loaded is fine
        r = _launchctl("bootstrap", _domain(), str(path))
        if r is None or r.returncode != 0:
            plan.error = (r.stderr.strip() if r is not None else "") or "launchctl 没有加载它"
    return plan


def uninstall(group: str, confirm: bool) -> bool:
    """True when there was a job to remove (with confirm, it is gone)."""
    path = plist_path(group)
    if not path.is_file():
        return False
    if confirm:
        _launchctl("bootout", f"{_domain()}/{label(group)}")
        path.unlink()
    return True


def loaded(group: str) -> bool:
    r = _launchctl("print", f"{_domain()}/{label(group)}")
    return r is not None and r.returncode == 0
