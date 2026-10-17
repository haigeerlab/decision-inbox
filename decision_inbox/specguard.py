"""Read-only access to spec-guard's map_view.py (see spec/spec-guard-reader.md).

The command comes from spec-guard's interface.json when it has one (0.66.0+,
spec/doctor-and-observer.md decision 2); older installs fall back to hooks/map_view.py.

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

from . import deps

PLUGIN = "spec-guard"
INTERFACE_MAJOR = 1
SCHEMA_VERSION = 1
PROJECT_PLACEHOLDER = "<project-root>"


@dataclass(frozen=True)
class Located:
    path: str
    version: str | None
    interface: deps.Interface = deps.Interface("absent")
    argv: tuple[str, ...] = ()        # map-view command with the project left as PROJECT_PLACEHOLDER


@dataclass(frozen=True)
class Missing:
    reason: str


@dataclass(frozen=True)
class Incompatible:
    reason: str
    version: str | None


def _from_interface(root: Path, iface: deps.Interface) -> tuple[str, tuple[str, ...]] | Incompatible | None:
    """Script path and argv from interface.json's mapView; None when the file gives no usable command."""
    view = iface.data.get("mapView")
    if not isinstance(view, dict):
        return None
    if view.get("schemaVersion") != SCHEMA_VERSION:
        return Incompatible(f"spec-guard 的 map-view 是 schemaVersion {view.get('schemaVersion')}，本插件只认 1",
                            iface.version)
    command = view.get("command")
    if not isinstance(command, list) or not all(isinstance(c, str) for c in command):
        return None
    argv, script = [], None
    for part in command:
        if part == "python3":
            argv.append(sys.executable)
        elif script is None and part.endswith(".py"):
            script = str(root / part)
            argv.append(script)
        else:
            argv.append(part)
    if script is None or not Path(script).is_file():
        return None
    return script, tuple(argv)


def locate(project: str) -> Located | Missing | Incompatible:
    """Find spec-guard's map-view: from interface.json when it is there, else the known script path."""
    found = deps.find(PLUGIN, project)
    if isinstance(found, deps.NotFound):
        return Missing(found.reason)
    root = Path(found.root)
    iface = deps.read_interface(found.root, INTERFACE_MAJOR)
    if iface.state == "incompatible":
        return Incompatible(deps.sourced(f"spec-guard 接口版本不兼容（{iface.version}），本插件只认 1.x", PLUGIN),
                            iface.version)
    if iface.state == "ok":
        picked = _from_interface(root, iface)
        if isinstance(picked, Incompatible):
            return picked
        if picked is not None:
            return Located(picked[0], found.version, iface, picked[1])
    script = root / "hooks" / "map_view.py"
    if not script.is_file():
        return Missing(f"spec-guard 的安装目录里没有 map_view.py：{script}")
    return Located(str(script), found.version, iface)




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
    external_review: str = "none"   # none | recorded | declined (spec-guard 0.66.0+)


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
        external_review=m.get("externalReview", "none"),
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
    if isinstance(found, Incompatible):
        return ReadResult("incompatible", found.reason)
    argv = ([project if a == PROJECT_PLACEHOLDER else a for a in found.argv] if found.argv
            else [sys.executable, "-B", found.path, "--project", project, "--json"])
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
