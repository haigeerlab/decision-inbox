"""Stop hook: stop a working session once when another session waits on it (see spec/stop-hook.md).

Read-only: it reads the group's state and the host's Stop payload, never writes
or sends anything. Whether it already stopped this turn comes only from the
host's `stop_hook_active`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from decision_inbox import items, store, tickets
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
    """--session wins; otherwise the roster entry whose repo contains cwd (spec 关键决策 2)."""
    if session:
        entry = store.find_session(g, relay_name=session)
        return (entry, None) if entry else (None, f"名册里没有身份 {session}")
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        return None, "认不出本会话：输入里没有 cwd"
    found = [e for e in store.roster(g) if e.get("repo") and _inside(cwd, e["repo"])]
    if len(found) > 1:
        return None, "认不出本会话：工作目录同时属于 " + "、".join(e["shortName"] for e in found)
    if not found:
        return None, f"认不出本会话：{cwd} 不在名册登记的任何仓库里"
    return found[0], None


def decide(g: store.Group, payload: dict, session: str | None = None, now: str | None = None) -> Decision:
    now = now or store.now()
    if payload.get("stop_hook_active"):
        return _pass("本轮已经拦过一次")
    entry, problem = _who(g, payload, session)
    if entry is None:
        return _pass(problem)
    me, short = entry["relayName"], entry["shortName"]
    open_ = tickets.open_tickets(g, now)
    if any(t.waiter == me for t in open_):
        return _pass("本会话开着等待单，已报阻塞")
    if any(it["sender"] == me and it["fullyStopped"] for it in items.pending(g)):
        return _pass("本会话有完全停住的待答事项，已报阻塞")
    waiting = sorted((t for t in open_ if t.target == short), key=lambda t: t.no)
    if not waiting:
        return _pass("没有会话在等本会话")
    rows = [f"- #{t.no} {(store.find_session(g, relay_name=t.waiter) or {}).get('shortName', t.waiter)} 在等你："
            f"{''.join(x.strip() for x in t.what.splitlines())}（已等 {waited(t.minutes)}）" for t in waiting]
    reason = "\n".join(["【decision-inbox】收工前请先处理：有会话在等你。", *rows,
                        "已经交付：发消息告诉对方，请它发【已恢复】，结束行写这张单的编号。",
                        "还没做完：继续做；做不下去就抛【等待其他会话】或【等待用户】，说明卡在哪。"])
    return Decision(True, reason, None)
