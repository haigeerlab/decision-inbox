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
class Answer:
    """One user answer to a module (module-crew 0.5.0 `answers`); the two counts are None when unread."""
    ref: str
    at: str
    commits_after: int | None
    ticks_after: int | None


@dataclass(frozen=True)
class Wait:
    """One 【等待用户】 the module raised (`waitUser`), open or closed."""
    ref: str
    state: str
    decide: str | None
    at: str | None


@dataclass(frozen=True)
class Module:
    module: str
    relay_name: str
    stage: str
    suspended: str | None
    review: tuple[str, int] | None = None  # (reviewing|rework, round) from 0.3.0's optional field (review-nearby)
    # module-crew 0.4.0 stall facts (crew-stall-facts); absent on 0.3.x or when the shape is odd
    started_at: str | None = None
    last_commit_at: str | None = None
    commits_error: str | None = None
    asks: tuple[tuple[str, tuple[str, ...]], ...] = ()   # (node, ats) per node module-crew counted
    waiting_user: bool = False                            # an open 【等待用户】 from this module
    # loop-detection: module-crew 0.5.0 answers (None before 0.5.0) and the waitUser rows themselves
    ask_refs: tuple[tuple[str, str], ...] = ()            # (ref, at) of every submission asked
    waits: tuple[Wait, ...] = ()
    answers: tuple[Answer, ...] | None = None


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


REVIEW_STATES = ("reviewing", "rework")


def _review(value) -> tuple[str, int] | None:
    """The optional review field; an odd shape is read as absent so a module-crew tweak never blinds a line."""
    if not isinstance(value, dict) or value.get("state") not in REVIEW_STATES:
        return None
    rounds = value.get("round")
    if type(rounds) is not int or rounds < 0:
        return None
    return value["state"], rounds


def _text(value) -> str | None:
    return value if isinstance(value, str) else None


def _stall_facts(row: dict) -> dict:
    """The 0.4.0 stall facts of one row; anything not shaped as module-crew documents is left out."""
    commits = row.get("commits") if isinstance(row.get("commits"), dict) else {}
    last = commits.get("last") if isinstance(commits.get("last"), dict) else {}
    asks = []
    for ask in row.get("asks") if isinstance(row.get("asks"), list) else ():
        ats = ask.get("ats") if isinstance(ask, dict) else None
        if isinstance(ask, dict) and isinstance(ask.get("node"), str) and isinstance(ats, list) and ats \
                and all(isinstance(a, str) for a in ats):
            asks.append((ask["node"], tuple(ats)))
    waits = row.get("waitUser") if isinstance(row.get("waitUser"), list) else ()
    return {"started_at": _text(row.get("startedAt")), "last_commit_at": _text(last.get("at")),
            "commits_error": _text(commits.get("error")), "asks": tuple(asks),
            "waiting_user": any(isinstance(w, dict) and w.get("state") == "open" for w in waits),
            "ask_refs": _ask_refs(row.get("asks")),
            "waits": tuple(Wait(w["ref"], w["state"], _text(w.get("decide")), _text(w.get("at"))) for w in waits
                           if isinstance(w, dict) and isinstance(w.get("ref"), str)
                           and isinstance(w.get("state"), str)),
            "answers": _answers(row.get("answers"))}


def _count(value) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _ask_refs(asks) -> tuple[tuple[str, str], ...]:
    out = []
    for ask in asks if isinstance(asks, list) else ():
        refs, ats = (ask.get("refs"), ask.get("ats")) if isinstance(ask, dict) else (None, None)
        if isinstance(refs, list) and isinstance(ats, list) and len(refs) == len(ats):
            out += [(r, a) for r, a in zip(refs, ats) if isinstance(r, str) and isinstance(a, str)]
    return tuple(sorted(out, key=lambda ra: ra[1]))


def _answers(value) -> tuple[Answer, ...] | None:
    """0.5.0's answers; not a list means not reported (None), an odd entry is dropped."""
    if not isinstance(value, list):
        return None
    return tuple(Answer(a["ref"], a["at"], _count(a.get("commitsAfter")), _count(a.get("ticksAfter")))
                 for a in value if isinstance(a, dict) and isinstance(a.get("ref"), str)
                 and isinstance(a.get("at"), str))


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
        modules.append(Module(row["module"], row["relayName"], row["stage"], row["suspended"],
                              _review(row.get("review")), **_stall_facts(row)))
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
