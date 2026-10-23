"""agent-relay's script commands (patrol-launchd): what the launchd patrol runs instead of the MCP tools.

The commands come from agent-relay's interface.json `script` section (agent-relay >= 0.9.0, interface 2.8),
with `~` taken as the home directory, so nothing depends on PATH. The JSON they print is the same as the MCP
tools', so `relay.parse_*` read it; relay.py itself stays free of subprocess.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from decision_inbox import deps

UPGRADE_HINT = "agent-relay 需升级到 0.9.0（没有脚本命令）"
TIMEOUT_SECONDS = 30


class ScriptUnavailable(Exception):
    """agent-relay or its script commands cannot be found."""


@dataclass(frozen=True)
class ScriptResult:
    code: int
    stdout: str
    error: str   # first non-empty stderr line, or why the command could not run


def script_argv(kind: str, agent: str | None = None, identity: str | None = None) -> list[str]:
    """The command line for one script command: agents, outbox, sessions or send."""
    found = deps.find("agent-relay")
    if isinstance(found, deps.NotFound):
        raise ScriptUnavailable(found.reason)
    interface = deps.read_interface(found.root, deps.MAJORS["agent-relay"])
    if interface.state != "ok":
        raise ScriptUnavailable(interface.detail or UPGRADE_HINT)
    template = (interface.data.get("script") or {}).get(kind)
    if not isinstance(template, list) or not template or not all(isinstance(a, str) for a in template):
        raise ScriptUnavailable(UPGRADE_HINT)
    subs = {"<agent>": agent, "<script identity>": identity}
    argv = [subs[a] if a in subs else a for a in template]
    if None in argv:
        raise ValueError(f"{kind} 需要的参数没给")
    if argv[0] == "~" or argv[0].startswith("~/"):
        argv[0] = str(Path.home()) + argv[0][1:]
    return argv


def run_script(kind: str, agent: str | None = None, identity: str | None = None,
               body: str | None = None) -> ScriptResult:
    """Run one script command; a send's body goes through stdin. Never raises for a failed run."""
    try:
        argv = script_argv(kind, agent=agent, identity=identity)
    except ScriptUnavailable as e:
        return ScriptResult(127, "", str(e))
    try:
        r = subprocess.run(argv, input=body, stdin=None if body is not None else subprocess.DEVNULL,
                           capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as e:
        return ScriptResult(127, "", str(e).splitlines()[0] if str(e) else type(e).__name__)
    error = next((line.strip() for line in r.stderr.splitlines() if line.strip()), "")
    return ScriptResult(r.returncode, r.stdout, error if r.returncode else "")
