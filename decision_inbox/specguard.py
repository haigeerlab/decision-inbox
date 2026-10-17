"""Read-only access to spec-guard's map_view.py (see spec/spec-guard-reader.md).

The capability map and todo files are never parsed here; spec-guard owns that
logic and this module only runs its script and reads its JSON.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
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


SCHEMA_VERSION = 1


class BadOutput(ValueError):
    """map_view.py printed something that is not the agreed JSON."""


class SchemaMismatch(ValueError):
    """schemaVersion is not 1: the contract changed, check it before reading."""


@dataclass(frozen=True)
class Bottleneck:
    id: str
    suspended_reason: str | None
    blocks: tuple[str, ...]


@dataclass(frozen=True)
class AwaitingReview:
    id: str
    kind: str
    review: str


@dataclass(frozen=True)
class ModuleFact:
    id: str
    position: int
    responsibility: str
    depends_on: tuple[str, ...]
    status: str
    step: str | None
    progress_done: int
    progress_total: int
    suspended_reason: str | None
    blocked_on: tuple[str, ...]
    missing_deps: tuple[str, ...]
    blocks: tuple[str, ...]
    review_spec: str
    review_plan: str
    last_tick_at: str | None
    first_tick_at: str | None
    tick_commits: int | None
    suspended_at: str | None


@dataclass(frozen=True)
class LineMap:
    project_root: str
    title: str | None
    generated_at: str
    generator_version: str | None
    stage: str
    active_module: str | None
    next_gate: str | None
    history: str
    totals: dict
    head_sha: str | None
    head_branch: str | None
    unmerged_count: int | None
    unmerged_base: str | None
    unpushed_count: int | None
    unpushed_upstream: str | None
    bottlenecks: tuple[Bottleneck, ...]
    awaiting_review: tuple[AwaitingReview, ...]
    modules: tuple[ModuleFact, ...]


def _module(m: dict) -> ModuleFact:
    progress = m.get("progress") or {}
    blocks = m.get("blocks") or {}
    review = m.get("review") or {}
    return ModuleFact(
        id=m["id"], position=int(m["position"]), responsibility=m.get("responsibility", ""),
        depends_on=tuple(m.get("dependsOn") or ()), status=m["status"], step=m.get("step"),
        progress_done=int(progress.get("done", 0)), progress_total=int(progress.get("total", 0)),
        suspended_reason=m.get("suspendedReason"), blocked_on=tuple(m.get("blockedOn") or ()),
        missing_deps=tuple(m.get("missingDeps") or ()), blocks=tuple(blocks.get("ids") or ()),
        review_spec=review.get("spec", "none"), review_plan=review.get("plan", "none"),
        last_tick_at=m.get("lastTickAt"), first_tick_at=m.get("firstTickAt"),
        tick_commits=m.get("tickCommits"), suspended_at=m.get("suspendedAt"),
    )


def parse_map(text: str) -> LineMap:
    """map_view.py --json stdout -> LineMap; unknown fields are ignored (contract: only additions in v1)."""
    try:
        d = json.loads(text)
    except (TypeError, json.JSONDecodeError) as e:
        raise BadOutput(f"map_view.py 的输出不是合法 JSON：{e}") from None
    if not isinstance(d, dict):
        raise BadOutput("map_view.py 的输出顶层不是对象")
    if d.get("schemaVersion") != SCHEMA_VERSION:
        raise SchemaMismatch(f"map_view.py 的 schemaVersion 是 {d.get('schemaVersion')!r}，本插件只认 1")
    try:
        head = d.get("head") or {}
        unmerged = head.get("unmerged") or {}
        unpushed = head.get("unpushed") or {}
        history = d.get("history", "unavailable")
        modules = sorted((_module(m) for m in d["modules"]), key=lambda m: m.position)
        if history == "unavailable":
            modules = [m if m.tick_commits is None else
                       ModuleFact(**{**m.__dict__, "tick_commits": None}) for m in modules]
        return LineMap(
            project_root=(d.get("project") or {}).get("root", ""), title=(d.get("project") or {}).get("title"),
            generated_at=d.get("generatedAt", ""), generator_version=(d.get("generator") or {}).get("version"),
            stage=d.get("stage", ""), active_module=d.get("activeModule"), next_gate=d.get("nextGate"),
            history=history, totals=dict(d.get("totals") or {}),
            head_sha=head.get("sha"), head_branch=head.get("branch"),
            unmerged_count=unmerged.get("count"), unmerged_base=unmerged.get("base"),
            unpushed_count=unpushed.get("count"), unpushed_upstream=unpushed.get("upstream"),
            bottlenecks=tuple(Bottleneck(b["id"], b.get("suspendedReason"), tuple(b.get("blocks") or ()))
                              for b in d.get("bottlenecks") or ()),
            awaiting_review=tuple(AwaitingReview(a["id"], a["kind"], a["review"])
                                  for a in d.get("awaitingReview") or ()),
            modules=tuple(modules),
        )
    except (KeyError, TypeError, ValueError) as e:
        raise BadOutput(f"map_view.py 的输出缺少约定字段：{e}") from None


DEFAULT_TIMEOUT = 15


@dataclass(frozen=True)
class ReadResult:
    status: str
    reason: str | None = None
    exit_code: int | None = None
    map: LineMap | None = None


def read_line(project: str, timeout: float = DEFAULT_TIMEOUT) -> ReadResult:
    """Run spec-guard's map_view.py for one line's repository and classify the outcome honestly."""
    if not os.path.isabs(project) or not os.path.isdir(project):
        return ReadResult("bad-args", f"仓库路径必须是存在的绝对路径目录：{project}")
    found = locate(project)
    if isinstance(found, Missing):
        return ReadResult("not-installed", found.reason)
    argv = [sys.executable, "-B", found.path, "--project", project, "--json"]
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return ReadResult("timeout", f"map_view.py 超过 {timeout} 秒没有结束")
    code, out, err = done.returncode, done.stdout, done.stderr.strip()
    if code == 2:
        return ReadResult("bad-args", err or "map_view.py 报参数或路径错误", code)
    if code == 3:
        return ReadResult("no-map", "无能力图", code)
    if code == 4:
        try:
            detail = json.loads(out).get("detail")
        except (json.JSONDecodeError, AttributeError):
            detail = None
        return ReadResult("unreadable", f"能力图或模块文件读不出：{detail or err or '未给原因'}", code)
    if code != 0:
        return ReadResult("bad-output", f"map_view.py 退出码 {code}：{err[:200]}", code)
    try:
        return ReadResult("ok", None, code, parse_map(out))
    except SchemaMismatch as e:
        return ReadResult("schema-mismatch", str(e), code)
    except BadOutput as e:
        return ReadResult("bad-output", str(e), code)
