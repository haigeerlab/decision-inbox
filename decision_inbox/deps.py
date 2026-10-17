"""Dependency plugins: where they are installed and what their interface.json says
(see spec/doctor-and-observer.md, decisions 1 and 2).

Only files are read; no dependency command is run from here.
"""

from __future__ import annotations

import json
import os
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
    entries = [e for key, value in (records.get("plugins") or {}).items()
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
    return Install(chosen.get("installPath", ""), chosen.get("version"))


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
