"""Stop hook: stop a working session once when another session waits on it (see spec/stop-hook.md).

Read-only: it reads the group's state and the host's Stop payload, never writes
or sends anything. Whether it already stopped this turn comes only from the
host's `stop_hook_active`.
"""

from __future__ import annotations

import json
import os
import re
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
            return None, f"名册里没有邮箱名 {session}"
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
        return _pass("本会话有完全停住的待决事项，已报阻塞")
    waiting = sorted((t for t in open_ if t.target == short), key=lambda t: t.no)
    answered = _answered(g, me, now, session_start(payload))
    if not waiting and not answered:
        silent = _silent_stop(g, entry, read_map or specguard.read_line)
        if silent is not None:
            return Decision(True, silent, None)
        return _pass("没有会话在等本会话，也没有已答复、还没结项的待决事项")
    out = []
    if waiting:
        rows = [f"- W{t.no}（结束行写 #{t.no}）{(store.find_session(g, relay_name=t.waiter) or {}).get('shortName', t.waiter)} 在等你："
                f"{''.join(x.strip() for x in t.what.splitlines())}（已等 {waited(t.minutes)}）" for t in waiting]
        out += ["【decision-inbox】收工前请先处理：有会话在等你。", *rows,
                "已经交付：发消息告诉对方，请它发【已恢复】，结束行写这条等待记录的编号（#数字）。",
                "还没做完：继续做；做不下去就抛【等待其他会话】或【等待用户】，说明卡在哪。"]
    if answered:
        out.append("另外，用户已答复你抛的待决事项，你还没发【已恢复】（表示已结项）：" if waiting
                   else "【decision-inbox】收工前请先处理：用户已答复你抛的待决事项，你还没发【已恢复】（表示已结项）。")
        out += [*answered, "做完了：发【已恢复】，结束行写这个编号。",
                "做不下去：抛【等待其他会话】或【等待用户】，说明卡在哪。",
                # the hook cannot see this session's own sent mail (relay-presence-and-doubt 关键决策 6)
                "已经发过【已恢复】、决策收件箱还没收进：回一句「已发 #邮箱号」即可收工，不用重发。"]
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
        "你既没报阻塞也没抛待决事项。",
        "手上没有已批准、还没做完的下一步：抛一项【等待用户】，说明要用户定什么。",
        "在等别人：抛【等待其他会话】。",
        "还能接着做：继续做，不要停下。"])


ANSWERED = ("forwarded", "picked", "acknowledged")
ORIGINAL_CHARS = 40


def session_start(payload: dict) -> str | None:
    """stage-c2-fixes I-18: when this session began, from the first timestamped record of its transcript."""
    path = payload.get("transcript_path")
    if not isinstance(path, str) or not path:
        return None
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    at = json.loads(line).get("timestamp")
                except (ValueError, AttributeError):
                    continue
                if isinstance(at, str) and at:
                    _instant(at)
                    return at
    except (OSError, ValueError):
        return None
    return None


def _local(at: str) -> str:
    return _instant(at).astimezone().strftime("%m-%d %H:%M")


def _answered(g: store.Group, me: str, now: str, started: str | None = None) -> list[str]:
    """Items this session raised that the user answered and it has not ended with 【已恢复】 (H17).

    stage-c2-fixes I-18: one raised before this session began came with the mailbox name; say so.
    """
    rows = []
    for it in items.by_status(g, *ANSWERED):
        if it["sender"] != me or not it["answers"] or not items.delivered(it):
            continue  # decision-cards DI-6: an answer never sent is not waiting for 【已恢复】
        last = it["answers"][-1]
        original = "".join(x.strip() for x in last["original"].splitlines())
        if len(original) > ORIGINAL_CHARS:
            original = original[:ORIGINAL_CHARS] + "…"
        if started and _instant(it["receivedAt"]) < _instant(started):
            no = it["no"]
            rows.append(f"- #{no} 是这个邮箱名之前的会话在 {_local(it['receivedAt'])} 抛出的，用户 {_local(last['at'])} "
                        f"答复：「{original}」。你接手了这个邮箱名：已经处理完就发【已恢复】结项（结束行写 #{no}）；"
                        f"不归你处理就发【撤回】，写「事项：#{no}」")
            continue
        minutes = max(0, int((_instant(now) - _instant(last["at"])).total_seconds() // 60))
        rows.append(f"- #{it['no']} 用户已答复：「{original}」（{waited(minutes)}前）")
    return rows


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


# decision-cards DI-4 (user chose A): the hub session's own turn, checked against what the command printed.
_HUB_COMMAND_RE = re.compile(r"decision[-_]inbox\S*\s+(?:view|inbox\s+reply)\b")
_PERSISTED_RE = re.compile(r"Full output saved to: (\S+)")
_BLOCK_RE = re.compile(r"```[^\n]*\n(.*?)\n```", re.S)
_HEAD_RE = re.compile(r"^\*\*(?:#\d+ · |去 ).*$", re.M)  # item cards, and DI-9 prompt reminders


class _Unreadable(ValueError):
    pass


def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def _turn(path: str) -> tuple[str | None, str]:
    """(last hub command output of this turn or None, what the assistant wrote after it)."""
    rows = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
    except (OSError, ValueError) as e:
        raise _Unreadable(str(e)) from e
    start = 0
    for i, row in enumerate(rows):
        content = (row.get("message") or {}).get("content") if isinstance(row, dict) else None
        if row.get("type") == "user" and (isinstance(content, str) or
                                          (isinstance(content, list) and any(
                                              isinstance(b, dict) and b.get("type") == "text" for b in content))):
            start = i
    commands, output, after = {}, None, []
    for row in rows[start:]:
        content = (row.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for b in content:
            if not isinstance(b, dict):
                continue
            if row.get("type") == "assistant" and b.get("type") == "tool_use":
                command = (b.get("input") or {}).get("command")
                if isinstance(command, str) and _HUB_COMMAND_RE.search(command):
                    commands[b.get("id")] = command
            elif row.get("type") == "user" and b.get("type") == "tool_result" and b.get("tool_use_id") in commands:
                output, after = _text_of(b.get("content")), []
            elif row.get("type") == "assistant" and b.get("type") == "text":
                after.append(b.get("text") or "")
    if output is not None and (saved := _PERSISTED_RE.search(output)):
        try:
            output = open(saved.group(1), encoding="utf-8").read()
        except OSError as e:
            raise _Unreadable(f"读不到 {saved.group(1)}") from e
    if output is not None:
        try:
            doc = json.loads(output)
            output = doc["show"] if isinstance(doc, dict) and isinstance(doc.get("show"), str) else output
        except ValueError:
            pass
    return output, "\n".join(after)


def _norm(text: str) -> str:
    return " ".join(text.split())


def hub_turn_check(payload: dict) -> Decision:
    """Block once when the hub's reply dropped a card head or a copy block, or added code blocks with nothing pending."""
    if payload.get("stop_hook_active"):
        return _pass("本轮已经拦过一次")
    path = payload.get("transcript_path")
    if not isinstance(path, str) or not path:
        return _pass("没有会话记录")
    try:
        output, said = _turn(path)
    except _Unreadable as e:
        return _pass(f"会话记录读不懂，收件箱停止检查放行：{e}")
    if output is None:
        return _pass("本轮没有出主视图")
    blocks = [b.strip() for b in _BLOCK_RE.findall(output)]
    heads = _HEAD_RE.findall(output)
    written = {_norm(b) for b in _BLOCK_RE.findall(said)}
    flat = _norm(said)
    problems = []
    missing_heads = [h for h in heads if _norm(h) not in flat]
    if missing_heads:
        problems.append("缺了这些卡片抬头：" + "；".join(missing_heads))
    missing_blocks = [b for b in blocks if _norm(b) not in written]
    if missing_blocks:
        problems.append("缺了这些复制块（要放在代码块里，一字不差）：" + "；".join(missing_blocks))
    if not blocks and "```" in said:
        problems.append("没有待答的待决事项，回复里却出现了代码块（代码块只给要你回答的待决事项用）")
    if not problems:
        return _pass("收件箱这一轮的卡片和复制块都在")
    return Decision(True, "\n".join([
        "【decision-inbox】这一轮的回复没有照命令输出显示决策卡片：", *(f"- {p}" for p in problems),
        "请把命令输出的主视图逐字贴给用户（按 Markdown 直接显示，不要套进代码块），不要改写成摘要。"]), None)


def transcript_readable(path: str) -> str | None:
    """None when the hub stop check understands a session record, else why not (doctor)."""
    try:
        _turn(path)
    except _Unreadable as e:
        return str(e)
    return None
