"""The hub's main view and expanded views (see spec/hub-view.md).

Layout only: states and signals come from line-health, items from
decision-queue, tickets from wait-tickets. Nothing here judges or writes.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime

from decision_inbox import approval, items, sources, specguard, stall, store, tickets

RECENT_MINUTES = 10
COPY_LABEL = "推荐回复（点代码块右上角复制，发给我）："  # says what the copy block is even when it is not rendered
TOPIC_CHARS = 20
FORWARDED = ("forwarded", "picked", "acknowledged", "closed")
INVALIDATED = ("superseded", "withdrawn")


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _minutes(now: str, then: str) -> int:
    return max(0, int((_instant(now) - _instant(then)).total_seconds() // 60))


def ago(now: str, then: str) -> str:
    minutes = _minutes(now, then)
    if minutes < 60:
        return f"{minutes} 分钟前"
    if minutes < 24 * 60:
        return f"{minutes // 60} 小时前"
    return f"{minutes // (24 * 60)} 天前"


def waited(minutes: int) -> str:
    """A duration without 前: N 分钟 / N 小时 / N 天 (shared by map-view and stop-hook)."""
    if minutes < 60:
        return f"{minutes} 分钟"
    return f"{minutes // 60} 小时" if minutes < 24 * 60 else f"{minutes // (24 * 60)} 天"


def clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def copy_line(no: int, letter: str, reply: str | None) -> str:
    """Decided format 8: drop a guessed leading number, never repeat the letter the reply starts with."""
    reply = re.sub(r"^\d+\s+", "", reply or "")
    if not reply:
        return f"{no} {letter}"
    if reply.startswith(letter) and reply[len(letter):len(letter) + 1] in ("", " ", ":", "：", "；", "，"):
        return f"{no} {reply}"
    return f"{no} {letter} {reply}"


def _short(g: store.Group, relay_name: str) -> str:
    return (store.find_session(g, relay_name=relay_name) or {}).get("shortName", relay_name)


def _today(now: str) -> str:
    return _instant(now).astimezone().date().isoformat()


def _push_line(g: store.Group, now: str, assessment) -> str | None:
    """Decided format 5: the session waited on most that itself waits for nobody."""
    if not any(s.no == 1 for s in assessment.signals):
        return None
    open_ = [t for t in tickets.open_tickets(g, now) if t.maybe_stale is None]
    if not open_:
        return None
    on_sessions = [t for t in open_ if t.target not in tickets.USER_TARGETS]
    waiting = {_short(g, t.waiter) for t in on_sessions}
    counts = Counter(t.target for t in on_sessions if t.target not in waiting)
    ranked = counts.most_common(2)
    if ranked and (len(ranked) == 1 or ranked[0][1] > ranked[1][1]):
        where = f"卡在 {ranked[0][0]}"
    else:
        where = "卡在哪见 /flow"
    return f"⚠ 全线停住 {max(t.minutes for t in open_)} 分钟：{where}"


def _lines_row(g: store.Group, assessment) -> str | None:
    parts = []
    for entry in store.roster(g):
        state = assessment.lines.get(entry["relayName"])
        if state is not None:
            parts.append(f"{entry['shortName']} {state.text.replace('阻塞：等 ', '阻塞：等')}")
    return " · ".join(parts) or None


def _needs_user(g: store.Group, assessment) -> list[str]:
    return [e["relayName"] for e in store.roster(g)
            if getattr(assessment.lines.get(e["relayName"]), "word", None) == "needs-user"]


def _anomalies(assessment) -> list:
    return [s for s in assessment.signals if s.no != 1]


_ADVICE = {
    3: "问 {who} 是否卡住，或让它继续或上抛",
    4: "打开 {who} 让它恢复",
    5: "先等它做完这一轮；要插队就去它的会话说明",
    6: "看挂起原因是否已经解决",
    7: "看一下这次审查的分歧点",
    8: "问 {who} 进展，或交审查者跟进",
    9: "确认旧等待是否还需要，不需要就说「关掉 W{ticket}」",
    10: "在 Codex 里点开 {who} 让它加载",
    11: "完全退出 ChatGPT 再打开 {who} 的任务",
}
# A signal number shared by two cases picks its advice by code (relay-presence-and-doubt).
_ADVICE_BY_CODE = {"idle-backlog": "巡视会叫醒 {who}；叫不醒就打开它"}
# The patrol can wake Claude sessions only (p0-field-fixes F-P0-2).
_ADVICE_FOR_CODEX = {"idle-backlog": "打开 {who} 的任务"}


def advice(g: store.Group, signal) -> str:
    """The fixed advice sentence for signals 3～10 (shared with patrol's owner alerts)."""
    who = _short(g, signal.sessions[0]) if signal.sessions else "?"
    found = re.search(r"等待记录 W(\d+)", signal.text)
    entry = store.find_session(g, relay_name=signal.sessions[0]) if signal.sessions else None
    by_code = _ADVICE_FOR_CODEX if (entry or {}).get("host") == "codex-desktop" else {}
    text = by_code.get(signal.code) or _ADVICE_BY_CODE.get(signal.code, _ADVICE.get(signal.no, ""))
    return text.format(who=who, ticket=found.group(1) if found else "编号")


def _anomaly_row(g: store.Group, signal) -> str:
    """Signal advice table: who, where it is stuck, what to do."""
    who = _short(g, signal.sessions[0]) if signal.sessions else "?"
    if signal.no == 2:
        target = _short(g, signal.sessions[1])
        return (f"- {who}：交付了没人接——{target} 已发消息给 {who}，{who} 还没去取。"
                f"建议：提醒 {who} 去取{target}的交付")
    return f"- {who}：{signal.text}。建议：{advice(g, signal)}"


def _anomaly_section(g: store.Group, assessment, extra=()) -> str | None:
    rows = [_anomaly_row(g, s) for s in _anomalies(assessment)] + list(extra)
    return "\n".join(["异常", *rows]) if rows else None


def _overview(g: store.Group, now: str, assessment, extra=()) -> str:
    decide = len([it for it in items.pending(g) if not items.is_go_to_session(it)]) + len(_needs_user(g, assessment))
    text = f"等你决定 {decide} 项 · 异常 {len(_anomalies(assessment)) + len(extra)}"
    recent = [it for it in items.by_status(g, *FORWARDED)  # a go-to-session item is closed without forwarding
              if "forwarded" in it["statusAt"] and _minutes(now, it["statusAt"]["forwarded"]) <= RECENT_MINUTES]
    if recent:
        recent.sort(key=lambda it: _instant(it["statusAt"]["forwarded"]))
        text += " · 刚转达：" + "、".join(
            f"{it['no']} → {'＋'.join(_short(g, r) for r in it['recipients'])}" for it in recent)
    return text


def _footer(g: store.Group, now: str) -> str:
    count = tickets.counts(g, _today(now))
    invalid = len(items.by_status(g, *INVALIDATED))
    stale = len(tickets.stale_tickets(g))
    waiting = f"等待中 {count['open']} 条" + (f"（其中 {stale} 条可能已失效）" if stale else "")
    return f"{waiting} · 已失效 {invalid} 项 · 今天已关 {count['closed_today']} 条"


def _confirm_card(g: store.Group, now: str, relay_name: str, relay) -> str:
    """Decided format 4: a host permission prompt waiting in the session itself."""
    short = _short(g, relay_name)
    fact = relay.agents.get(relay_name) if relay is not None else None
    title = f"━━ 去原会话确认 · {short}"
    if fact is not None and fact.presence_since:
        title += f" · {ago(now, fact.presence_since)}"
    detail = f"（{fact.presence_detail}）" if fact is not None and fact.presence_detail else ""
    card = f"{title}\n要你做：打开「{short}」会话，确认它弹出的请求{detail}"
    entry = store.find_session(g, relay_name=relay_name) or {}
    if entry.get("host") == "claude-desktop" and entry.get("desktopSession"):
        card += f"\n  链接：claude://claude.ai/epitaxy/{entry['desktopSession']}"  # stall-and-patrol R16; never approves
    return card


def _source(g: store.Group, it: dict) -> str:
    return f"多线：{'＋'.join(it['lines'])}" if it["multi"] else _short(g, it["sender"])


def _review_lines(it: dict) -> list[str]:
    review = it["review"]
    label = f"**{review['text']}**" if review.get("highlight") else review["text"]
    out = [f"审查：{label} · 详情：{it['no']} 详情"]
    if review.get("warn"):
        out += [f"  正文提到：{m}" for m in review.get("mentions", [])]
    if it.get("writingNotes"):  # rehearsal2-fixes: shown to the user only
        out.append("写法提示：" + "；".join(it["writingNotes"]))
    return out


def _decision_lines(it: dict) -> list[str]:
    """Each 「待用户决定」 as its own question with the reviewer's lean (review-nearby R2)."""
    out = ["待你决定的问题（每条都要答，没答全会被追问）："]
    for d in it.get("decisions") or ():
        out.append(f"{d['id']}：{d['question']}")
        out.append("  " + "　".join(f"{letter}. {text}" for letter, text in d["options"]))
        if d["lean"]:
            out.append(f"  审查倾向：{d['lean']}" + (f"（{d['leanReason']}）" if d.get("leanReason") else ""))
    return out if len(out) > 1 else []


def _unanswered_in_copy(it: dict, line: str) -> str | None:
    missing = [d["id"] for d in it.get("decisions") or ()
               if not re.search(rf"(?<![A-Za-z0-9]){d['id']}(?![0-9])", line)]
    return f"  还要答 {'、'.join(missing)}，写在同一条回复里" if missing else None


def _item_card(g: store.Group, now: str, it: dict, loop_facts=None) -> str:
    no = it["no"]
    topic = clip(it["decide"].split("\n")[0], TOPIC_CHARS)
    if loop_facts is None:
        title = f"━━ {no} · {_source(g, it)} · {topic} · {ago(now, it['receivedAt'])}"
    else:  # loop-detection: the fixed head of DI-5
        title = loop_head(g, it, "等待用户", _loop_of(it, loop_facts), now)
    if it["blocks"]:
        title += f" · 挡住 {it['blocks']} 条线"
    out = [*_hint(g, it, loop_facts), title, f"要你决定：{it['decide']}"]
    options = it["options"]
    rec = next((o for o in options if o["letter"] == it["recommended"]), None)
    if rec is not None:
        options = [rec] + [o for o in options if o is not rec]
    for o in options:
        first = o["text"].split("\n")[0]  # whole first line: clipped options looked alike (e2e-round1-fixes F12)
        out.append(f"推荐 {o['letter']}：{first}" if o is rec else f"{o['letter']}：{first}")
        out.append(f"  选了会怎样：{o['consequence'] or '提出方未说明后果'}")
        if o is rec:
            line = copy_line(no, o["letter"], it["suggestedReply"])
            out += [COPY_LABEL, "```", line, "```"]
            if (gap := _unanswered_in_copy(it, line)) is not None:
                out.append(gap)
        else:
            out.append(f"  回 {no} {o['letter']}")
    return "\n".join(out + _decision_lines(it) + _review_lines(it) + _folded(it, loop_facts))


def _combined(g: store.Group) -> str | None:
    """One copy block answering every recommended card at once (relay-checkpoint-authority R4)."""
    pending = [it for it in items.pending(g) if not items.is_go_to_session(it)]  # nothing to answer
    asks = [it for it in pending if it.get("decisions")]  # answered on their own (review-nearby R2)
    pending = [it for it in pending if not it.get("decisions") and not approval.is_approval(it)]
    picks = [f"{it['no']} {it['recommended']}" for it in pending if it["recommended"]]
    if len(picks) < 2:
        return None
    out = ["一次答完（全按推荐）：", "```", "，".join(picks), "```"]
    out += [f"#{it['no']} 没有推荐，要单独回" for it in pending if not it["recommended"]]
    out += [f"#{it['no']} 带待你决定的问题，要单独回" for it in asks]
    return "\n".join(out)


ADDED = "【决策收件箱补充】"
ORIGINAL = "【原文】"
NODE_EFFECTS = {"Spec": "Spec 批准后，授权写 Plan；不授权开始实现。",
                "Plan": "Plan 批准后，授权按 Plan 开始实现；最终验收另审。",
                "最终验收": "最终验收批准后，授权合并进集成分支；合并后撤不回。",
                "接口提案": "接口提案批准后，授权按提案改接口；用到它的模块要跟着改。"}


def _verbatim(text: str, path: str) -> list[str]:
    """Markdown files render as they do in their project; anything else is fenced so every line shows as is.

    The fence is longer than any backtick run inside, so the original can never close it early.
    """
    body = text.rstrip("\n")
    if path.endswith(".md"):
        return [body]
    longest = max((len(run) for run in re.findall(r"`+", body)), default=0)
    fence = "`" * max(3, longest + 1)
    return [fence + "text", body, fence]


def _original_lines(kind: str, ref: dict) -> list[str]:
    title = {"submission": "开发会话的交审原文", "conclusion": "审查结论原文"}[kind]
    got = sources.read_original(ref["path"], ref["fingerprint"])
    head = f"━━ {title}（{ref['path']}）{ORIGINAL}"
    if not got.ok:
        return [head, f"原文取不到：{ref['path']} {ref['fingerprint']} —— {got.reason}"]
    return [head, *_verbatim(got.text, ref["path"])]


def _artifact_lines(a: dict) -> list[str]:
    got = sources.read_artifact(a["path"], a["commit"], a.get("previous"))
    head = f"━━ {a['path']} @ {a['commit']}{ORIGINAL}"
    if not got.ok:
        return [head, f"原文取不到：{a['path']} ＠ {a['commit']} —— {got.reason}"]
    out = [head]
    if got.diff is not None:
        out += [f"与上一版 {a['previous']} 的差异：", *_verbatim(got.diff, "diff"), "全文："]
    return out + _verbatim(got.text, a["path"])


def _module_sources(it: dict, keep) -> list[str]:
    """Submission, artifacts, conclusion — in that order — for the refs `keep` selects."""
    originals = it.get("originals") or {}
    out = []
    for ref in originals.get("submission", ()):
        out += _original_lines("submission", ref) if keep(ref) else []
    for a in it.get("artifacts") or ():
        out += _artifact_lines(a) if keep(a) else []
    for ref in originals.get("conclusion", ()):
        out += _original_lines("conclusion", ref) if keep(ref) else []
    return out


def _submission_text(it: dict) -> str | None:
    for ref in (it.get("originals") or {}).get("submission", ()):
        got = sources.read_original(ref["path"], ref["fingerprint"])
        if got.ok:
            return got.text
    return None


def render_approval(g: store.Group, it: dict, now: str, read_map=specguard.read_line, loop_facts=None) -> str:
    """An approval item in full (approval-display): background, originals verbatim, recommendation last."""
    no = it["no"]
    bg = approval.background(g, it, read_map=read_map)
    node = bg.node or "未知节点"
    head = (f"━━ #{no} · {bg.project} · 模块 {bg.module or '未知'} · 审 {node} · {ago(now, it['receivedAt'])}"
            if loop_facts is None else loop_head(g, dict(it, project=bg.project), f"审 {node}",
                                                 _loop_of(it, loop_facts), now))
    out = [*_hint(g, it, loop_facts), head + ADDED,
           f"项目：{bg.project}（{bg.repo or '仓库未知'}）· 线：{_short(g, it['sender'])}"]
    out += ["能力图：", *(f"  {line}" for line in bg.map_lines)] if bg.map_lines else [f"能力图读不到：{bg.map_error}"]
    round_ = f"本项：{node}，第 {bg.round} 次交审"
    out.append(round_ + (f"（上次你答：{bg.last_answer}）" if bg.last_answer else ""))
    out.append("相关决定：" + ("；".join(bg.related) if bg.related else "无"))
    if bg.node in approval.FINAL_NODES:
        out += [f"━━ 验收标准与证据【对照】", *approval.evidence_table(it, _submission_text(it))]
    modules = approval.modules_of(it)
    if len(modules) > 1:  # several modules in one item: one section each (decision 47)
        for module in modules:
            out += [f"━━ 模块 {module}", *_module_sources(it, lambda ref, m=module: ref.get("module") == m)]
        if rest := _module_sources(it, lambda ref: not ref.get("module")):
            out += ["━━ 没写模块的原文", *rest]
    else:
        out += _module_sources(it, lambda ref: True)
    rec = next((o for o in it["options"] if o["letter"] == it["recommended"]), None)
    out += [f"━━ 批准会发生什么{ADDED}", NODE_EFFECTS.get(bg.node, "节点未知，以提出方写的后果为准。")]
    if rec is not None and rec["consequence"]:
        out.append(f"提出方写的推荐选项 {rec['letter']} 的后果：{rec['consequence']}")
    if it.get("decisions"):
        out += [f"━━ 待你决定{ADDED}", *_decision_lines(it)[1:]]
    out.append(f"━━ 选项与推荐（放最后，只作参考）{ADDED}")
    for o in it["options"]:
        out += [f"{o['letter']}：{o['text']}", f"  选了会怎样：{o['consequence'] or '提出方未说明后果'}"]
    example = " ".join([str(no), rec["letter"] if rec else it["options"][0]["letter"]])
    example += "".join(f"；{d['id']} {d['lean'] or d['options'][0][0]}" for d in it.get("decisions") or ())
    if rec is not None:
        out.append(f"推荐 {rec['letter']}：{rec['text']}；答复写法示例：{example}")
    else:
        out.append(f"提出方没写推荐；答复写法示例：{example}")
    return "\n".join(out + _folded(it, loop_facts))


def _approval_line(g: store.Group, now: str, it: dict) -> str:
    return (f"━━ #{it['no']} · {it.get('project') or _short(g, it['sender'])} · 模块 {it.get('approvalModule') or '未知'}"
            f" · 审 {it.get('approvalNode') or '未知节点'} · {ago(now, it['receivedAt'])} · 回「看 {it['no']}」看全文")


def render_look(g: store.Group, no: int, now: str) -> str:
    """「看 N」: one pending item in full."""
    it = next((x for x in items.pending(g) if x["no"] == no), None)
    if it is None:
        return f"#{no} 不在待答表里"
    return render_approval(g, it, now) if approval.is_approval(it) else _item_card(g, now, it)


GO_TO_SESSION_REMIND_MINUTES = 30
_LINK = "claude://claude.ai/epitaxy/{}"


def _go_to_where(it: dict) -> str:
    gts = it["goToSession"]
    link = gts.get("link") or ""
    if link.startswith("claude://"):
        return f"去：{gts['session']}（{link}）"
    if link.startswith("local_"):
        return f"去：{gts['session']}（{_LINK.format(link)}）"
    return f"去：在 Codex 应用里打开 {gts['session']} 对应的任务"


def go_to_session_rows(g: store.Group, now: str) -> list[str]:
    """go-to-session (R21 DI-7): what the user must click in another session, on top of the main view."""
    rows = []
    for it in items.pending(g):
        if not items.is_go_to_session(it):
            continue
        gts, waited = it["goToSession"], _minutes(now, it["receivedAt"])
        title = f"#{it['no']} · {_short(g, it['sender'])} · 去会话操作"
        if waited >= GO_TO_SESSION_REMIND_MINUTES:
            title += f"（已等 {waited} 分钟，再提醒一次）"
        lines = [title, f"  {_go_to_where(it)}", f"  被拦的操作：{gts['blockedAction']}", f"  点：{gts['button']}",
                 f"  为什么这里批不了：{gts['reason']}"]
        if gts.get("hostText"):
            lines.append(f"  宿主原文：{gts['hostText']}")
        if gts.get("relatedItem"):
            lines.append(f"  你在 #{gts['relatedItem']} 已同意，只差宿主这一下")
        lines.append("  点完不用回复，对方会发【已恢复】自动结项")
        rows.append("\n".join(lines))
    return ["⚠ 要你去会话里操作：\n" + "\n".join(rows)] if rows else []


def _cards(g: store.Group, now: str, assessment, relay, loop_facts=None) -> list[str]:
    reported = {it["sender"] for it in items.pending(g) if items.is_go_to_session(it)}
    confirms = [_confirm_card(g, now, name, relay) for name in _needs_user(g, assessment) if name not in reported]
    cards, opened = [], False
    for it in items.pending(g):
        if items.is_go_to_session(it):
            continue  # shown on top by go_to_session_rows
        if not approval.is_approval(it):
            cards.append(_item_card(g, now, it, loop_facts))
        elif not opened:  # only the first approval opens in full (approval-display decision 1)
            cards.append(render_approval(g, it, now, loop_facts=loop_facts))
            opened = True
        else:
            cards.append(_approval_line(g, now, it))
    return confirms + cards


def render(g: store.Group, now: str, assessment, relay=None, extra=(), loop_facts=None) -> str:
    """Main view, fixed order (requirement 6.1): push, lines, overview, anomalies, cards, counts.

    `extra` holds anomaly rows the caller found outside line-health (hub-loop's returned questions).
    """
    head = [line for line in (_push_line(g, now, assessment), _lines_row(g, assessment)) if line]
    head.append(_overview(g, now, assessment, extra))
    sections = ["\n".join(head), _modules_section(g, now, loop_facts), _anomaly_section(g, assessment, extra),
                *_cards(g, now, assessment, relay, loop_facts),
                _combined(g), _footer(g, now)]
    return "\n\n".join(s for s in sections if s)


CLOSE_REASONS = {1: "对方明说结束", 2: "被取代", 3: "所等的事已发生", 4: "用户关闭"}


def _one_line(text: str) -> str:
    return "".join(part.strip() for part in text.split("\n"))


def _clock(value: str) -> str:
    return _instant(value).astimezone().strftime("%H:%M")


def render_detail(g: store.Group, item: int) -> str:
    """「编号 详情」: full text, line scopes and agent-relay message ids."""
    it = items.get(g, item)
    if it is None:
        return f"#{item} 不存在"
    out = [f"#{item} 详情 · {_source(g, it)} · 收到于 {_clock(it['receivedAt'])}",
           f"agent-relay 消息编号：{it['relayId']}"]
    if it["sent"]:
        out.append("答复发送编号：" + "、".join(f"{_short(g, s['to'])} #{s['relayId']}" for s in it["sent"]))
    out += [f"各线范围：{name}：{_one_line(it['scopes'][name])}" for name in it["lines"] if name in it["scopes"]]
    return "\n".join(out + ["原文：", it["text"].rstrip("\n")])


def wait_no(no) -> str:
    """A wait record's number as shown to people: W3 (术语表 v1.1; #数字 is for items only)."""
    return f"W{no}"


def _ticket_head(g: store.Group, waiter: str, target: str, what: str) -> str:
    return f"{_short(g, waiter)} 等 {target}：{_one_line(what)}"


def render_waits(g: store.Group, now: str, relay=None) -> str:
    """「看等待」: one line per open ticket with wait-tickets' marks."""
    rows = []
    for t in tickets.open_tickets(g, now, relay):
        parts = [f"{wait_no(t.no)} {_ticket_head(g, t.waiter, t.target, t.what)}"]
        if "waited" not in t.marks:
            parts.append(f"已等 {t.minutes} 分钟")
        row = " · ".join(parts + [_one_line(n) for n in t.notes])
        if t.maybe_stale is not None:
            row += f"（可能已失效：之后又发过 #{t.maybe_stale}，回『关掉 {wait_no(t.no)}』）"
        rows.append(row)
    return "\n".join(rows) or "没有开着的等待记录"


def render_closed(g: store.Group, day: str) -> str:
    """「看已关闭」: tickets closed on `day` with reason and basis."""
    rows = [f"{wait_no(t['no'])} {_ticket_head(g, t['waiter'], t['target'], t['what'])} · "
            f"{CLOSE_REASONS.get(t['close']['reason'], t['close']['reason'])} · 依据：{t['close']['basis']} · "
            f"{_clock(t['close']['at'])} 关"
            for t in tickets.closed_on(g, day)]
    return "\n".join(rows) or f"{day} 没有关闭的等待记录"


def render_invalidated(g: store.Group) -> str:
    """「看失效」: superseded and withdrawn items, one line each."""
    rows = []
    for it in items.by_status(g, *INVALIDATED):
        events = {e["type"]: e.get("data", {}) for e in items.history(g, it["no"])}
        if it["status"] == "superseded":
            state = f"已取代（被 #{events.get('items.superseded', {}).get('by', '?')} 取代）"
        else:
            reason = events.get("items.withdrawn", {}).get("reason")
            state = f"已撤回（{reason}）" if reason else "已撤回 "
        topic = clip(it["decide"].split("\n")[0], TOPIC_CHARS)
        rows.append(f"#{it['no']} {state}· {_source(g, it)} · {topic}")
    return "\n".join(rows) or "没有失效的待决事项"


# loop-detection (R21 DI-5): a module's earlier questions, one line each; the module's facts in a few words.
HISTORY_ROWS = 5


def _result(it: dict) -> str:
    if items.is_go_to_session(it):
        return "去会话操作已结项" if it["status"] == "closed" else "去会话操作"
    if it["status"] == "pending":
        return "等你答"
    if it["status"] in INVALIDATED:
        return "已失效"
    if it.get("answers"):
        a = it["answers"][-1]
        return f"答了 {a.get('loopOption') or a.get('letter') or clip(_one_line(a['original']), 12)}"
    return "已关"


def history_rows(own, before: int | None = None) -> list[str]:
    """「第 i 次 · 要你决定首行 · 结果」 for a module's items (before item `before` when given)."""
    rows, n = [], 0
    for it in own:
        if before is not None and it["no"] == before:
            break
        counted = not items.is_go_to_session(it) and it["status"] != "superseded"
        n += counted
        head = f"第 {n} 次" if counted else "不计次"
        rows.append(f"{head} · #{it['no']} {clip(it['decide'].split(chr(10))[0], TOPIC_CHARS)} · {_result(it)}")
    return rows


def _worked_text(hours: float) -> str:
    return "开工不到 1 小时" if hours < 1 else f"开工 {hours:.0f} 小时"


def loop_facts_text(f) -> str:
    """「第 n 次问你（基准 M，超出第 k 次）· 你答了 j 次进度没动 · 开工 X 小时 · 进度 a/b」."""
    base = f"基准 {f.baseline}" if f.baseline is not None else "基准未知"
    if f.over:
        base += f"，超出第 {f.over} 次"
    parts = [f"第 {f.asked} 次问你（{base}）"]
    parts.append(f"你答了 {f.still} 次进度没动" if f.still is not None else (f.unread or "进度读不到"))
    if f.worked_hours is not None:
        parts.append(_worked_text(f.worked_hours))
    if f.progress is not None:
        parts.append(f"进度 {f.progress[0]}/{f.progress[1]}")
    return " · ".join(parts)


def render_module(g: store.Group, module: str, now: str, loop_facts=None) -> str:
    """「看模块 <id>」: every question of the module and its facts."""
    found = [f for f in loop_facts or () if f.module == module]
    if found:
        f = found[0]
        own = list(f.items)
        head = f"模块 {module}（{_short(g, f.line)}）· {loop_facts_text(f)}"
        if f.hit:
            head += f"\n⚠ 可能在打转：{f.hit}"
    else:
        own = sorted((it for it in items.by_status(g, *_EVERY) if it.get("module") == module),
                     key=lambda it: _instant(it["receivedAt"]))
        head = f"模块 {module}（不在做的模块里，只列问过的待决事项）"
    if not own:
        return f"模块 {module} 还没有问过你的待决事项"
    return "\n".join([head, *history_rows(own)])


_EVERY = ("pending", *FORWARDED, *INVALIDATED)


def _loop_of(it: dict, loop_facts):
    return next((f for f in loop_facts or () if f.line == it["sender"] and f.module == it.get("module")), None)


def loop_head(g: store.Group, it: dict, kind: str, f, now: str) -> str:
    """「━━ #N · 项目 · 模块 <id> · <节点或类型> · 第 n 次问你（基准 M）· … · 多久前」 (DI-5)."""
    module = it.get("module")
    short = _short(g, it["sender"])
    project = it.get("project") or (f.project if f is not None else short)
    parts = [f"━━ #{it['no']}", project if project == short else f"{project}（{short}）",
             f"模块 {module}" if module else "模块未知", kind]
    if module and f is not None:
        parts.append(loop_facts_text(f))
    return " · ".join(parts + [ago(now, it["receivedAt"])])


def _hint(g: store.Group, it: dict, loop_facts) -> list[str]:
    """On top of an open item of a module that looks like going round in circles (DI-6)."""
    f = _loop_of(it, loop_facts)
    if f is None or not f.hit or items.is_go_to_session(it):
        return []
    no, ready = it["no"], "、".join(f.ready) or "能力图里暂时没有可开工的模块"
    hours = stall.settings(g)["loopQuietHours"]
    return [f"⚠ 模块 {f.module} 可能在打转：{f.hit}",
            f"  A 挂起它，先开可开工的模块（{ready}）：回「{no} 挂起」",
            f"  B 换方案：回「{no} 换方案：<怎么换>」",
            f"  C 继续等，{hours:g} 小时内不再提示：回「{no} 继续等」"]


def _folded(it: dict, loop_facts) -> list[str]:
    """The module's earlier questions, one line each, the latest HISTORY_ROWS of them (DI-5)."""
    f = _loop_of(it, loop_facts)
    rows = history_rows(list(f.items), before=it["no"]) if f is not None else []
    if not rows:
        return []
    out = ["同模块之前问过：", *(f"  {r}" for r in rows[-HISTORY_ROWS:])]
    if len(rows) > HISTORY_ROWS:
        out.append(f"  还有 {len(rows) - HISTORY_ROWS} 次，回「看模块 {f.module}」看全部")
    return out


def _modules_section(g: store.Group, now: str, loop_facts) -> str | None:
    """「在做的模块」: one line per module in progress (DI-5)."""
    rows = []
    for f in loop_facts or ():
        base = f.baseline if f.baseline is not None else "未知"
        row = f"{_short(g, f.line)} · 模块 {f.module} · 问了 {f.asked} 次（基准 {base}）"
        if f.worked_hours is not None:
            row += f" · {_worked_text(f.worked_hours)}"
        row += f" · 最后一次进展 {ago(now, f.last_progress)}" if f.last_progress else " · 还没有进展记录"
        if f.unread:
            row += f" · {f.unread}"
        if f.hit:
            row += " · ⚠ 可能在打转"
        rows.append(row)
    return "\n".join(["在做的模块", *rows]) if rows else None


def loop_rows(g: store.Group, loop_facts) -> list[str]:
    """Main view, right after the go-to-session rows: each module that looks like going round in circles."""
    return [f"⚠ 模块 {f.module}（{_short(g, f.line)}）可能在打转：{f.hit}；等它下次来问时在那一项上选，或去会话里说"
            for f in loop_facts or () if f.hit]
