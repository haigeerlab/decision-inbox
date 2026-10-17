"""The hub session's main loop: receive, reply, record sends (see spec/hub-loop.md).

The hub session only calls agent-relay and carries out what these functions
return; every judgement and every record lives here or in the modules they
call. The `hub` domain is written only by this module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from decision_inbox import health, install, items, protocol, reviews, store, tickets, view

DOMAIN = "hub"
BRIDGE = "bridge"  # agent-relay's automated notices (never answered)
KIND_LABELS = {"wait-session": "等待其他会话", "resumed": "已恢复", "review-conclusion": "审查结论"}


@dataclass
class Receipt:
    sends: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    ack: list = field(default_factory=list)
    unread: list = field(default_factory=list)
    more: bool = False


def _doc(tx) -> dict:
    doc = tx.read_state(DOMAIN)
    for key in ("received", "outgoing", "unknown"):
        doc.setdefault(key, {})
    doc.setdefault("nextOut", 1)
    return doc


def _short(g: store.Group, relay_name: str) -> str:
    return (store.find_session(g, relay_name=relay_name) or {}).get("shortName", relay_name)


def _first_line(text: str) -> str:
    return next((line.strip() for line in text.split("\n") if line.strip()), "")


def _return_text(label: str, problems) -> str:
    """Same wording as decision-queue's return note, for the other message kinds."""
    lines = [f"退回：你的【{label}】没有处理，原因："]
    lines += [f"- {p.text}" for p in problems]
    lines.append("请补全后重新发送。")
    return "\n".join(lines)


def _queue(g: store.Group, tx, doc: dict, to: str, text: str, reply_to, kind: str, item, at: str) -> dict:
    """Keep one message to send; its body goes to a file the hub sends unchanged (bodyFile)."""
    n = doc["nextOut"]
    doc["nextOut"] = n + 1
    folder = g.path / "outgoing"
    folder.mkdir(mode=0o700, exist_ok=True)
    path = folder / f"{n}.txt"
    store._atomic_write_bytes(path, text.encode("utf-8"))
    out_id = f"out:{n}"
    doc["outgoing"][out_id] = {"to": to, "replyTo": reply_to, "kind": kind, "item": item, "createdAt": at,
                               "relayId": None, "failed": False}
    tx.append_event("hub.queued", ref=item, actor="hub", data={"id": out_id, "to": to, "kind": kind})
    return _send_view(g, out_id, doc["outgoing"][out_id])


def _send_view(g: store.Group, out_id: str, entry: dict) -> dict:
    n = out_id.partition(":")[2]
    return {"id": out_id, "to": entry["to"], "bodyFile": str(g.path / "outgoing" / f"{n}.txt"),
            "replyTo": entry["replyTo"], "kind": entry["kind"]}


def _hints(g: store.Group, sender: str, hints) -> list[str]:
    return [f"{_short(g, sender)}：{h.text}" for h in hints]


def _dispatch(g: store.Group, m, at: str) -> tuple[str, list, list[str], dict | None]:
    """Hand one message to its module. Returns (kind, return problems or text, notes, unknown record)."""
    if m.sender == BRIDGE:
        return "bridge", [], [f"agent-relay 通知：{_first_line(m.body)}"], None
    msg = protocol.parse(m.body)
    short = _short(g, m.sender)
    if msg.kind in ("wait-user", "withdraw"):
        r = items.receive(g, m.body, sender=m.sender, relay_id=m.id, received_at=at)
        notes = _hints(g, m.sender, r.hints)
        if msg.kind == "wait-user" and r.accepted:
            notes += _hints(g, m.sender, tickets.receive(g, m.body, sender=m.sender, relay_id=m.id, sent_at=at).hints)
        return msg.kind, [r.return_text] if r.return_text else [], notes, None
    if msg.kind in ("wait-session", "resumed"):
        r = tickets.receive(g, m.body, sender=m.sender, relay_id=m.id, sent_at=at)
        if r.problems:
            return msg.kind, [_return_text(KIND_LABELS[msg.kind], r.problems)], [], None
        if msg.kind == "resumed":
            items.on_resumed(g, msg, sender=m.sender, at=at)
        return msg.kind, [], _hints(g, m.sender, r.hints), None
    if msg.kind == "review-conclusion":
        r = reviews.record_conclusion(g, msg, sender=m.sender, at=at)
        texts = [_return_text(KIND_LABELS[msg.kind], r.problems)] if r.problems else []
        return msg.kind, texts, _hints(g, m.sender, r.hints), None
    if msg.kind == "user-reply":
        return msg.kind, [], [f"{short} 发来一条【用户答复】，收件枢纽不处理"], None
    note = f"{short} 称：{_first_line(m.body)}（说「{m.id} 原文」看全文）"
    return "unknown", [], [note], {"sender": m.sender, "text": m.body, "at": at}


def receive(g: store.Group, inbox, now: str) -> Receipt:
    """Take one bridge_inbox page; each message is recorded as soon as it is handled."""
    result = Receipt(more=inbox.has_more)
    result.notes += list(inbox.warnings)
    for m in inbox.messages:
        if m.truncated:
            result.unread.append(m.id)
            result.notes.append(f"#{m.id} 正文没读全：用 bridge_inbox 把 maxChars 调大（最多 400000）重读后再交")
            continue
        result.ack.append(m.id)
        if str(m.id) in store.read_state(g, DOMAIN).get("received", {}):
            continue
        at = m.created_at or now
        kind, texts, notes, unknown = _dispatch(g, m, at)
        result.notes += list(dict.fromkeys(notes))  # two modules may report the same protocol hint
        with g.transaction() as tx:
            doc = _doc(tx)
            for text in texts:
                result.sends.append(_queue(g, tx, doc, m.sender, text, m.id, "return", None, now))
            if unknown is not None:
                doc["unknown"][str(m.id)] = unknown
            doc["received"][str(m.id)] = {"at": now, "kind": kind, "returned": bool(texts)}
            tx.append_event("hub.received", ref=None, actor=m.sender, data={"relayId": m.id, "kind": kind})
            tx.write_state(DOMAIN, doc)
    if inbox.has_more:
        result.notes.append("还有未读消息：确认已读（bridge_ack）后再读一页")
    return result


class UnknownOutgoing(ValueError):
    """A send id that is not waiting to be sent."""


def _queue_answers(g: store.Group, outgoing, now: str) -> list[dict]:
    """Queue decision-queue's 【用户答复】 texts; only the proposer's copy replies to the item."""
    sends = []
    with g.transaction() as tx:
        doc = _doc(tx)
        for o in outgoing:
            it = items.get(g, o.item)
            reply_to = it["relayId"] if o.to == it["sender"] else None
            sends.append(_queue(g, tx, doc, o.to, o.text, reply_to, "answer", o.item, now))
            if o.to == it["sender"]:
                for to, text in _notices(g, it, now):
                    sends.append(_queue(g, tx, doc, to, text, None, "notice", o.item, now))
        tx.write_state(DOMAIN, doc)
    return sends


def _notices(g: store.Group, it: dict, now: str) -> list[tuple[str, str]]:
    """A single-line item raised by an owner: tell the dev lines it owns (answer-handoff-gaps 已定事项 3)."""
    owner = store.find_session(g, relay_name=it["sender"])
    if it["multi"] or owner is None or owner["role"] != "owner" or not it["answers"]:
        return []
    last = it["answers"][-1]
    text = protocol.format_answer_notice(it["no"], owner["shortName"], last["original"], last["at"],
                                         source_relay_id=it["relayId"])
    return [(e["relayName"], text) for e in store.roster(g)
            if e["role"] == "dev" and set(e["line"]) & set(owner["line"])]


def outgoing(g: store.Group) -> list[dict]:
    """Messages not sent yet: failed ones and ones never reported back."""
    pending = store.read_state(g, DOMAIN).get("outgoing", {})
    ordered = sorted(pending.items(), key=lambda kv: int(kv[0].partition(":")[2]))
    return [_send_view(g, out_id, e) for out_id, e in ordered if e["relayId"] is None]


def sent(g: store.Group, done: dict, failed, at: str) -> tuple[int, ...]:
    """Record what the hub sent (agent-relay ids) or failed to send; then close answered tickets."""
    failed = list(failed)
    recorded = []
    with g.transaction() as tx:
        doc = _doc(tx)
        for out_id in [*done, *failed]:
            entry = doc["outgoing"].get(out_id)
            if entry is None or entry["relayId"] is not None:
                raise UnknownOutgoing(out_id)
        for out_id, relay_id in done.items():
            entry = doc["outgoing"][out_id]
            entry.update(relayId=relay_id, failed=False, sentAt=at)
            tx.append_event("hub.sent", ref=entry["item"], actor="hub", data={"id": out_id, "relayId": relay_id})
            recorded.append((out_id, entry))
        for out_id in failed:
            doc["outgoing"][out_id]["failed"] = True
            tx.append_event("hub.send-failed", ref=doc["outgoing"][out_id]["item"], actor="hub", data={"id": out_id})
        tx.write_state(DOMAIN, doc)
    # Body files stay: nothing in a group is ever deleted (spec/group-store.md 关键决策 5).
    for out_id, entry in recorded:
        if entry["kind"] == "answer":
            items.record_sent(g, entry["item"], to=entry["to"], relay_id=entry["relayId"], at=at)
    return tickets.close_answered(g, at)


@dataclass
class Reply:
    show: str
    sends: list = field(default_factory=list)


def main_view(g: store.Group, now: str, relay=None, maps: dict | None = None, exclude=()) -> str:
    """hub-view's main view, headed by what the hub itself must fix first."""
    head = []
    unsent = [s for s in outgoing(g) if s["id"] not in exclude]
    if unsent:
        head.append(f"⚠ 有 {len(unsent)} 条消息没发出去，说「重发」再试")
    if relay is None:
        head.append("⚠ 读不到 agent-relay，各线状态不全")
    previous = store.read_state(g, "patrol").get("snapshot")
    assessment = health.assess(g, now=now, relay=relay, maps=maps or {}, previous=previous)
    return "\n".join([*head, view.render(g, now, assessment, relay)])


_DETAIL_RE = re.compile(r"^#?(\d+)\s*详情$")
_ORIGINAL_RE = re.compile(r"^#?(\d+)\s*原文$")
_CLOSED_RE = re.compile(r"^看已关闭(?:\s*(\d{4}-\d{2}-\d{2}))?$")
_CLOSE_RE = re.compile(r"^关掉\s*((?:#\s*\d+[\s、，,]*)+)(.*)$", re.S)


def today(now: str) -> str:
    return datetime.fromisoformat(now.replace("Z", "+00:00")).astimezone().date().isoformat()


def _original(g: store.Group, relay_id: str) -> str:
    rec = store.read_state(g, DOMAIN).get("unknown", {}).get(relay_id)
    if rec is None:
        return f"没有记下 #{relay_id} 这条消息的原文（只记认不出类型的消息）"
    return f"{_short(g, rec['sender'])} 发来的 #{relay_id} 原文：\n{rec['text']}"


def _close(g: store.Group, numbers: list[int], reason: str, now: str, relay, maps) -> Reply:
    """「关掉 #编号」: every number must be an open ticket, else nothing is closed."""
    open_ = store.read_state(g, "tickets").get("tickets", {})
    for no in numbers:
        if items.get(g, no) is not None:
            return Reply(f"#{no} 是事项，不是等待单；要放弃事项请让提出方发【撤回】")
        if open_.get(str(no), {}).get("status") != "open":
            return Reply(f"#{no} 不是开着的等待单，请确认编号")
    for no in numbers:
        tickets.close_by_user(g, no, reason or None, now)
    listed = "、".join(f"#{n}" for n in numbers)
    return Reply(f"已关掉 {listed}（{reason or '用户关闭'}）\n\n" + main_view(g, now, relay, maps))


def reply(g: store.Group, text: str, now: str, relay=None, maps: dict | None = None) -> Reply:
    """Everything the user says in the hub, matched as a whole sentence (spec 关键决策 4)."""
    said = text.strip()
    if m := _DETAIL_RE.match(said):
        return Reply(view.render_detail(g, int(m.group(1))))
    if m := _ORIGINAL_RE.match(said):
        return Reply(_original(g, m.group(1)))
    if said == "看等待":
        return Reply(view.render_waits(g, now, relay))
    if m := _CLOSED_RE.match(said):
        return Reply(view.render_closed(g, m.group(1) or today(now)))
    if said == "看失效":
        return Reply(view.render_invalidated(g))
    if m := _CLOSE_RE.match(said):
        numbers = [int(n) for n in re.findall(r"\d+", m.group(1))]
        return _close(g, numbers, m.group(2).strip(), now, relay, maps)
    if said == "重发":
        again = outgoing(g)
        return Reply(f"重新列出 {len(again)} 条没发出去的消息" if again else "没有没发出去的消息", again)
    parsed = items.interpret_reply(g, text)
    if parsed.question:
        return Reply(parsed.question)
    sends = _queue_answers(g, items.answer(g, parsed.answers, answered_at=now), now)
    told = "；".join(_told(g, a.item, [s for s in sends if _item_of(g, s) == a.item]) for a in parsed.answers)
    body = main_view(g, now, relay, maps, exclude={s["id"] for s in sends})
    return Reply(f"已转达：{told}\n\n{body}", sends)


def _told(g: store.Group, item: int, sends: list[dict]) -> str:
    """「#12 → 前端负责人（另告知：前端）」: notices are listed apart from the answers."""
    text = f"#{item} → " + "＋".join(_short(g, s["to"]) for s in sends if s["kind"] == "answer")
    notified = [_short(g, s["to"]) for s in sends if s["kind"] == "notice"]
    return text + (f"（另告知：{'、'.join(notified)}）" if notified else "")


def _item_of(g: store.Group, send: dict):
    return store.read_state(g, DOMAIN)["outgoing"][send["id"]]["item"]


CONVENTION = """<!-- BEGIN decision-inbox hub -->
## decision-inbox 收件枢纽（协作组「{group}」）

你是这个协作组的收件枢纽：替用户收件、整理、转达用户的答复、盯异常。你自己不做决定。
判断和记账都由下面的命令做；你只调用 agent-relay 的工具，并把命令的输出照做或原样显示。

### 被叫醒、或收到 agent-relay 提醒时

1. 用 `bridge_inbox` 读自己的收件箱，把返回的 JSON 原样写入 {io}/inbox.json。
2. 运行 `{cli} inbox receive {group} --inbox {io}/inbox.json`。
3. 输出的 `sends` 逐条用 `bridge_send` 发出：`to` 照填，正文用 `bodyFile` 指向给出的文件（不要自己抄写正文），有 `replyTo` 就照填，不要求回复。
4. 运行 `{cli} inbox sent {group} --done out:N=发出的消息编号 … --failed out:N …`，发成的写在 --done 后，失败的写在 --failed 后。
5. 对输出 `ack` 里的每个编号调用 `bridge_ack`。`unread` 里的消息正文没读全：用 `bridge_inbox` 把 maxChars 调大（最多 400000）重读，再从第 1 步做。
6. 输出 `more` 为真时，从第 1 步再读一页。
7. 用 `bridge_agents` 和 `bridge_outbox`（带 `includeAcknowledged: true`，否则对方已确认的消息不会列出）读状态，分别原样写入 {io}/agents.json 和 {io}/outbox.json，运行
   `{cli} view {group} --agents {io}/agents.json --outbox {io}/outbox.json`，
   把输出的主视图和第 2 步输出的 `notes` 原样显示给用户。

### 用户每说一句话

1. 用 `bridge_agents` 读状态，原样写入 {io}/agents.json。
2. 用写文件工具把用户这句话一字不改地写入 {io}/said.txt。
3. 运行 `{cli} inbox reply {group} --text-file {io}/said.txt --agents {io}/agents.json`。
4. 输出有 `sends` 就按上面第 3、4 步发出并记账。
5. 把输出的 `show` 原样显示给用户。它是一个问题时，等用户回答，不要自己替用户选。

### 改规则

用户说「以后 X 都这样」这类话时，不用上面的命令：先向用户确认收件人（哪几个会话），确认后用 `bridge_send` 把用户原话一字不改地发给这些会话。

### 边界

- 只发命令输出里的消息和上面「改规则」的转发，此外不给任何会话发消息。
- 转述别人的进展要写「X 称」，不能当成事实。
- 宿主弹出的权限确认只能用户去原会话亲手点；你只告诉用户去哪个会话点，不转达、不代批。
- 不替用户决定、不改写选项、不补后果、不合并选项、不审查、不改任何项目的文件。
- 某一步出错：把出错的命令和输出告诉用户，不自己补救，不改协作组的状态文件。
<!-- END decision-inbox hub -->
"""


def convention(group: str, cli: str | None = None, workdir: str | None = None) -> str:
    """The hub session's own convention block; onboarding writes it into place."""
    io = workdir or str(store.root_dir() / group / "io")
    return CONVENTION.format(group=group, cli=cli or install.cli(), io=io)
