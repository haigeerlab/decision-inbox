"""Background for an approval item: project, map position, rounds, earlier decisions (spec/approval-display.md).

Read-only; the originals themselves are read by `sources`, at display time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from decision_inbox import items, sources, specguard

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
    from decision_inbox import mapview  # mapview imports view, which imports this module
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


def rounds(g, it: dict) -> tuple[int, str | None]:
    """Which submission this is for its module and node, and the user's last answer when it was not the pick."""
    earlier = sorted((x for x in items.by_status(g, *ANSWERED, "superseded", "withdrawn", "pending")
                      if x["no"] < it["no"] and _same(it, x)), key=lambda x: x["no"])
    last = next((x for x in reversed(earlier) if x.get("answers")), None)
    last_answer = None
    if last is not None and last["answers"][-1]["letter"] != last.get("recommended"):
        last_answer = last["answers"][-1]["original"]
    return len(earlier) + 1, last_answer


def background(g, it: dict, read_map=specguard.read_line) -> Background:
    round_, last_answer = rounds(g, it)
    related = []
    for x in sorted((x for x in items.by_status(g, *ANSWERED) if x["no"] != it["no"] and _same(it, x, node=False)),
                    key=lambda x: x["no"], reverse=True)[:RELATED_LIMIT]:
        answer = x["answers"][-1]
        related.append(f"#{x['no']}（{answer['at'][5:10]}）你答：{answer['original'].splitlines()[0]}")
    repo = next((root for a in it.get("artifacts") or () if (root := sources.repo_root(a["path"]))), None)
    lines, error, title = (_map_lines(read_map(repo), it.get("approvalModule")) if repo
                           else ([], "产物不在 git 仓库里，读不到能力图", None))
    return Background(project=it.get("project") or title or "（没写项目）", repo=repo,
                      module=it.get("approvalModule"), node=it.get("approvalNode"), round=round_,
                      last_answer=last_answer, related=related, map_lines=lines, map_error=error)


FINAL_NODES = ("最终验收", "final")


def modules_of(it: dict) -> list[str | None]:
    """Distinct module prefixes named in 产物／原文, in writing order (approval-display, decision 47)."""
    refs = list(it.get("artifacts") or ()) + [r for rs in (it.get("originals") or {}).values() for r in rs]
    return [m for m in dict.fromkeys(ref.get("module") for ref in refs) if m]


def _section(text: str, title_re) -> list[str] | None:
    """Lines under a heading or a 「标题：」 line, up to the next heading or field; None when absent."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if title_re.match(line.strip()):
            out = []
            for later in lines[i + 1:]:
                bare = later.strip()
                if bare.startswith("#") or (bare and not _NUMBERED_RE.match(bare)):
                    break
                out.append(later)
            return out
    return None


_NUMBERED_RE = re.compile(r"^-?\s*(\d+)\s*[.．、：:]\s*(.*)$")
_CRITERIA_TITLE = re.compile(r"^#+\s*验收标准\s*$")
_EVIDENCE_TITLE = re.compile(r"^验收标准与证据\s*[：:]?\s*$")


def evidence_table(it: dict, submission_text: str | None) -> list[str]:
    """R17: each acceptance criterion of the module's Spec against the evidence the submission gives."""
    module = it.get("approvalModule")
    first = next(iter(it.get("artifacts") or ()), None)
    repo = sources.repo_root(first["path"]) if first else None
    if not (module and first and repo):
        return ["Spec 取不到：不知道模块或仓库，没法对照验收标准"]
    spec = sources.read_artifact(f"{repo}/spec/{module}.md", first["commit"])
    if not spec.ok:
        return [f"Spec 取不到：{spec.reason}"]
    criteria = _section(spec.text, _CRITERIA_TITLE)
    if not criteria:
        return [f"spec/{module}.md 里没有「验收标准」一节"]
    given = {}
    evidence = _section(submission_text or "", _EVIDENCE_TITLE)
    for line in evidence or ():
        if m := _NUMBERED_RE.match(line.strip()):
            given[m.group(1)] = m.group(2).strip()
    out = [] if evidence is not None else ["（交审原文里没有「验收标准与证据」一节）"]
    for line in criteria:
        if not (m := _NUMBERED_RE.match(line.strip())):
            continue
        no, text = m.groups()
        proof = given.get(no)
        if proof is None:
            out.append(f"{no}. {text} —— ⚠ 缺证据")
        elif proof in ("无", "没有"):
            out.append(f"{no}. {text} —— ⚠ 缺证据（写的是「无」）")
        else:
            out.append(f"{no}. {text} —— {proof}")
    return out
