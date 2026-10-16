"""Read-only access to spec-guard's map_view.py (see spec/spec-guard-reader.md).

The capability map and todo files are never parsed here; spec-guard owns that
logic and this module only runs its script and reads its JSON.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

PLUGIN_PREFIX = "spec-guard@"


@dataclass(frozen=True)
class Located:
    path: str
    version: str | None


@dataclass(frozen=True)
class Missing:
    reason: str


def _records_file() -> Path:
    override = os.environ.get("DECISION_INBOX_PLUGINS_FILE")
    return Path(override) if override else Path.home() / ".claude" / "plugins" / "installed_plugins.json"


def locate(project: str) -> Located | Missing:
    """Find map_view.py from Claude's install records; a project-scope install for `project` wins."""
    path = _records_file()
    try:
        records = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return Missing(f"找不到 Claude 的插件安装记录：{path}")
    except (OSError, json.JSONDecodeError) as e:
        return Missing(f"插件安装记录读不出：{path}（{e}）")
    entries = [e for key, value in (records.get("plugins") or {}).items()
               if key.startswith(PLUGIN_PREFIX) for e in (value or []) if isinstance(e, dict)]
    if not entries:
        return Missing("本机没有安装 spec-guard")
    project_path = os.path.realpath(project)
    scoped = [e for e in entries if e.get("projectPath")
              and os.path.realpath(e["projectPath"]) == project_path]
    users = [e for e in entries if e.get("scope") == "user"]
    chosen = (scoped or users or [None])[0]
    if chosen is None:
        return Missing("spec-guard 只装在别的项目里，这个仓库用不到")
    script = Path(chosen.get("installPath", "")) / "hooks" / "map_view.py"
    if not script.is_file():
        return Missing(f"spec-guard 的安装目录里没有 map_view.py：{script}")
    return Located(str(script), chosen.get("version"))
