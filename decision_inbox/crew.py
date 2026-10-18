"""Read-only access to module-crew's published sessions output (see spec/crew-line-status.md).

Only the command named in module-crew's interface.json is run, inside the
coordinator's repository; module-crew's state store is never read here.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import deps, store

PLUGIN = "module-crew"
INTERFACE_MAJOR = 1
SCHEMA_VERSION = 1
DEFAULT_TIMEOUT = 3.0


@dataclass(frozen=True)
class Module:
    module: str
    relay_name: str
    stage: str
    suspended: str | None


@dataclass(frozen=True)
class CrewRead:
    status: str                     # ok | unknown
    modules: tuple[Module, ...] = ()
    reason: str = ""


def _unknown(reason: str) -> CrewRead:
    return CrewRead("unknown", (), reason)


def _argv(root: str, sessions) -> list[str] | str:
    """The command from interface.json; its program must live inside the plugin root."""
    command = sessions.get("command") if isinstance(sessions, dict) else None
    if not (isinstance(command, list) and command and all(isinstance(a, str) for a in command)):
        return "interface.json 里没有 sessions.command"
    first = command[0]
    base = Path(root).resolve()
    program = (base / first).resolve()
    if not first or os.path.isabs(first) or base not in program.parents:
        return f"sessions.command 的程序不在插件目录里：{first!r}"
    return [str(program), *command[1:]]


def _parse(out: str) -> tuple[Module, ...] | str:
    try:
        doc = json.loads(out)
    except json.JSONDecodeError as e:
        return f"输出读不懂（{e}）"
    if not isinstance(doc, dict) or doc.get("schemaVersion") != SCHEMA_VERSION:
        version = doc.get("schemaVersion") if isinstance(doc, dict) else None
        return f"输出 schemaVersion {version}，本插件只认 {SCHEMA_VERSION}"
    modules = []
    for row in doc.get("sessions") or ():
        for key in ("module", "relayName", "stage"):
            if not isinstance(row, dict) or not isinstance(row.get(key), str):
                return f"输出缺少契约字段 {key}"
        if "suspended" not in row or not isinstance(row["suspended"], (str, type(None))):
            return "输出缺少契约字段 suspended"
        modules.append(Module(row["module"], row["relayName"], row["stage"], row["suspended"]))
    return tuple(modules)


def read_modules(repo: str, timeout: float = DEFAULT_TIMEOUT) -> CrewRead:
    """Run module-crew's sessions output in `repo`; anything short of a clean read is "unknown" with a reason."""
    found = deps.find(PLUGIN, repo)
    if isinstance(found, deps.NotFound):
        return _unknown(found.reason)
    interface = deps.read_interface(found.root, INTERFACE_MAJOR)
    if interface.state != "ok":
        return _unknown(interface.detail or "读不到 interface.json")
    sessions = interface.data.get("sessions")
    schema = sessions.get("schemaVersion") if isinstance(sessions, dict) else None
    if schema != SCHEMA_VERSION:
        return _unknown(f"interface.json 的 sessions schemaVersion {schema}，本插件只认 {SCHEMA_VERSION}")
    argv = _argv(found.root, sessions)
    if isinstance(argv, str):
        return _unknown(argv)
    try:
        done = subprocess.run(argv, cwd=repo, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return _unknown(f"sessions --json 超过 {timeout:g} 秒没有结束")
    except OSError as e:
        return _unknown(f"sessions --json 运行不了（{e}）")
    if done.returncode != 0:
        first = (done.stderr.strip().splitlines() or [""])[0]
        return _unknown(first or f"sessions --json 退出码 {done.returncode}")
    parsed = _parse(done.stdout)
    if isinstance(parsed, str):
        return _unknown(parsed)
    return CrewRead("ok", parsed)


def coordinators(g: store.Group) -> list[dict]:
    """Roster entries marked as module-crew coordinators that still take part."""
    left = store.left_relays(g)
    return [e for e in store.roster(g)
            if e.get("crewCoordinator") and e.get("repo") and e["relayName"] not in left]


def crews(g: store.Group) -> dict[str, CrewRead]:
    """One read per coordinator line, keyed by its relay name."""
    return {e["relayName"]: read_modules(e["repo"]) for e in coordinators(g)}
