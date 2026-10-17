"""Dependency plugins: where they are installed and what their interface.json says
(see spec/doctor-and-observer.md, decisions 1 and 2).

Only files are read; no dependency command is run from here.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Install:
    root: str
    version: str | None


@dataclass(frozen=True)
class NotFound:
    reason: str


@dataclass(frozen=True)
class Interface:
    state: str                 # ok | absent | unreadable | incompatible
    version: str | None = None
    data: dict = field(default_factory=dict)
    detail: str = ""


def records_file() -> Path:
    override = os.environ.get("DECISION_INBOX_PLUGINS_FILE")
    return Path(override) if override else Path.home() / ".claude" / "plugins" / "installed_plugins.json"


def find(plugin: str, project: str | None = None) -> Install | NotFound:
    """Install root of `plugin` from Claude's install records; a project-scope install for `project` wins."""
    path = records_file()
    try:
        records = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return NotFound(f"找不到 Claude 的插件安装记录：{path}")
    except (OSError, json.JSONDecodeError) as e:
        return NotFound(f"插件安装记录读不出：{path}（{e}）")
    entries = [{**e, "_market": key.split("@", 1)[1]} for key, value in (records.get("plugins") or {}).items()
               if key.startswith(plugin + "@") for e in (value or []) if isinstance(e, dict)]
    if not entries:
        return NotFound(f"本机没有安装 {plugin}")
    scoped = []
    if project is not None:
        project_path = os.path.realpath(project)
        scoped = [e for e in entries if e.get("projectPath")
                  and os.path.realpath(e["projectPath"]) == project_path]
    users = [e for e in entries if e.get("scope") == "user"]
    chosen = (scoped or users or [None])[0]
    if chosen is None:
        return NotFound(f"{plugin} 只装在别的项目里，这个仓库用不到")
    live = _directory_source(path.parent, chosen["_market"], plugin)
    return live or Install(chosen.get("installPath", ""), chosen.get("version"))


def _directory_source(plugins_dir: Path, market: str, plugin: str) -> Install | None:
    """Claude loads a directory marketplace's plugin from its source, not from the recorded copy."""
    try:
        known = json.loads((plugins_dir / "known_marketplaces.json").read_text(encoding="utf-8"))
        source = known[market]["source"]
        if source.get("source") != "directory":
            return None
        repo = Path(source["path"])
        listed = json.loads((repo / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        rel = next(p["source"] for p in listed["plugins"] if p.get("name") == plugin)
        root = (repo / rel).resolve()
        meta = json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError, TypeError, StopIteration):
        return None
    return Install(str(root), meta.get("version"))


def _major_minor(text) -> tuple[int, int] | None:
    parts = str(text).split(".")
    try:
        return int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
    except ValueError:
        return None


def read_interface(root: str, major: int, rel: str = "interface.json") -> Interface:
    """Read `<root>/<rel>` and accept interface versions >=major.0,<major+1.0."""
    path = Path(root) / rel
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return Interface("absent", detail=f"没有 {path}")
    except (OSError, json.JSONDecodeError) as e:
        return Interface("unreadable", detail=f"{path} 读不懂（{e}）")
    if not isinstance(data, dict) or "interface" not in data:
        return Interface("unreadable", detail=f"{path} 里没有 interface 字段")
    version = str(data["interface"])
    parsed = _major_minor(version)
    if parsed is None:
        return Interface("unreadable", version, data, f"接口版本写法看不懂：{version}")
    if parsed[0] != major:
        return Interface("incompatible", version, data, f"接口版本 {version}，本插件只认 {major}.x")
    return Interface("ok", version, data)


def sourced(text: str, source: str) -> str:
    """Mark where a problem comes from, so it reaches whoever can fix it (doctor-and-observer decision 6)."""
    return f"{text}（来源：{source}）"


# Accepted interface major per dependency (spec/doctor-and-observer.md decision 2).
MAJORS = {"spec-guard": 1, "delegate": 1, "agent-relay": 2}
_DELEGATE_DEFAULTS = {"review": "/delegate:review", "run": "/delegate:run", "doctor": "/delegate:doctor"}
_DELEGATE_COMMAND = re.compile(r"^/delegate:[a-z-]+$")


@dataclass(frozen=True)
class Dependency:
    name: str
    version: str | None          # None: not found
    reason: str = ""             # why not found
    interface: Interface = Interface("absent")


def dependency(name: str, project: str | None = None) -> Dependency:
    found = find(name, project)
    if isinstance(found, NotFound):
        return Dependency(name, None, found.reason)
    return Dependency(name, found.version, interface=read_interface(found.root, MAJORS[name]))


def describe(d: Dependency) -> str:
    """One line for doctor: installed version and whether its interface is usable."""
    if d.version is None:
        return f"{d.name}：{d.reason}"
    head = f"{d.name} {d.version}"
    state = d.interface.state
    if state == "ok":
        return f"{head}：接口 {d.interface.version}，兼容"
    if state == "absent":
        return f"{head}：读不到接口说明（可能早于提供 interface.json 的版本）"
    return f"{head}：{d.interface.detail}"


def delegate_command(d: Dependency, purpose: str) -> str:
    """delegate's command name for `purpose`, from its interface when well-formed, else the default."""
    entry = d.interface.data.get(purpose) if d.interface.state == "ok" else None
    command = entry.get("command") if isinstance(entry, dict) else None
    if isinstance(command, str) and _DELEGATE_COMMAND.match(command):
        return command
    return _DELEGATE_DEFAULTS[purpose]
