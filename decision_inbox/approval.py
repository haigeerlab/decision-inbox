"""Background for an approval item: project, map position, rounds, earlier decisions (spec/approval-display.md).

Read-only; the originals themselves are read by `sources`, at display time.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from decision_inbox import items, mapview, sources, specguard

RELATED_LIMIT = 5
ANSWERED = ("forwarded", "picked", "acknowledged", "closed")


def is_approval(it: dict) -> bool:
    """An item that names something to read verbatim (session-protocol v2.1)."""
    return bool(it.get("artifacts") or any((it.get("originals") or {}).values()))


@dataclass
class Background:
    project: str
    repo: str | None
    module: str | None
    node: str | None
    round: int
    last_answer: str | None
    related: list[str] = field(default_factory=list)
    map_lines: list[str] = field(default_factory=list)
    map_error: str | None = None


def _same(it: dict, other: dict, node: bool = True) -> bool:
    return (other["sender"] == it["sender"] and other.get("approvalModule") == it.get("approvalModule")
            and (not node or other.get("approvalNode") == it.get("approvalNode")))


def _map_lines(read, module: str | None) -> tuple[list[str], str | None, str | None]:
    if read.status != "ok" or read.map is None:
        return [], read.reason or read.status, None
    modules = sorted(read.map.modules, key=lambda m: m.position)
    mine = next((m for m in modules if m.id == module), None)
    deps = set(mine.depends_on) if mine else set()
    lines = []
    for m in modules:
        mark = " ← 本项" if m is mine else "（依赖）" if m.id in deps else ""
        lines.append(f"{m.position}. {m.id} {mapview.status_cell(m)}{mark}")
    if module and mine is None:
        lines.append(f"（能力图里没有模块 {module}）")
    return lines, None, read.map.title


def background(g, it: dict, read_map=specguard.read_line) -> Background:
    earlier = sorted((x for x in items.by_status(g, *ANSWERED, "superseded", "withdrawn", "pending")
                      if x["no"] < it["no"] and _same(it, x)), key=lambda x: x["no"])
    last = next((x for x in reversed(earlier) if x.get("answers")), None)
    last_answer = None
    if last is not None and last["answers"][-1]["letter"] != last.get("recommended"):
        last_answer = last["answers"][-1]["original"]
    related = []
    for x in sorted((x for x in items.by_status(g, *ANSWERED) if x["no"] != it["no"] and _same(it, x, node=False)),
                    key=lambda x: x["no"], reverse=True)[:RELATED_LIMIT]:
        answer = x["answers"][-1]
        related.append(f"#{x['no']}（{answer['at'][5:10]}）你答：{answer['original'].splitlines()[0]}")
    repo = next((root for a in it.get("artifacts") or () if (root := sources.repo_root(a["path"]))), None)
    lines, error, title = (_map_lines(read_map(repo), it.get("approvalModule")) if repo
                           else ([], "产物不在 git 仓库里，读不到能力图", None))
    return Background(project=it.get("project") or title or "（没写项目）", repo=repo,
                      module=it.get("approvalModule"), node=it.get("approvalNode"), round=len(earlier) + 1,
                      last_answer=last_answer, related=related, map_lines=lines, map_error=error)
