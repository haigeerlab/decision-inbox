"""The 待答表: items waiting for the user's decision (see spec/decision-queue.md).

This module only produces texts and recipients; the hub session sends them
through agent-relay and reports the message ids back.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from decision_inbox import protocol, reviews, sources, store
from decision_inbox.protocol import Issue

DOMAIN = "items"
MULTILINE_ROLES = ("coordinator", "owner")
# Scope problems only matter when the sender may raise a multi-line item.
_SCOPE_CODES = ("scope-missing:", "scope-unknown:", "missing-field:各线范围")


@dataclass(frozen=True)
class ReceiveResult:
    handled: bool
    accepted: bool = False
    item: int | None = None
    problems: tuple[Issue, ...] = ()
    hints: tuple[Issue, ...] = ()
    return_text: str | None = None
    superseded: tuple[int, ...] = ()  # explicit and default, for the 【登记回执】 (review-nearby R10)


FINAL = ("superseded", "withdrawn", "closed")


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _not_owner(no, doc: dict | None = None, sender: str | None = None, kind: str = "supersede") -> Issue:
    """A mail id of one's own pending item gets named (p0-field-fixes F-P0-1, rehearsal-fixes); the code stays not-owner."""
    if doc is not None:
        mine = next((k for k, it in doc["items"].items()
                     if it["sender"] == sender and it["relayId"] == no and it["status"] not in FINAL), None)
        if mine is not None and kind == "withdraw":
            return Issue("not-owner", f"#{no} 是邮箱号，对应事项 #{mine}；改写「事项：#{mine}」重发【撤回】")
        if mine is not None:
            return Issue("not-owner", f"#{no} 是邮箱号，对应事项 #{mine}；去掉【取代】靠默认取代，或改写【取代 #{mine}】")
    return Issue("not-owner", f"#{no} 不存在，或不是你抛出的事项")


def _owned(doc: dict, no, sender: str) -> dict | None:
    it = doc["items"].get(str(no)) if no is not None else None
    return it if it is not None and it["sender"] == sender and it["status"] not in FINAL else None


def _resolve_own(doc: dict, no, sender: str, legacy: bool) -> int | None:
    """The sender's own open item that `no` names: the hub's number, or for a line not migrated
    yet its own message id, which is what the old hand-written hub echoed (transition-compat)."""
    if _owned(doc, no, sender) is not None:
        return int(no)
    if legacy and no is not None:
        return next((int(k) for k, it in doc["items"].items()
                     if it["sender"] == sender and it["relayId"] == no and it["status"] not in FINAL), None)
    return None


def _label(it: dict, no: int, legacy: bool) -> str:
    """How an item is named back to its sender: old lines know their message id first."""
    return f"#{it['relayId']}（hub 编号 {no}）" if legacy and it.get("relayId") is not None else f"#{no}"


def _doc(tx) -> dict:
    doc = tx.read_state(DOMAIN)
    doc.setdefault("items", {})
    return doc


def _return_text(problems) -> str:
    lines = ["退回：你的【等待用户】没有收进待答表，原因："]
    lines += [f"- {p.text}" for p in problems]
    lines.append("请补全后重新抛出。")
    return "\n".join(lines)


_ITEM_REF_RE = re.compile(r"#\d+")
_LETTER_ONLY_RE = re.compile(r"^(\d+\s+)?[A-Za-z]$")
_ADVICE_RE = re.compile(r"^通过，附建议\d+条（(.*)）$")


def writing_notes(msg) -> list[tuple[str, str]]:
    """Loose writing in a 【等待用户】, for the user's eyes only (rehearsal2-fixes, user's choice A).

    Plugin-local on purpose: these are not session-protocol hint codes and change no parse result.
    """
    fields, out = msg.fields, []
    if not fields.get("项目", "").strip():
        out.append(("missing-project", "缺「项目：」"))
    if _LETTER_ONLY_RE.match(fields.get("你该回", "").strip()):
        out.append(("reply-letter-only", "「你该回」只写了选项字母，没写完整回复原文"))
    review = msg.review
    if review.status == "passed-with-advice" and review.advice_count:
        value = review.raw.strip().replace(",", "，").replace("(", "（").replace(")", "）")
        if review.ref is not None:
            value = protocol._REVIEW_REF_RE.sub("", value).rstrip()
        hit = _ADVICE_RE.match(value)
        if hit is None or not hit.group(1).strip():
            out.append(("review-empty-advice", "「架构审查」写了附建议，括号里没写建议内容"))
    refs = set(_ITEM_REF_RE.findall(fields.get("要你决定", "")))
    lines = [x for x in fields.get("要点", "").splitlines() if x.strip()]
    if len(refs) >= 2 and len(lines) < 2 * len(refs):
        out.append(("brief-thin-batch", f"一次要决定 {len(refs)} 项，要点只有 {len(lines)} 行"))
    return out


def _approval_key(msg) -> tuple[str | None, str | None]:
    """Module and node from the 交审原文 when readable, else the 产物 module prefix (approval-display)."""
    module = node = None
    for ref in msg.originals.get("submission", ()):
        got = sources.read_original(ref.path, ref.fingerprint)
        if got.ok:
            module, node = sources.submission_meta(got.text)
            break
    if module is None:
        module = next((a.module for a in msg.artifacts if a.module), None)
    return module, node


def _record(msg, sender: str, relay_id, received_at: str, multi: bool, label) -> dict:
    return {
        "sender": sender,
        "relayId": relay_id,
        "receivedAt": received_at,
        "text": None,
        "from": msg.fields.get("来自", "").strip(),
        "decide": msg.fields.get("要你决定", "").strip(),
        "brief": msg.fields.get("要点", "").strip("\n"),
        "options": [{"letter": o.letter, "text": o.text, "consequence": o.consequence} for o in msg.options],
        "recommended": msg.recommended,
        "suggestedReply": msg.suggested_reply,
        "fullyStopped": msg.fully_stopped,
        "multi": multi,
        "lines": list(msg.lines_in_scope) if multi else [],
        "scopes": dict(msg.scopes) if multi else {},
        "ends": {"ids": list(msg.ends.ids), "none": msg.ends.none},
        "review": {"text": label.text, "warn": label.warn, "highlight": label.highlight, "ref": label.ref,
                   "mentions": list(label.mentions)},
        "writingNotes": [text for _, text in writing_notes(msg)],
        "decisions": [{"id": d.id, "question": d.question, "options": [list(o) for o in d.options],
                       "lean": d.lean, "leanReason": d.lean_reason} for d in msg.decisions],
        # approval-display: what to read verbatim; module and node as the submission states them
        "project": msg.fields.get("项目", "").strip(),
        "artifacts": [{"module": a.module, "path": a.path, "commit": a.commit, "previous": a.previous}
                      for a in msg.artifacts],
        "originals": {kind: [{"module": r.module, "path": r.path, "fingerprint": r.fingerprint} for r in refs]
                      for kind, refs in msg.originals.items()},
        **dict(zip(("approvalModule", "approvalNode"), _approval_key(msg))),
        "status": "pending",
        "statusAt": {"pending": received_at},
        "answers": [],
        "recipients": [],
        "sent": [],
    }


def _receive_wait_user(g, msg, text, sender, relay_id, received_at) -> ReceiveResult:
    entry = store.find_session(g, relay_name=sender) or {}
    problems = list(msg.problems)
    hints = list(msg.hints)
    multi = bool(msg.lines_in_scope)
    if multi and entry.get("role") not in MULTILINE_ROLES:
        multi = False
        problems = [p for p in problems if not p.code.startswith(_SCOPE_CODES)]
        hints.append(Issue("multiline-not-allowed", "只有总协调和负责人能抛多线事项，已按普通事项处理"))
    if multi:
        left = store.left_relays(g)
        for name in msg.lines_in_scope:
            named = store.find_session(g, short_name=name)
            if named is None or named["relayName"] in left:
                problems.append(Issue(f"scope-session-unknown:{name}", f"适用会话里的 {name} 不在会话名册里"))
    legacy = sender in store.legacy_relays(g)
    with g.transaction() as tx:
        doc = _doc(tx)
        superseded = []
        for kind, no in msg.markers:
            if kind == "supersede":
                own = _resolve_own(doc, no, sender, legacy)
                if own is None:
                    problems.append(_not_owner(no, doc, sender))
                else:
                    superseded.append(own)
        if problems:
            tx.append_event("items.returned", ref=None, actor=sender,
                            data={"relayId": relay_id, "codes": [p.code for p in problems]})
            tx.write_state(DOMAIN, doc)
            return ReceiveResult(True, False, None, tuple(problems), tuple(hints), _return_text(problems))
        auto = []
        if not msg.markers:
            # No 【取代】 or 【并行】: this session's unanswered item of the same kind is
            # replaced by default (wait-honesty-and-briefs A7).
            auto = sorted(int(k) for k, it in doc["items"].items()
                          if it["sender"] == sender and it["status"] == "pending" and it["multi"] == multi)
            for old in auto:
                it = doc["items"][str(old)]
                ref = f"#{it['relayId']}" if legacy and it.get("relayId") is not None else f"#{old}"
                hints.append(Issue("auto-superseded", f"{_label(it, old, legacy)} 已被新事项自动取代；"
                                                      f"确实要两项都答，请写【与 {ref} 并行】重发"))
        no = tx.allocate_number()
        label = reviews.display_label(g, session=sender, message=msg, received_at=received_at)
        record = _record(msg, sender, relay_id, received_at, multi, label)
        record["text"] = text
        record["markers"] = [list(m) for m in msg.markers]
        doc["items"][str(no)] = record
        tx.append_event("items.received", ref=no, actor=sender, data={"relayId": relay_id})
        for old in superseded:
            _set_status(doc, old, "superseded", received_at)
            tx.append_event("items.superseded", ref=old, actor=sender, data={"by": no})
        for old in auto:
            _set_status(doc, old, "superseded", received_at)
            tx.append_event("items.superseded", ref=old, actor=sender, data={"by": no, "auto": True})
        tx.write_state(DOMAIN, doc)
    return ReceiveResult(True, True, no, (), tuple(hints), superseded=tuple(superseded + auto))


def _set_status(doc: dict, no, status: str, at: str) -> None:
    it = doc["items"][str(no)]
    it["status"] = status
    it["statusAt"][status] = at


def _receive_withdraw(g, msg, sender, relay_id, received_at) -> ReceiveResult:
    problems = list(msg.problems)
    legacy = sender in store.legacy_relays(g)
    with g.transaction() as tx:
        doc = _doc(tx)
        own = None if problems else _resolve_own(doc, msg.item, sender, legacy)
        if not problems and own is None:
            problems.append(_not_owner(msg.item, doc, sender, kind="withdraw"))
        if problems:
            tx.append_event("items.returned", ref=None, actor=sender,
                            data={"relayId": relay_id, "codes": [p.code for p in problems]})
            tx.write_state(DOMAIN, doc)
            return ReceiveResult(True, False, None, tuple(problems), (), _return_text(problems))
        _set_status(doc, own, "withdrawn", received_at)
        tx.append_event("items.withdrawn", ref=own, actor=sender,
                        data={"relayId": relay_id, "reason": msg.fields.get("原因", "").strip()})
        tx.write_state(DOMAIN, doc)
    return ReceiveResult(True, True, own)


def _blocks(it: dict) -> int:
    """How many lines the item holds up (spec 关键决策 3)."""
    if it["multi"]:
        return len(it["lines"])
    return 1 if it["fullyStopped"] else 0


def pending(g: store.Group) -> list[dict]:
    """Items waiting for the user: most lines held up first, then oldest first."""
    found = []
    for key, it in store.read_state(g, DOMAIN).get("items", {}).items():
        if it["status"] == "pending":
            found.append(dict(it, no=int(key), blocks=_blocks(it)))
    return sorted(found, key=lambda it: (-it["blocks"], _instant(it["receivedAt"])))


def get(g: store.Group, item: int) -> dict | None:
    it = store.read_state(g, DOMAIN).get("items", {}).get(str(item))
    return None if it is None else dict(it, no=int(item))


def by_status(g: store.Group, *statuses: str) -> list[dict]:
    """Items in any of `statuses`, by number (hub-view's detail, recent and invalidated views)."""
    found = [dict(it, no=int(key)) for key, it in store.read_state(g, DOMAIN).get("items", {}).items()
             if it["status"] in statuses]
    return sorted(found, key=lambda it: it["no"])


@dataclass(frozen=True)
class Answer:
    item: int
    letter: str | None
    original: str
    decisions: tuple[tuple[str, str], ...] = ()  # (D-number, letter) for 「待用户决定」 (review-nearby R2)


@dataclass(frozen=True)
class ReplyParse:
    answers: tuple[Answer, ...] = ()
    question: str | None = None


# A digit run glued to lowercase letters is a commit hash, not an item (review-nearby R6); 「12B」 still is one.
_SEGMENT_RE = re.compile(r"^\s*#?(\d+)(?![0-9a-z])\s*(.*)$", re.S)
# The option letter may be followed by punctuation: 「21 B，C15 退回」 (review-nearby R6).
_LETTER_RE = re.compile(r"^([A-Z])(?:[\s，；,;、：:].*)?$", re.S)
_SPLIT_RE = re.compile(r"[，；;,]")
# session-protocol v2.0 section 2: C (coordinator), R (review) and D (decision) numbers are never items.
_PREFIXED_RE = re.compile(r"^\s*#?(?:[CD]\d+|R-?\d+)(?![A-Za-z0-9])")
ANSWERED = ("forwarded", "picked", "acknowledged")


def _segments(text: str, known: dict) -> list[str]:
    """Split only when every piece starts with an existing item number (spec 关键决策 4)."""
    def numbered(piece: str) -> bool:
        m = _SEGMENT_RE.match(piece)
        return bool(m) and m.group(1) in known

    def grouped(pieces: list[str], seps: list[str]) -> list[str] | None:
        """Numbered pieces, each carrying the prefixed pieces after it (「21 B，C15 退回」 is one answer)."""
        if not numbered(pieces[0]) or not all(numbered(x) or _PREFIXED_RE.match(x) for x in pieces):
            return None
        out = [pieces[0]]
        for sep, piece in zip(seps, pieces[1:]):
            if numbered(piece):
                out.append(piece)
            else:
                out[-1] += sep + piece
        return out

    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if len(lines) > 1:
        return grouped(lines, ["\n"] * len(lines)) or [text]
    pieces = [x.strip() for x in _SPLIT_RE.split(text)]
    if len(pieces) > 1 and all(pieces):
        out = grouped(pieces, _SPLIT_RE.findall(text))
        if out is not None and len(out) > 1:
            return out
    return [text]


_DECISION_ANSWER_RE = re.compile(r"(?<![A-Za-z0-9])(D\d+)\s*(?:[：:]|选)?\s*([A-Z])(?![A-Za-z])")


def _decision_answers(key: str, it: dict, letter: str | None, segment: str):
    """The D answers of one segment, or the question to ask when any is missing or wrong (session-protocol v2.0 §8).

    Nothing is filled from the reviewer's lean: it only appears in the example of how to write it.
    """
    asked = {d["id"]: d for d in it["decisions"]}
    given: dict[str, set[str]] = {}
    for d_id, picked in _DECISION_ANSWER_RE.findall(segment):
        given.setdefault(d_id, set()).add(picked)
    gaps = []
    if letter is None:
        gaps.append("主选项（" + "／".join(o["letter"] for o in it["options"]) + "）没答")
    for d_id, picks in given.items():
        d = asked.get(d_id)
        if d is None:
            gaps.append(f"没有 {d_id}")
        elif len(picks) > 1:
            gaps.append(f"{d_id} 答了两个不同的选项")
        elif not picks <= {o[0] for o in d["options"]}:
            gaps.append(f"{d_id} 没有选项 {next(iter(picks))}")
    for d_id, d in asked.items():
        if d_id not in given:
            choices = "／".join(f"{o[0]}. {o[1]}" for o in d["options"])
            gaps.append(f"没答 {d_id} {d['question']}（{choices}）")
    if not gaps:
        return tuple((d_id, next(iter(given[d_id]))) for d_id in asked), None
    good = {d_id: next(iter(p)) for d_id, p in given.items()
            if d_id in asked and len(p) == 1 and p <= {o[0] for o in asked[d_id]["options"]}}
    main = letter or it.get("recommended") or it["options"][0]["letter"]
    example = "；".join([f"{key} {main}"] + [f"{d_id} {good.get(d_id) or d['lean'] or d['options'][0][0]}"
                                             for d_id, d in asked.items()])
    return (), (f"#{key} 还没答全：{'；'.join(gaps)}。请把主选项和每个待你决定的问题写在同一条回复里重发，"
                f"例如「{example}」（这只是写法示例，不是默认答案）。")


NO_ITEM_QUESTION = "没看出这句是答哪一项的，请在开头写上编号，例如「12 B」。"


def interpret_reply(g: store.Group, text: str) -> ReplyParse:
    """The user's reply as answers, or a question when anything does not match (requirement 6.4)."""
    text = text.strip()
    known = store.read_state(g, DOMAIN).get("items", {})
    waiting = [k for k, it in known.items() if it["status"] == "pending"]
    answers: list[Answer] = []
    for segment in _segments(text, known):
        m = _SEGMENT_RE.match(segment)
        if m:
            key, rest = m.group(1), m.group(2).strip()
        elif len(waiting) == 1:
            key, rest = waiting[0], segment
        else:
            return ReplyParse(question=NO_ITEM_QUESTION)
        it = known.get(key)
        if it is None:
            return ReplyParse(question=f"#{key} 不在待答表里，请确认编号。")
        if it["status"] in ANSWERED:
            return ReplyParse(question=f"#{key} 已经转达过，要改答复请先说明以哪次为准。")
        if it["status"] != "pending":
            return ReplyParse(question=f"#{key} 已经不在待答状态（已失效或已结束），请确认。")
        letter = None
        lm = _LETTER_RE.match(rest) if m else None
        if lm:
            letter = lm.group(1)
            if letter not in {o["letter"] for o in it["options"]}:
                return ReplyParse(question=f"#{key} 没有选项 {letter}，请确认。")
        picked = ()
        if it.get("decisions"):
            picked, question = _decision_answers(key, it, letter, segment)
            if question:
                return ReplyParse(question=question)
        answer = Answer(int(key), letter, segment, picked)
        same = [a for a in answers if a.item == answer.item]
        if same and (same[0].letter != letter or (letter is None and same[0].original != segment)):
            return ReplyParse(question=f"#{key} 这次回复里有两个不同的答复，请说明以哪个为准。")
        if not same:
            answers.append(answer)
    return ReplyParse(answers=tuple(answers))


@dataclass(frozen=True)
class Outgoing:
    to: str
    text: str
    item: int


def answer(g: store.Group, answers, answered_at: str) -> tuple[Outgoing, ...]:
    """Record the user's answers and build the 【用户答复】 texts; the hub sends them."""
    out: list[Outgoing] = []
    legacy, left = store.legacy_relays(g), store.left_relays(g)
    with g.transaction() as tx:
        doc = _doc(tx)
        for a in answers:
            it = doc["items"].get(str(a.item))
            if it is None or it["status"] != "pending":
                raise ValueError(f"#{a.item} is not waiting for an answer")
            option = next((o for o in it["options"] if o["letter"] == a.letter), None)
            option_text = f"{option['letter']}：{option['text']}" if option else None
            batch = [Outgoing(it["sender"], protocol.format_user_reply(
                item=a.item, original=a.original, answered_at=answered_at, option_text=option_text,
                source_relay_id=it["relayId"]), a.item)]
            if it["sender"] in legacy and it["relayId"] is not None:
                batch[0] = Outgoing(batch[0].to, protocol.legacy_head(batch[0].text, a.item, it["relayId"]), a.item)
            if it["multi"]:
                sender = (store.find_session(g, relay_name=it["sender"]) or {}).get("shortName", it["sender"])
                texts = protocol.format_multiline_replies(item=a.item, sender=sender, original=a.original,
                                                          answered_at=answered_at, wait_user_text=it["text"],
                                                          source_relay_id=it["relayId"])
                for short, text in texts.items():
                    to = store.find_session(g, short_name=short)["relayName"]
                    if to in left:
                        continue
                    if to in legacy and it["relayId"] is not None:
                        text = protocol.legacy_head(text, a.item, it["relayId"], multi_sender=it["sender"])
                    batch.append(Outgoing(to, text, a.item))
            it["answers"].append({"letter": a.letter, "original": a.original, "at": answered_at,
                                  "decisions": [list(d) for d in a.decisions]})
            it["recipients"] = [o.to for o in batch]
            _set_status(doc, a.item, "forwarded", answered_at)
            tx.append_event("items.answered", ref=a.item, actor="user",
                            data={"letter": a.letter, "original": a.original, "recipients": it["recipients"],
                                  "decisions": [list(d) for d in a.decisions]})
            out += batch
        tx.write_state(DOMAIN, doc)
    return tuple(out)


PROGRESS = ("forwarded", "picked", "acknowledged")


def record_sent(g: store.Group, item: int, to: str, relay_id, at: str) -> None:
    """Remember the agent-relay id of a reply the hub sent, so /item can prove who sent it."""
    with g.transaction() as tx:
        doc = _doc(tx)
        doc["items"][str(item)]["sent"].append({"to": to, "relayId": relay_id, "at": at,
                                                "state": None, "ackAt": None})
        tx.append_event("items.sent", ref=item, actor="hub", data={"to": to, "relayId": relay_id})
        tx.write_state(DOMAIN, doc)


def _progress(it: dict) -> str:
    """The slowest recipient decides (spec 假设 2)."""
    level = {}
    for sent in it["sent"]:
        level[sent["to"]] = 2 if sent["ackAt"] else 1 if sent["state"] == "accepted" else 0
    return PROGRESS[min(level.get(r, 0) for r in it["recipients"])] if it["recipients"] else "forwarded"


def update_delivery(g: store.Group, facts: dict, at: str) -> None:
    """facts: agent-relay message id -> (deliveryState, acknowledgedAt). Status only moves forward."""
    with g.transaction() as tx:
        doc = _doc(tx)
        for key, it in doc["items"].items():
            if it["status"] not in PROGRESS:
                continue
            for sent in it["sent"]:
                if sent["relayId"] in facts:
                    sent["state"], sent["ackAt"] = facts[sent["relayId"]]
            new = _progress(it)
            if PROGRESS.index(new) > PROGRESS.index(it["status"]):
                _set_status(doc, key, new, at)
                tx.append_event("items.delivery", ref=int(key), actor="relay", data={"status": new})
        tx.write_state(DOMAIN, doc)


def on_resumed(g: store.Group, message, sender: str, at: str) -> tuple[int, ...]:
    """【已恢复】 from the proposer closes its own answered items named in 结束."""
    closed = []
    with g.transaction() as tx:
        doc = _doc(tx)
        for written in message.ends.ids:
            no = written
            if str(no) not in doc["items"]:  # the proposer's own message id (e2e-round1-fixes F10)
                no = next((int(k) for k, it in doc["items"].items()
                           if it["relayId"] == written and it["sender"] == sender), written)
            it = doc["items"].get(str(no))
            if it is not None and it["sender"] == sender and it["status"] in PROGRESS:
                _set_status(doc, no, "closed", at)
                tx.append_event("items.closed", ref=no, actor=sender, data={})
                closed.append(no)
        tx.write_state(DOMAIN, doc)
    return tuple(closed)


def history(g: store.Group, item: int) -> list[dict]:
    return [e for e in store.read_events(g, ref=item) if str(e.get("type", "")).startswith("items.")]


def receive(g: store.Group, text: str, sender: str, relay_id, received_at: str) -> ReceiveResult:
    """Take one incoming message; only 【等待用户】 and 【撤回】 belong here."""
    msg = protocol.parse(text)
    if msg.kind == "wait-user":
        return _receive_wait_user(g, msg, text, sender, relay_id, received_at)
    if msg.kind == "withdraw":
        return _receive_withdraw(g, msg, sender, relay_id, received_at)
    return ReceiveResult(False)
