"""A stuck line is asked to raise the question itself (see spec/stall-and-patrol.md, R14, user chose B).

The hub never decides for it: patrol wakes the line with an ask, and when no 【等待用户】 follows
within ANSWER_WAIT the main view lists the three options so the user can act in that session.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from decision_inbox import items, loops, protocol, reviews, store

DEFAULTS = {"stalledHours": 12, "reworkRounds": 3, "repeatAsks": 3, "repeatHours": 24,
            "askAgainHours": 12, "answerWaitMinutes": 30,
            "loopAnswers": 2, "loopHours": 12, "loopQuietHours": 12,  # loop-detection (DI-6)
            "promptMinutes": 5}  # decision-cards DI-9: a session on a permission prompt this long
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
            f"A 挂起当前模块，先开可开工的模块（{ready}）；B 换方案（写明怎么换）；C 继续等，12 小时内不再问。"
            "挂起由你自己用 spec-guard 的 module-suspend 做，不要等决策收件箱代做。")


def module_ask_text(short: str, module: str, where: str, ready: str) -> str:
    """The wake for a module under a module-crew coordinator (crew-stall-facts): module-crew's own way to suspend."""
    return (f"【decision-inbox 巡视】{short}：模块 {module}{where}。请就这个模块抛一项【等待用户】，写清卡在哪，"
            f"给用户三个选项：A 挂起模块 {module}，先开可开工的模块（{ready}）；B 换方案（写明怎么换）；"
            "C 继续等，12 小时内不再问。挂起按 module-crew 的做法做，不要等决策收件箱代做。")


_NODE_NAMES = {code: name for name, code in protocol.REVIEW_NODES.items()}
_SKIP_STAGES = ("merged", "wait-merge")   # done, or waiting for the merge: no new commits are expected


def _module_findings(now: str, crews: dict, cfg: dict, loop_facts=None) -> dict[str, str]:
    """key -> where, from module-crew 0.4.0 facts; modules without them (0.3.x) are never judged.

    loop-detection: a module waiting for the user or in review is judged too; the stall time is work time,
    the waiting spans of its loop facts taken out (wall-clock when the hub has no facts for it).
    """
    found = {}
    facts = {f.key: f for f in loop_facts or ()}
    for coordinator, read in (crews or {}).items():
        if getattr(read, "status", None) != "ok":
            continue
        for m in read.modules:
            if m.stage in _SKIP_STAGES or m.suspended:
                continue
            since = None if m.commits_error else (m.last_commit_at or m.started_at)
            f = facts.get(f"{coordinator}|{m.module}")
            worked = (loops.worked_since(f, since, now) if f is not None else _hours(now, since)) if since else 0
            if since and worked >= cfg["stalledHours"]:
                what = (f"已经 {int(worked)} 小时没有新提交（最后一次提交 {since[5:16].replace('T', ' ')}，"
                        "等你答复的时间不算）" if m.last_commit_at else f"开工 {int(worked)} 小时还没有提交（等你答复的时间不算）")
                found[f"{coordinator}|stalled:{m.module}"] = what
            answered = max((a.at for a in m.answers or ()), key=_instant, default=None)
            for node, ats in m.asks:
                # decision-cards I-13: asks the user already answered do not count again
                recent = [at for at in ats if _hours(now, at) <= cfg["repeatHours"]
                          and (answered is None or _instant(at) > _instant(answered))]
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
        settled = [_settled_at(it) for it in same if _settled_at(it)]
        if settled:  # decision-cards I-13: only what came after the user's latest answer counts
            last = max(settled, key=_instant)
            same = [it for it in same if _instant(it["receivedAt"]) > _instant(last)]
        if len(same) >= cfg["repeatAsks"]:
            topic = same[-1]["decide"].splitlines()[0] if same[-1]["decide"] else "同一件事"
            found.setdefault(f"{sender}|repeat",
                             f"同一件事「{topic}」{cfg['repeatHours']} 小时内报批 {len(same)} 次")
    return found


def _settled_at(it: dict) -> str | None:
    """When the user's answer (or the sender's closing) settled an item; None while it is open or invalidated."""
    if it["status"] in items.PROGRESS:
        return it["statusAt"].get("forwarded")
    if it["status"] == "closed":
        return it["statusAt"].get("forwarded") or it["statusAt"].get("closed")
    return None


def _hushed(key: str, loop_facts) -> bool:
    """loop-detection: a module the hub already shows as going round in circles is not woken (DI-6)."""
    name, _, reason = key.partition("|")
    kind, _, module = reason.partition(":")
    if kind not in ("stalled", "repeat"):
        return False
    return any(f.hit and f.line == name and (not module or f.module == module) for f in loop_facts or ())


def asks(g: store.Group, now: str, lines: dict, maps: dict, state: dict, crews: dict | None = None,
         loop_facts=None) -> list[Ask]:
    """What patrol should ask this round; each key at most once per askAgainHours."""
    cfg = settings(g)
    asked = state.get("stallAsks", {})
    left = store.left_relays(g)
    out = []
    for key, where in {**_findings(g, now, lines, cfg), **_module_findings(now, crews, cfg, loop_facts)}.items():
        name, _, reason = key.partition("|")
        module = reason.partition(":")[2]
        if _hushed(key, loop_facts):
            continue
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
                    f"请去「{entry['shortName']}」处理（{where}）：A 挂起{f'模块 {module}' if module else '当前模块'}，先开可开工的模块；B 换方案；C 继续等")
    return rows
