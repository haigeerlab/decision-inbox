"""patrol-watch (stage-c-fixes DI-11): a launchd job that tells the user when the patrol has gone quiet.

It runs outside the hub and the patrol session, so it keeps working when both are idle. It only tells the
user (a macOS notification naming the patrol session and what to do); it never runs the patrol itself.
"""

from __future__ import annotations

import os
import plistlib
import re
import subprocess
import sys
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
# patrol-watch-runtime: launchd agents may not read these (macOS privacy), so the job never runs from them
PROTECTED = ("Documents", "Desktop", "Downloads")


def _plist(group: str) -> str:
    """The job runs the runtime copy (install.write_runtime) with the python that installed it: launchd's own
    PATH only has /usr/bin/python3, which may be older than 3.10."""
    env = {"PATH": f"{os.path.dirname(sys.executable)}:/usr/bin:/bin"}
    if os.environ.get("DECISION_INBOX_HOME"):
        env["DECISION_INBOX_HOME"] = os.environ["DECISION_INBOX_HOME"]
    log = str(store.root_dir() / group / "patrol-watch.log")
    return plistlib.dumps({
        "Label": label(group),
        "ProgramArguments": [str(runtime_cli()), "patrol-watch", group],
        "EnvironmentVariables": env,
        "StartInterval": INTERVAL_SECONDS,
        "RunAtLoad": True,
        "StandardOutPath": log,
        "StandardErrorPath": log,
    }).decode("utf-8")


def runtime_cli() -> Path:
    return install_mod.runtime_dir() / "bin" / "decision-inbox"


def _protected(path) -> str | None:
    """The protected home folder path lies in, if any."""
    real = os.path.realpath(path)
    for name in PROTECTED:
        root = os.path.realpath(Path.home() / name)
        if real == root or real.startswith(root.rstrip(os.sep) + os.sep):
            return name
    return None


@dataclass
class Plan:
    path: Path
    content: str
    changed: bool
    error: str | None = None
    refused: bool = False  # nothing was written: the job could not run from where it would be


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
    content = _plist(group)
    old = path.read_text(encoding="utf-8") if path.is_file() else None
    plan = Plan(path, content, old != content)
    for what, where in (("python", sys.executable), ("运行副本", install_mod.runtime_dir())):
        folder = _protected(where)
        if folder:
            plan.error = (f"{what}（{where}）在 ~/{folder} 下，launchd 没有权限读这里（macOS 隐私保护），"
                          f"装了也跑不起来；换一个不在 ~/Documents、~/Desktop、~/Downloads 下的")
            plan.refused = True
            return plan
    if confirm:
        install_mod.write_runtime(install_mod.plugin_root())
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


_LAST_EXIT_RE = re.compile(r"last exit code = (-?\d+)")


def last_exit(group: str) -> int | None:
    """The job's last exit code from launchctl print; None when it has not exited yet or is not loaded."""
    r = _launchctl("print", f"{_domain()}/{label(group)}")
    m = _LAST_EXIT_RE.search(r.stdout) if r is not None and r.returncode == 0 else None
    return int(m.group(1)) if m else None


def program(group: str) -> str | None:
    """What the installed plist runs (its first argument)."""
    try:
        args = plistlib.loads(plist_path(group).read_bytes()).get("ProgramArguments") or [None]
    except (OSError, plistlib.InvalidFileException, ValueError, AttributeError):
        return None
    return args[0]


def log_tail(group: str) -> str:
    try:
        lines = (store.root_dir() / group / "patrol-watch.log").read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return ""
    return next((line.strip() for line in reversed(lines) if line.strip()), "")
