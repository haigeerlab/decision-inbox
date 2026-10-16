"""Read-only queries /lines, /flow and /item (see spec/query-commands.md).

Facts come from line-health, decision-queue, wait-tickets and relay-reader;
nothing here writes state, sends messages or wakes anyone.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from decision_inbox import health, items, store, tickets
from decision_inbox.view import ago, copy_line


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _clock(value: str) -> str:
    return _instant(value).astimezone().strftime("%H:%M")


def _dev_lines(g: store.Group) -> list[dict]:
    return [e for e in store.roster(g) if e["role"] == "dev"]


@dataclass(frozen=True)
class _Edge:
    waiter: str      # relay name
    target: str      # relay name
    ticket: int
    sent_at: str


def _wait_graph(g: store.Group, now: str) -> list[_Edge]:
    """Open tickets between sessions on the roster; waits on the user stay out of the graph."""
    raw = store.read_state(g, tickets.DOMAIN).get("tickets", {})
    edges = []
    for t in tickets.open_tickets(g, now):
        entry = store.find_session(g, short_name=t.target)
        if entry is not None and store.find_session(g, relay_name=t.waiter) is not None:
            edges.append(_Edge(t.waiter, entry["relayName"], t.no, raw[str(t.no)]["sentAt"]))
    return edges


def _module_text(read) -> str:
    if read is None:
        return "当前模块：未读取"
    if read.status != "ok":
        return read.reason or read.status
    line_map = read.map
    current = next((m for m in line_map.modules if m.id == line_map.active_module), None)
    if current is not None:
        return f"当前模块 {current.id}（{current.progress_done}/{current.progress_total}）"
    return "全部模块已完成" if line_map.stage == "DONE" else "当前模块：无"


def _last_output(name: str, read, assessment, now: str) -> str:
    """Newest of the snapshot's changedAt and, with complete history, spec-guard's lastTickAt."""
    times = [v["changedAt"] for v in assessment.snapshot.get("sessions", {}).get(name, {}).values()
             if v.get("changedAt")]
    if read is not None and read.status == "ok" and read.map.history == "complete":
        times += [m.last_tick_at for m in read.map.modules if m.last_tick_at]
    if not times:
        return "最后产出：无记录"
    last = max(times, key=_instant)
    return f"最后产出 {_clock(last)}（{ago(now, last)}）"


def _unread(name: str, relay) -> str:
    fact = relay.agents.get(name) if relay is not None else None
    count = fact.waiting_count if fact is not None else None
    return f"未读 {count}" if count is not None else "未读 未知"


def _waiting_for(g: store.Group, name: str, now: str) -> str:
    parts = [f"你（#{it['no']}）" for it in items.pending(g) if it["sender"] == name and it["fullyStopped"]]
    for t in tickets.open_tickets(g, now):
        if t.waiter != name:
            continue
        if t.target in tickets.USER_TARGETS:
            if not parts:
                parts.append("你")
        elif t.target not in parts:
            parts.append(t.target)
    return "、".join(parts) or "—"


def _join(parts: list[str]) -> str:
    """Spec examples drop the space between a full-width ）and the next ·."""
    return " · ".join(parts).replace("） · ", "）· ")


def render_lines(g: store.Group, now: str, assessment, relay=None, maps: dict | None = None) -> str:
    """/lines: one row per development line (role dev), roster order."""
    maps = maps or {}
    rows = []
    for entry in _dev_lines(g):
        name = entry["relayName"]
        state = assessment.lines.get(name)
        read = maps.get(name)
        rows.append(_join([
            entry["shortName"], state.text if state else "无状态",
            _module_text(read), _last_output(name, read, assessment, now),
            _unread(name, relay), f"在等：{_waiting_for(g, name, now)}",
        ]))
    return "\n".join(rows)


def _cycle(edges: list[_Edge], order: list[str]) -> list[str] | None:
    """First wait cycle found by depth-first search, members in roster order."""
    out: dict[str, list[str]] = {}
    for e in edges:
        out.setdefault(e.waiter, []).append(e.target)
    done: set[str] = set()

    def visit(node: str, path: list[str]) -> list[str] | None:
        if node in path:
            return path[path.index(node):]
        if node in done:
            return None
        for nxt in out.get(node, []):
            found = visit(nxt, path + [node])
            if found:
                return found
        done.add(node)
        return None

    for start in order:
        found = visit(start, [])
        if found:
            return sorted(set(found), key=order.index)
    return None


def _blocked_by(edges: list[_Edge], sources: list[str]) -> list[tuple[str, int]]:
    """Sessions waiting on `sources` directly or indirectly, with the ticket pointing toward them."""
    seen, queue, out = set(sources), list(sources), []
    while queue:
        node = queue.pop(0)
        for e in edges:
            if e.target == node and e.waiter not in seen:
                seen.add(e.waiter)
                queue.append(e.waiter)
                out.append((e.waiter, e.ticket))
    return out


_PRIORITY = ("needs-user", "item", "retired", "offline", "stalled")


def _flag(g, name: str, state, relay) -> str | None:
    fact = relay.agents.get(name) if relay is not None else None
    if state is not None and state.word == "needs-user":
        return "needs-user"
    if state is not None and state.word == "blocked" and state.item is not None:
        return "item"
    if fact is not None and fact.retired:
        return "retired"
    if state is not None and state.word in ("offline", "stalled"):
        return state.word
    return None


@dataclass(frozen=True)
class _Verdict:
    why: str
    todo: str
    who: str


def _classify(g: store.Group, now: str, name: str, assessment, relay) -> _Verdict:
    """Source categories of requirement 7.1 plus the idle-but-waited-on fallback; first match wins."""
    short = _short(g, name)
    state = assessment.lines.get(name)
    word = state.word if state is not None else None
    fact = relay.agents.get(name) if relay is not None else None
    if word == "needs-user":
        detail = f"（{fact.presence_detail}）" if fact is not None and fact.presence_detail else ""
        return _Verdict(f"等你在原会话亲自确认{detail}", f"打开「{short}」会话，确认它弹出的请求", "用户")
    asks = [it for it in items.pending(g) if it["sender"] == name and it["fullyStopped"]]
    if asks:
        it = asks[0]
        reply = (copy_line(it["no"], it["recommended"], it["suggestedReply"]) if it["recommended"]
                 else f"{it['no']} 你的决定")
        return _Verdict(f"等你决定 #{it['no']}：{it['decide'].splitlines()[0]}", f"回「{reply}」", "用户")
    if fact is not None and fact.retired:
        return _Verdict("身份失效（agent-relay 里这个身份已退役）", "叫醒后用原名重登", "插件 + agent-relay")
    if word == "offline":
        return _Verdict("掉线", f"巡视会自动叫醒，叫不醒请打开「{short}」", "插件，兜底用户")
    picked = next((s for s in assessment.signals if s.no == 2 and name in s.sessions), None)
    if picked is not None:
        waiter, sender = _short(g, picked.sessions[0]), _short(g, picked.sessions[1])
        return _Verdict(f"交付了没人接：{sender} 已发消息给 {waiter}，{waiter} 还没去取",
                        f"叫醒 {waiter} 去取{sender}的交付", "插件")
    if word == "stalled":
        return _Verdict(f"悄悄停下：{state.text}，还有已批准的任务没做完", f"叫醒 {short}，要它继续或上抛", "插件")
    if word == "working":
        since = fact.presence_since if fact is not None else None
        busy = f"，已忙 {ago(now, since).removesuffix('前')}" if since else ""
        return _Verdict(f"正在忙长任务{busy}", "不打扰，等它做完这一轮", "—")
    external = [t for t in tickets.open_tickets(g, now) if t.waiter == name
                and t.target not in tickets.USER_TARGETS and store.find_session(g, short_name=t.target) is None]
    if external:
        t = external[0]
        return _Verdict(f"等别的线交付：等 {t.target} 的「{_one_line(t.what)}」", "交负责人跟进", "负责人")
    text = state.text if state is not None else "无状态"
    return _Verdict(f"被等着但没在干活（{text}）", f"问 {short} 是否已交付，没交付就让它接着做", "用户")


def _short(g: store.Group, name: str) -> str:
    return (store.find_session(g, relay_name=name) or {}).get("shortName", name)


def _one_line(text: str) -> str:
    return "".join(part.strip() for part in text.split("\n"))


def _conclusion(g: store.Group, now: str, assessment, relay) -> list[str]:
    order = [e["relayName"] for e in store.roster(g) if e["role"] != "hub"]
    edges = _wait_graph(g, now)
    cycle = _cycle(edges, order)
    if cycle:
        sources, where = cycle, " ⇄ ".join(_short(g, n) for n in cycle)
        verdict = _Verdict("互等成环", "你来定谁先做", "用户")
        times = [e.sent_at for e in edges if e.waiter in cycle and e.target in cycle]
    else:
        waiters = {e.waiter for e in edges}
        candidates = [n for n in order if n in {e.target for e in edges} and n not in waiters]
        if candidates:
            def weight(n):
                first = min(_instant(e.sent_at) for e in edges if e.target == n)
                return (-len(_blocked_by(edges, [n])), first)
            source = min(candidates, key=weight)
        else:
            flagged = [(n, _flag(g, n, assessment.lines.get(n), relay)) for n in order]
            flagged = [(n, f) for n, f in flagged if f]
            if not flagged:
                return ["流畅：没有卡点"]
            source = min(flagged, key=lambda nf: _PRIORITY.index(nf[1]))[0]
        sources, where = [source], _short(g, source)
        verdict = _classify(g, now, source, assessment, relay)
        times = [e.sent_at for e in edges if e.target == source]
        if not times and assessment.lines.get(source) is not None and assessment.lines[source].since:
            times = [assessment.lines[source].since]
    if times:
        where += f"（{_clock(min(times, key=_instant))} 起）"
    blocked = _blocked_by(edges, sources)
    others = [n for n in order if n not in sources and n not in {b for b, _ in blocked}
              and n in assessment.lines]
    return [
        f"停在哪：{where}",
        f"为什么：{verdict.why}",
        f"你要做：{verdict.todo}（谁来做：{verdict.who}）",
        "被它挡住：" + ("、".join(f"{_short(g, n)}（#{no}）" for n, no in blocked) or "无"),
        "其他：" + (_join([f"{_short(g, n)} {assessment.lines[n].text}" for n in others]) or "无"),
    ]


WAKE_FAILED = ("held", "refused", "unknown", "expired")


def _minutes(now: str, then: str) -> int:
    return max(0, int((_instant(now) - _instant(then)).total_seconds() // 60))


def _details(g: store.Group, now: str, assessment, relay, wakes: dict) -> list[str]:
    order = [e["relayName"] for e in store.roster(g) if e["role"] != "hub"]
    edges = _wait_graph(g, now)
    cycle = _cycle(edges, order)
    chain = "；".join(f"{_short(g, e.waiter)} → {_short(g, e.target)}" for e in sorted(edges, key=lambda e: e.ticket))
    if not edges:
        chain = "无等待"
    else:
        chain += "；" + (f"有循环：{' ⇄ '.join(_short(g, n) for n in cycle)}" if cycle else "无循环")
    backlog = []
    for name in order:
        fact = relay.agents.get(name) if relay is not None else None
        if fact is None or not fact.waiting_count or not fact.waiting_oldest_at:
            continue
        waited = _minutes(now, fact.waiting_oldest_at)
        if waited < health.BACKLOG_MINUTES:
            continue
        text = f"{_short(g, name)} 有 {fact.waiting_count} 条未读，最早已等 {waited} 分钟"
        failed = sum(n for state, n in wakes.get(name, {}).items() if state in WAKE_FAILED)
        backlog.append(text + (f"，叫醒没成功 {failed} 次" if failed else ""))
    stalled = [sig.text for sig in assessment.signals if sig.no == 3]
    pending_senders = {it["sender"] for it in items.pending(g)}
    open_ = tickets.open_tickets(g, now)
    missed = [f"{_short(g, n)} 停在自己会话里等输入，但没抛【等待用户】" for n in order
              if relay is not None and n in relay.agents and relay.agents[n].presence_raw == "waiting-input"
              and n not in pending_senders and not any(t.waiter == n for t in open_)]
    long_waits = [f"{_short(g, t.waiter)} 等 {t.target}：{_one_line(t.what)} · 已阻塞 {t.minutes // 60} 小时 · "
                  "负责人跟进：第一版不记录"
                  for t in open_ if t.minutes >= tickets.STUCK_MINUTES and t.target not in tickets.USER_TARGETS]
    return [
        "检查明细",
        f"- 等待链：{chain}",
        f"- 积压：{'；'.join(backlog) or '无'}",
        f"- 停住的线：{'；'.join(stalled) or '无'}",
        f"- 漏抛：{'；'.join(missed) or '无'}",
        f"- 长期外部阻塞：{'；'.join(long_waits) or '无'}",
    ]


def render_flow(g: store.Group, now: str, assessment, relay=None, wakes: dict | None = None) -> str:
    """/flow: one conclusion, then the five check details."""
    return "\n\n".join(["\n".join(_conclusion(g, now, assessment, relay)),
                        "\n".join(_details(g, now, assessment, relay, wakes or {}))])


_ITEM_STATUS = {"pending": "待答", "superseded": "已取代", "withdrawn": "已撤回", "forwarded": "已转达",
                "picked": "对方已取走", "acknowledged": "对方已确认", "closed": "已结束"}


def item_message_ids(g: store.Group, number: int) -> tuple[int, ...]:
    """agent-relay ids to look up for /item: the 【等待用户】 itself, then each reply sent."""
    it = items.get(g, number)
    if it is None:
        return ()
    ids = [it["relayId"]] + [s["relayId"] for s in sorted(it["sent"], key=lambda s: _instant(s["at"]))]
    return tuple(dict.fromkeys(i for i in ids if isinstance(i, int)))


def _status_rows(g: store.Group, relay_id: int, at: str, statuses: dict) -> list[tuple[str, str]]:
    st = statuses.get(relay_id)
    if st is None:
        return [(at, f"agent-relay 查不到 #{relay_id}")]
    parts = [f"投递 {st.delivery_state or '未知'}"]
    if st.wake_state:
        parts.append(f"唤醒 {st.wake_state}" + (f"（{st.wake_detail}）" if st.wake_detail else ""))
    if st.reply_ids:
        parts.append("回复 " + "、".join(f"#{r}" for r in st.reply_ids))
    if st.outcome:
        parts.append(f"结果 {st.outcome}")
    rows = [(st.sent_at or at, f"agent-relay #{relay_id}：" + "，".join(parts))]
    if st.acknowledged_at:
        rows.append((st.acknowledged_at, f"agent-relay #{relay_id}：{_short(g, st.recipient)} 已确认"))
    return rows


def _item_timeline(g: store.Group, it: dict, statuses: dict) -> list[str]:
    no, times = it["no"], it["statusAt"]
    events = {e["type"]: e for e in items.history(g, no)}
    rows = [(it["receivedAt"], f"{_short(g, it['sender'])} 抛出（agent-relay #{it['relayId']}；"
                               f"审查：{it['review']['text']}）")]
    rows += _status_rows(g, it["relayId"], it["receivedAt"], statuses)
    if "superseded" in times:
        by = events.get("items.superseded", {}).get("data", {}).get("by", "?")
        rows.append((times["superseded"], f"被 #{by} 取代"))
    if "withdrawn" in times:
        reason = events.get("items.withdrawn", {}).get("data", {}).get("reason")
        rows.append((times["withdrawn"], "提出方撤回" + (f"（原因：{reason}）" if reason else "")))
    for a in it["answers"]:
        rows.append((a["at"], f"你答复：{a['original']}"))
    for s in it["sent"]:
        rows.append((s["at"], f"转发给 {_short(g, s['to'])}（agent-relay #{s['relayId']}）"))
        rows += _status_rows(g, s["relayId"], s["at"], statuses)
    if "picked" in times:
        rows.append((times["picked"], "对方已取走"))
    if "acknowledged" in times:
        rows.append((times["acknowledged"], "对方已确认"))
    if "closed" in times:
        actor = events.get("items.closed", {}).get("actor", it["sender"])
        rows.append((times["closed"], f"{_short(g, actor)} 已恢复，事项结束"))
    source = f"多线：{'＋'.join(it['lines'])}" if it["multi"] else _short(g, it["sender"])
    head = (f"#{no} · {source} · {it['decide'].splitlines()[0]} · "
            f"当前：{_ITEM_STATUS.get(it['status'], it['status'])}")
    return [head] + [f"{_clock(t)} {text}" for t, text in sorted(rows, key=lambda r: _instant(r[0]))]


def _ticket_timeline(g: store.Group, number: int, t: dict) -> list[str]:
    from decision_inbox.view import CLOSE_REASONS
    waiter = _short(g, t["waiter"])
    head = f"#{number} · 等待单 · {waiter} 等 {t['target']} · 当前：{'开着' if t['status'] == 'open' else '已关'}"
    rows = [f"{_clock(t['sentAt'])} {waiter} 开单：等 {t['target']} 的「{_one_line(t['what'])}」"
            f"（agent-relay #{t['relayId']}）"]
    if t.get("close"):
        c = t["close"]
        rows.append(f"{_clock(c['at'])} 关单：{CLOSE_REASONS.get(c['reason'], c['reason'])}，依据：{c['basis']}")
    return [head] + rows


def render_item(g: store.Group, number: int, statuses: dict | None = None) -> str:
    """/item: one item's or wait ticket's timeline; message bodies never appear."""
    it = items.get(g, number)
    if it is not None:
        return "\n".join(_item_timeline(g, it, statuses or {}))
    t = store.read_state(g, tickets.DOMAIN).get("tickets", {}).get(str(number))
    if t is not None:
        return "\n".join(_ticket_timeline(g, number, t))
    return f"#{number} 不是事项也不是等待单"
