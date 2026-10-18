"""Stop hook: stop a working session once when another session waits on it (see spec/stop-hook.md).

Read-only: it reads the group's state and the host's Stop payload, never writes
or sends anything. Whether it already stopped this turn comes only from the
host's `stop_hook_active`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime

from decision_inbox import items, specguard, store, tickets
from decision_inbox.view import waited


@dataclass(frozen=True)
class Decision:
    block: bool
    reason: str | None = None
    note: str | None = None


def _pass(note: str) -> Decision:
    return Decision(False, None, note)


def _inside(path: str, root: str) -> bool:
    path, root = os.path.realpath(path), os.path.realpath(root)
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def _who(g: store.Group, payload: dict, session: str | None) -> tuple[dict | None, str | None]:
    """--session wins; otherwise the roster entry whose repo contains cwd (spec 关键决策 2).

    Entries that left the group take no part either way (r20-fixes, O-who-left).
    """
    left = store.left_relays(g)
    if session:
        entry = store.find_session(g, relay_name=session)
        if entry is None:
            return None, f"名册里没有身份 {session}"
        return (None, f"{session} 已退出协作组") if session in left else (entry, None)
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        return None, "认不出本会话：输入里没有 cwd"
    found = [e for e in store.roster(g)
             if e.get("repo") and e["relayName"] not in left and _inside(cwd, e["repo"])]
    if len(found) > 1:
        return None, "认不出本会话：工作目录同时属于 " + "、".join(e["shortName"] for e in found)
    if not found:
        return None, f"认不出本会话：{cwd} 不在名册登记的任何仓库里"
    return found[0], None


def decide(g: store.Group, payload: dict, session: str | None = None, now: str | None = None,
           read_map=None) -> Decision:
    now = now or store.now()
    if payload.get("stop_hook_active"):
        return _pass("本轮已经拦过一次")
    entry, problem = _who(g, payload, session)
    if entry is None:
        return _pass(problem)
    me, short = entry["relayName"], entry["shortName"]
    open_ = tickets.open_tickets(g, now)
    if any(t.waiter == me for t in open_):
        return _pass("本会话开着等待记录，已报阻塞")
    if any(it["sender"] == me and it["fullyStopped"] for it in items.pending(g)):
        return _pass("本会话有完全停住的待答事项，已报阻塞")
    waiting = sorted((t for t in open_ if t.target == short), key=lambda t: t.no)
    answered = _answered(g, me, now)
    if not waiting and not answered:
        silent = _silent_stop(g, entry, read_map or specguard.read_line)
        if silent is not None:
            return Decision(True, silent, None)
        return _pass("没有会话在等本会话，也没有已答未恢复的事项")
    out = []
    if waiting:
        rows = [f"- W{t.no}（结束行写 #{t.no}）{(store.find_session(g, relay_name=t.waiter) or {}).get('shortName', t.waiter)} 在等你："
                f"{''.join(x.strip() for x in t.what.splitlines())}（已等 {waited(t.minutes)}）" for t in waiting]
        out += ["【decision-inbox】收工前请先处理：有会话在等你。", *rows,
                "已经交付：发消息告诉对方，请它发【已恢复】，结束行写这条等待记录的编号（#数字）。",
                "还没做完：继续做；做不下去就抛【等待其他会话】或【等待用户】，说明卡在哪。"]
    if answered:
        out.append("另外，用户已答复你抛的事项，你还没发【已恢复】：" if waiting
                   else "【decision-inbox】收工前请先处理：用户已答复你抛的事项，你还没发【已恢复】。")
        out += [*answered, "做完了：发【已恢复】，结束行写这个编号。",
                "做不下去：抛【等待其他会话】或【等待用户】，说明卡在哪。",
                # the hook cannot see this session's own sent mail (relay-presence-and-doubt 关键决策 6)
                "已经发过【已恢复】、收件枢纽还没收进：回一句「已发 #邮箱号」即可收工，不用重发。"]
    return Decision(True, "\n".join(out), None)


def _silent_stop(g: store.Group, entry: dict, read_map) -> str | None:
    """A dev line stopping with open todos and nothing reported (wait-honesty-and-briefs B1).

    Only when spec-guard can be read for its repository; anything else stays silent.
    """
    if entry["role"] != "dev" or not entry.get("repo"):
        return None
    if entry.get("crewCoordinator"):
        return None  # module progress belongs to module-crew (crew-coordinator-seam)
    if any(it["sender"] == entry["relayName"] for it in items.pending(g)):
        return None
    read = read_map(entry["repo"])
    line_map = getattr(read, "map", None)
    if getattr(read, "status", None) != "ok" or line_map is None or not line_map.active_module:
        return None
    m = next((m for m in line_map.modules if m.id == line_map.active_module), None)
    if m is None or m.progress_done >= m.progress_total or getattr(m, "status", None) == "suspended":
        return None
    return "\n".join([
        f"【decision-inbox】收工前请先处理：当前模块 {m.id} 还有 {m.progress_total - m.progress_done} 项没勾，"
        "你既没报阻塞也没抛事项。",
        "手上没有已批准、还没做完的下一步：抛一项【等待用户】，说明要用户定什么。",
        "在等别人：抛【等待其他会话】。",
        "还能接着做：继续做，不要停下。"])


ANSWERED = ("forwarded", "picked", "acknowledged")
ORIGINAL_CHARS = 40


def _answered(g: store.Group, me: str, now: str) -> list[str]:
    """Items this session raised that the user answered and it has not ended with 【已恢复】 (H17)."""
    rows = []
    for it in items.by_status(g, *ANSWERED):
        if it["sender"] != me or not it["answers"]:
            continue
        last = it["answers"][-1]
        original = "".join(x.strip() for x in last["original"].splitlines())
        if len(original) > ORIGINAL_CHARS:
            original = original[:ORIGINAL_CHARS] + "…"
        minutes = max(0, int((_instant(now) - _instant(last["at"])).total_seconds() // 60))
        rows.append(f"- #{it['no']} 用户已答复：「{original}」（{waited(minutes)}前）")
    return rows


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
