"""A stuck line is asked to raise the question itself (see spec/stall-and-patrol.md, R14, user chose B).

The hub never decides for it: patrol wakes the line with an ask, and when no 【等待用户】 follows
within ANSWER_WAIT the main view lists the three options so the user can act in that session.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from decision_inbox import items, protocol, reviews, store

DEFAULTS = {"stalledHours": 12, "reworkRounds": 3, "repeatAsks": 3, "repeatHours": 24,
            "askAgainHours": 12, "answerWaitMinutes": 30}
DESKTOP_LINK = "claude://claude.ai/epitaxy/{session}"


@dataclass(frozen=True)
class Ask:
    key: str          # "<relay name>|<stalled|rework|repeat>"
    kind: str         # wake (Claude, desktop message) | owner-alert (agent-relay mail to the line itself)
    target: str
    text: str


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _hours(now: str, then: str) -> float:
    return (_instant(now) - _instant(then)).total_seconds() / 3600


def settings(g: store.Group) -> dict:
    """Thresholds, overridable per group under "stall" in group.json (user: defaults are fine)."""
    try:
        own = json.loads((g.path / "group.json").read_text(encoding="utf-8")).get("stall") or {}
    except (OSError, ValueError):
        own = {}
    return {**DEFAULTS, **{k: v for k, v in own.items() if k in DEFAULTS and isinstance(v, (int, float))}}


def _ready(maps: dict, name: str) -> str:
    read = maps.get(name)
    line_map = getattr(read, "map", None) if getattr(read, "status", None) == "ok" else None
    ready = [m.id for m in line_map.modules if m.status == "ready"] if line_map else []
    return "、".join(ready) if ready else "能力图里暂时没有可开工的模块"


def ask_text(short: str, where: str, ready: str) -> str:
    return (f"【decision-inbox 巡视】{short}：{where}。请抛一项【等待用户】，写清卡在哪，给用户三个选项："
            f"A 挂起当前模块，先开可开工的模块（{ready}）；B 换做法（写明怎么换）；C 继续等，12 小时内不再问。"
            "挂起由你自己用 spec-guard 的 module-suspend 做，不要等决策收件箱代做。")


def module_ask_text(short: str, module: str, where: str, ready: str) -> str:
    """The wake for a module under a module-crew coordinator (crew-stall-facts): module-crew's own way to suspend."""
    return (f"【decision-inbox 巡视】{short}：模块 {module}{where}。请就这个模块抛一项【等待用户】，写清卡在哪，"
            f"给用户三个选项：A 挂起模块 {module}，先开可开工的模块（{ready}）；B 换做法（写明怎么换）；"
            "C 继续等，12 小时内不再问。挂起按 module-crew 的做法做，不要等决策收件箱代做。")


_NODE_NAMES = {code: name for name, code in protocol.REVIEW_NODES.items()}
_SKIP_STAGES = ("merged", "wait-merge")   # done, or waiting for the merge: no new commits are expected


def _module_findings(now: str, crews: dict, cfg: dict) -> dict[str, str]:
    """key -> where, from module-crew 0.4.0 facts; modules without them (0.3.x) are never judged."""
    found = {}
    for coordinator, read in (crews or {}).items():
        if getattr(read, "status", None) != "ok":
            continue
        for m in read.modules:
            if m.stage in _SKIP_STAGES or m.suspended or m.waiting_user or m.review:
                continue
            since = None if m.commits_error else (m.last_commit_at or m.started_at)
            if since and _hours(now, since) >= cfg["stalledHours"]:
                what = (f"已经 {int(_hours(now, since))} 小时没有新提交（最后一次提交 {since[5:16].replace('T', ' ')}）"
                        if m.last_commit_at else f"开工 {int(_hours(now, since))} 小时还没有提交")
                found[f"{coordinator}|stalled:{m.module}"] = what
            for node, ats in m.asks:
                recent = [at for at in ats if _hours(now, at) <= cfg["repeatHours"]]
                if len(recent) >= cfg["repeatAsks"]:
                    found.setdefault(f"{coordinator}|repeat:{m.module}",
                                     f"的{_NODE_NAMES.get(node, node)} {cfg['repeatHours']} 小时内报批 {len(recent)} 次")
    return found


def _findings(g: store.Group, now: str, lines: dict, cfg: dict) -> dict[str, str]:
    """key -> where it is stuck."""
    found = {}
    for name, state in lines.items():
        if state.word == "stalled" and state.since and _hours(now, state.since) >= cfg["stalledHours"]:
            found[f"{name}|stalled"] = f"已经 {int(_hours(now, state.since))} 小时没有进展（{state.text}）"
    for ref, submitter, node, rounds in reviews.round_stats(g).open:
        if rounds >= cfg["reworkRounds"]:
            found.setdefault(f"{submitter}|rework", f"审查 {ref}（{node}）来回 {rounds} 轮还没通过")
    recent: dict[tuple, list] = {}
    for it in items.by_status(g, *items.FINAL, "pending", *items.PROGRESS):
        if _hours(now, it["receivedAt"]) > cfg["repeatHours"]:
            continue
        topic = (it.get("approvalModule"), it.get("approvalNode")) if it.get("approvalModule") \
            else it["decide"].splitlines()[0] if it["decide"] else ""
        recent.setdefault((it["sender"], str(topic)), []).append(it)
    for (sender, _), same in recent.items():
        if len(same) >= cfg["repeatAsks"]:
            topic = same[-1]["decide"].splitlines()[0] if same[-1]["decide"] else "同一件事"
            found.setdefault(f"{sender}|repeat",
                             f"同一件事「{topic}」{cfg['repeatHours']} 小时内报批 {len(same)} 次")
    return found


def asks(g: store.Group, now: str, lines: dict, maps: dict, state: dict, crews: dict | None = None) -> list[Ask]:
    """What patrol should ask this round; each key at most once per askAgainHours."""
    cfg = settings(g)
    asked = state.get("stallAsks", {})
    left = store.left_relays(g)
    out = []
    for key, where in {**_findings(g, now, lines, cfg), **_module_findings(now, crews, cfg)}.items():
        name, _, reason = key.partition("|")
        module = reason.partition(":")[2]
        entry = store.find_session(g, relay_name=name)
        if entry is None or name in left or entry["role"] == "hub":
            continue
        if key in asked and _hours(now, asked[key]) < cfg["askAgainHours"]:
            continue
        text = (module_ask_text(entry["shortName"], module, where, _ready(maps, name)) if module
                else ask_text(entry["shortName"], where, _ready(maps, name)))
        if entry["host"] == "claude-desktop" and entry.get("desktopSession"):
            out.append(Ask(key, "wake", entry["desktopSession"], text))
        else:
            out.append(Ask(key, "owner-alert", name, text))
    return out


def overdue_rows(g: store.Group, now: str, state: dict) -> list[str]:
    """Main view: asked, but no new 【等待用户】 from that line within answerWaitMinutes."""
    cfg = settings(g)
    rows = []
    for key, at in sorted(state.get("stallAsks", {}).items()):
        name, _, reason = key.partition("|")
        module = reason.partition(":")[2]
        entry = store.find_session(g, relay_name=name)
        if entry is None or _hours(now, at) * 60 < cfg["answerWaitMinutes"]:
            continue
        if _hours(now, at) >= cfg["askAgainHours"]:
            continue
        raised = any(it["sender"] == name and _instant(it["receivedAt"]) >= _instant(at)
                     for it in items.by_status(g, *items.FINAL, "pending", *items.PROGRESS))
        if raised:
            continue
        where = (f"打开 {DESKTOP_LINK.format(session=entry['desktopSession'])}" if entry.get("desktopSession")
                 else "去 Codex 打开它的任务")
        who = f"{entry['shortName']}（模块 {module}）" if module else entry["shortName"]
        rows.append(f"⚠ 停滞：{who} 被问了 {int(_hours(now, at) * 60)} 分钟还没抛待决事项。"
                    f"请去「{entry['shortName']}」处理（{where}）：A 挂起{f'模块 {module}' if module else '当前模块'}，先开可开工的模块；B 换做法；C 继续等")
    return rows
