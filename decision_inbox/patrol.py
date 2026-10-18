"""Patrol: decide wakes, owner alerts and user notices; remember what was done (see spec/patrol.md).

`plan` is read-only and returns the actions for the scheduled task session to
carry out; `record` is the only writer of the `patrol` domain. Every "only
once" rule is kept in that domain, so catch-up runs never repeat an action.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from decision_inbox import health, install, items, stall, store, view

DOMAIN = "patrol"
OFFLINE = ("offline", "unreachable")
PROGRESS_SIGNALS = (3, 6, 7, 8, 9)
HUB_REMINDER_MINUTES = 30  # spec 已定事项 5
NOTICES_PER_ROUND = 3      # spec 关键决策 5
WAKE_GRACE_MINUTES = 5     # one patrol interval before a wake counts as failed (spec 关键决策 3)
IDLE_WAKE_MINUTES = 3      # an idle session's mail this old means agent-relay's own ping did not take (stall-and-patrol R19)
OFFLINE_MAIL_MINUTES = 3   # the hub's mail agent-relay could not deliver for "offline" this long (R19)
SNAPSHOTS = 24             # raw agents/outbox kept per kind, so a missed wake can be traced (R19)
DESKTOP_LINK = "claude://claude.ai/epitaxy/{session}"


@dataclass(frozen=True)
class Action:
    id: str
    kind: str            # wake | owner-alert | notify
    target: str | None   # desktopSession for wake, owner relay name for owner-alert, None for notify
    text: str


@dataclass
class Plan:
    now: str
    actions: list = field(default_factory=list)
    snapshot: dict = field(default_factory=dict)
    live: dict = field(default_factory=lambda: {"signals": [], "wakes": [], "notices": []})
    merged: list = field(default_factory=list)   # notice keys folded into notify:more
    by: str = "schedule"                          # hub-patrol: "hub" when the hub ran the round itself

    def to_json(self) -> dict:
        return {"version": 1, "now": self.now, "by": self.by,
                "actions": [a.__dict__ for a in self.actions],
                "snapshot": self.snapshot, "live": self.live, "merged": self.merged}


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def signal_key(signal) -> str:
    return "|".join([str(signal.no), *signal.sessions])


def notice_text(text: str) -> str:
    """Desktop notification wording (spec 关键决策 5)."""
    return f"decision-inbox：{text}，详见决策收件箱"


@dataclass
class _Context:
    g: store.Group
    now: str
    relay: object | None
    state: dict
    plan: Plan
    from_hub: bool = False
    outbox: object | None = None

    def notify(self, key: str, text: str) -> None:
        """Queue a user notice once per live episode of `key`."""
        self.plan.live["notices"].append(key)
        if key not in self.state.get("notices", {}):
            self.plan.actions.append(Action(f"notify:{key}", "notify", None, notice_text(text)))


def _fact(ctx: _Context, name: str):
    return ctx.relay.agents.get(name) if ctx.relay is not None else None


def _wake(ctx: _Context, entry: dict, text: str, stopped: bool = True) -> None:
    """Wake a Claude session once per backlog episode; tell the user if that did not help."""
    name, short = entry["relayName"], entry["shortName"]
    if name in ctx.plan.live["wakes"]:
        return  # already handled this round (a stuck answer wakes the owner first)
    ctx.plan.live["wakes"].append(name)
    if not entry.get("desktopSession"):
        ctx.notify(f"unwakeable:{name}", f"{short} 停着，名册里没登记它的桌面版会话，叫不醒，请手动打开")
        return
    tried = ctx.state.get("wakes", {}).get(name)
    if tried is None:
        ctx.plan.actions.append(Action(f"wake:{name}", "wake", entry["desktopSession"], text))
    elif (_instant(ctx.now) - _instant(tried["at"])).total_seconds() >= WAKE_GRACE_MINUTES * 60:
        still = "它还停着" if stopped else "它的消息还没读"
        link = DESKTOP_LINK.format(session=entry["desktopSession"])
        ctx.notify(f"unwakeable:{name}", f"叫不醒 {short}，{still}，请手动打开 {link}（来源：Claude 桌面版）")


def _idle_backlog(ctx: _Context, fact) -> bool:
    """Idle with mail older than IDLE_WAKE_MINUTES (p0-field-fixes F-P0-2)."""
    if fact.activity != "idle" or not fact.waiting_oldest_at:
        return False
    return (_instant(ctx.now) - _instant(fact.waiting_oldest_at)).total_seconds() >= IDLE_WAKE_MINUTES * 60


def _wakes(ctx: _Context) -> None:
    """Spec 关键决策 3: Claude sessions with messages waiting, stopped or idle too long; the hub too (F-P0-3)."""
    for entry in store.roster(ctx.g):
        fact = _fact(ctx, entry["relayName"])
        if entry["host"] != "claude-desktop" or fact is None or not fact.waiting_count:
            continue
        if ctx.from_hub and entry["role"] == "hub":
            continue  # the hub is the one running this round
        stopped = fact.presence in OFFLINE
        if stopped or _idle_backlog(ctx, fact):
            _wake(ctx, entry, f"【decision-inbox 巡视】你有 {fact.waiting_count} 条消息在等，请查看收件箱后继续。",
                  stopped=stopped)


def _offline_mail(ctx: _Context) -> None:
    """R19: mail the hub sent that agent-relay holds as "offline" for OFFLINE_MAIL_MINUTES wakes its Claude
    recipient over the desktop channel, whatever its presence says (#6811 slipped past presence)."""
    if ctx.outbox is None:
        return
    for name in dict.fromkeys(m.recipient for m in ctx.outbox.messages
                              if m.wake_pending == "offline" and not m.acknowledged_at and m.sent_at
                              and (_instant(ctx.now) - _instant(m.sent_at)).total_seconds()
                              >= OFFLINE_MAIL_MINUTES * 60):
        entry = store.find_session(ctx.g, relay_name=name)
        if entry is None or entry["host"] != "claude-desktop" or name in store.left_relays(ctx.g):
            continue
        if ctx.from_hub and entry["role"] == "hub":
            continue
        _wake(ctx, entry, "【decision-inbox 巡视】有消息送不进来（agent-relay 叫不醒你），请查看收件箱后继续。")


def _not_loaded(ctx: _Context) -> None:
    """R19: a Codex task that is not loaded cannot be woken from here; tell the user to open it."""
    for entry in store.roster(ctx.g):
        fact = _fact(ctx, entry["relayName"])
        if (entry["host"] == "codex-desktop" and fact is not None and fact.waiting_count
                and getattr(fact, "presence_raw", None) == "not-loaded"):
            ctx.plan.live["wakes"].append(entry["relayName"])
            ctx.notify(f"not-loaded:{entry['relayName']}",
                       f"{entry['shortName']} 有 {fact.waiting_count} 条消息没读，Codex 任务没打开：去 Codex 打开 "
                       f"{entry['shortName']} 的任务")


def save_snapshot(group: str, now: str, raw: dict) -> None:
    """Keep this round's raw agents/outbox (R19), only the latest SNAPSHOTS of each kind."""
    folder = store.root_dir() / group / "io" / "snapshots"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = now.replace(":", "").replace("+", "p")
    for kind, text in raw.items():
        if text is None:
            continue
        (folder / f"{stamp}-{kind}.json").write_text(text, encoding="utf-8")
        for old in sorted(folder.glob(f"*-{kind}.json"))[:-SNAPSHOTS]:
            old.unlink()


def _wake_hub(ctx: _Context) -> None:
    """Spec 关键决策 3: wake the hub too when the user is about to be notified and it is stopped."""
    if ctx.from_hub:
        return
    hub = next((e for e in store.roster(ctx.g) if e["role"] == "hub"), None)
    fact = _fact(ctx, hub["relayName"]) if hub else None
    if hub is None or fact is None or fact.presence not in OFFLINE or hub["relayName"] in ctx.plan.live["wakes"]:
        return
    if not any(a.kind == "notify" for a in ctx.plan.actions) and hub["relayName"] not in ctx.state.get("wakes", {}):
        return
    ctx.plan.live["wakes"].append(hub["relayName"])
    if hub.get("desktopSession") and hub["relayName"] not in ctx.state.get("wakes", {}):
        ctx.plan.actions.append(Action(f"wake:{hub['relayName']}", "wake", hub["desktopSession"],
                                       "【decision-inbox 巡视】有新的事要告诉用户，请刷新决策收件箱主视图。"))


def _owner(g: store.Group, session: str) -> dict | None:
    """The first owner on the roster whose lines include this session's line (spec 关键决策 4)."""
    entry = store.find_session(g, relay_name=session)
    lines = set(entry.get("line", [])) if entry else set()
    return next((e for e in store.roster(g) if e["role"] == "owner" and lines & set(e["line"])), None)


def _alerts(ctx: _Context, signals) -> None:
    """Progress signals: owner first, the user after ESCALATE_MINUTES or when no owner can take it."""
    for signal in signals:
        if signal.no not in PROGRESS_SIGNALS or not signal.sessions:
            continue
        key = signal_key(signal)
        short = (store.find_session(ctx.g, relay_name=signal.sessions[0]) or {}).get("shortName", signal.sessions[0])
        seen = ctx.state.get("signals", {}).get(key, {})
        owner = _owner(ctx.g, signal.sessions[0])
        owner_fact = _fact(ctx, owner["relayName"]) if owner else None
        if owner is None or (owner_fact is not None and owner_fact.presence in OFFLINE) or seen.get("alertFailed"):
            ctx.notify(f"signal:{key}", f"{short}：{signal.text}")
        elif "alertedAt" not in seen:
            text = f"【进度预警】{short}：{signal.text}。建议：{view.advice(ctx.g, signal)}"
            ctx.plan.actions.append(Action(f"alert:{key}", "owner-alert", owner["relayName"], text))
        elif (_instant(ctx.now) - _instant(seen["alertedAt"])).total_seconds() >= health.ESCALATE_MINUTES * 60:
            ctx.notify(f"escalate:{key}", f"{short}：{signal.text}；审查者 {health.ESCALATE_MINUTES} 分钟没处理")


def _handoffs(ctx: _Context) -> None:
    """answer-handoff-gaps 已定事项 2: an answer queued for an offline owner wakes it and tells the user now."""
    for it in items.by_status(ctx.g, "forwarded"):
        for name in it["recipients"]:
            entry = store.find_session(ctx.g, relay_name=name)
            fact = _fact(ctx, name)
            if entry is None or entry["role"] != "owner" or fact is None or fact.presence not in OFFLINE:
                continue
            blocks = items._blocks(it)
            held = f"，挡住 {blocks} 条线" if blocks else ""
            ctx.notify(f"handoff:{it['no']}|{name}", f"#{it['no']} 的答复卡在离线的{entry['shortName']}{held}")
            if entry.get("desktopSession"):
                _wake(ctx, entry, f"【decision-inbox 巡视】用户对 #{it['no']} 的答复在等你取走并转交，请查看收件箱。")


def _user_notices(ctx: _Context, signals, relay_error: str | None) -> None:
    """Signal 1, items holding lines up too long, and an unreadable agent-relay (spec 已定事项 5, 关键决策 5)."""
    for signal in signals:
        if signal.no == 1:
            ctx.notify("all-waiting", signal.text)
        elif signal.no == 11:  # one notice per batch of doubtful ids (relay-presence-and-doubt)
            short = (store.find_session(ctx.g, relay_name=signal.sessions[0]) or {}).get("shortName", signal.sessions[0])
            ctx.notify(f"doubt:{signal.sessions[0]}:{signal.text}",
                       f"{signal.text}。完全退出 ChatGPT 再打开 {short} 的任务")
    for it in items.pending(ctx.g):
        waited = (_instant(ctx.now) - _instant(it["receivedAt"])).total_seconds() / 60
        if it["blocks"] and waited >= HUB_REMINDER_MINUTES:
            topic = it["decide"].splitlines()[0]
            ctx.notify(f"item:{it['no']}", f"#{it['no']}「{topic}」已等 {int(waited)} 分钟，挡住 {it['blocks']} 条线")
    if relay_error:
        ctx.notify("relay-unreadable", "巡视读不到 agent-relay 的状态（来源：agent-relay）")


def _cap(ctx: _Context) -> None:
    """At most NOTICES_PER_ROUND notices; the rest fold into one, recorded as told when it is sent."""
    notices = [a for a in ctx.plan.actions if a.kind == "notify"]
    if len(notices) <= NOTICES_PER_ROUND:
        return
    keep, rest = notices[:NOTICES_PER_ROUND - 1], notices[NOTICES_PER_ROUND - 1:]
    ctx.plan.actions = [a for a in ctx.plan.actions if a.kind != "notify" or a in keep]
    ctx.plan.merged = [a.id.partition(":")[2] for a in rest]
    ctx.plan.actions.append(Action("notify:more", "notify", None, notice_text(f"还有 {len(rest)} 件事")))


def plan(g: store.Group, now: str, relay=None, maps: dict | None = None,
         relay_error: str | None = None, from_hub: bool = False, crews: dict | None = None,
         outbox=None) -> Plan:
    """Read-only: what this round should do (spec 关键决策 1)."""
    state = store.read_state(g, DOMAIN)
    assessment = health.assess(g, now=now, relay=relay, maps=maps or {}, previous=state.get("snapshot"),
                               crews=crews)
    result = Plan(now=now, snapshot=assessment.snapshot, by="hub" if from_hub else "schedule")
    result.live["signals"] = sorted({signal_key(s) for s in assessment.signals})
    ctx = _Context(g, now, relay, state, result, from_hub, outbox)
    _handoffs(ctx)  # first, so its notices lead the round and survive the cap
    _user_notices(ctx, assessment.signals, relay_error)
    _wakes(ctx)
    _offline_mail(ctx)
    _not_loaded(ctx)
    for ask in stall.asks(g, now, assessment.lines, maps or {}, state):  # R14: the line raises it itself
        result.actions.append(Action(f"stall:{ask.key}", ask.kind, ask.target, ask.text))
    _alerts(ctx, assessment.signals)
    _cap(ctx)
    _wake_hub(ctx)
    return result


def record(g: store.Group, plan_doc: dict, done=(), failed=(), now: str | None = None) -> None:
    """The only writer of the patrol domain: outcomes of this round, then forget what is no longer live."""
    done, failed = list(done), list(failed)
    at = plan_doc["now"]
    live = plan_doc["live"]
    with g.transaction() as tx:
        state = tx.read_state(DOMAIN)
        signals = {k: v for k, v in state.get("signals", {}).items() if k in live["signals"]}
        for key in live["signals"]:
            signals.setdefault(key, {"firstSeen": at})
        wakes = {k: v for k, v in state.get("wakes", {}).items() if k in live["wakes"]}
        notices = {k: v for k, v in state.get("notices", {}).items() if k in live["notices"]}
        keep_hours = stall.settings(g)["askAgainHours"]
        stall_asks = {k: v for k, v in state.get("stallAsks", {}).items()
                      if (_instant(at) - _instant(v)).total_seconds() < keep_hours * 3600}
        for action_id in done + failed:
            kind, _, key = action_id.partition(":")
            if kind == "wake":
                wakes[key] = {"at": at}
            elif kind == "alert" and key in signals and action_id in done:
                signals[key]["alertedAt"] = at
            elif kind == "alert" and key in signals:
                signals[key]["alertFailed"] = True
            elif action_id == "notify:more" and action_id in done:
                notices.update({merged: at for merged in plan_doc.get("merged", []) if merged in live["notices"]})
            elif kind == "notify" and action_id in done:
                notices[key] = at
            elif kind == "stall" and action_id in done:
                stall_asks[key] = at
        state.update(snapshot=plan_doc["snapshot"], signals=signals, wakes=wakes, notices=notices, lastRunAt=at,
                     stallAsks=stall_asks)
        tx.write_state(DOMAIN, state)
        tx.append_event("patrol.run", ref=None, actor="patrol",
                        data={"now": at, "recordedAt": now or store.now(), "done": done, "failed": failed,
                              "by": plan_doc.get("by", "schedule")})


PROMPT = """这是 decision-inbox 协作组「{group}」的巡视任务，每 5 分钟运行一次。按下面三步做完就结束，不做别的事，不催任何会话干活。

第 1 步：用 agent-relay 的 bridge_agents 工具（不带参数）读取各会话状态，把返回的 JSON 原文原样写入文件 {agents}；再用 bridge_outbox（agent 写 {hub}，不带别的参数）读决策收件箱发出、对方还没确认的消息，把返回的 JSON 原文原样写入文件 {outbox}。

第 2 步：运行
{cli} patrol plan {group} --agents {agents} --outbox {outbox} --out {plan}
它打印本轮要做的动作（JSON 的 actions），每个动作有 id、kind、target、text。没有动作就直接到第 3 步。

逐条执行：
- kind 为 wake：用桌面版的会话消息工具 send_message，把 text 原样发给会话 target（桌面版会话编号）。
- kind 为 owner-alert：用 agent-relay 的 bridge_send，把 text 原样发给邮箱名 target，不要求回复。
- kind 为 notify：运行下面这条命令发桌面通知，把 text 原样作为一个参数传入：
  {cli} notify "<text>"

第 3 步：运行
{cli} patrol record {group} --plan {plan} --done <做成的动作 id…> --failed <失败的动作 id…>
做成的写在 --done 后，失败的写在 --failed 后，没有的一项可以省略。

注意：只执行计划里的动作；不要读或转述任何消息正文；某一步出错就把出错的那一条记为失败，继续做完其余的。
"""


def prompt(group: str, cli: str | None = None, workdir: str | None = None, hub: str | None = None) -> str:
    """The self-contained scheduled-task prompt (spec 关键决策 7); onboarding installs it.

    Its files live in the group's io/, the one directory the hub allowlist lets it write
    without a prompt (rehearsal2-fixes); a run stuck on a prompt blocks every later run.
    """
    workdir = workdir or str(store.root_dir() / group / "io")
    if hub is None:  # onboard hub passes its own name: its entry is not on the roster yet
        try:
            roster = store.roster(store.open_group(group))
        except (store.GroupNotFound, store.InvalidName):
            roster = []
        hub = next((e["relayName"] for e in roster if e["role"] == "hub"), "<决策收件箱邮箱名>")
    return PROMPT.format(group=group, cli=cli or install.cli(), agents=f"{workdir}/decision-inbox-{group}-agents.json",
                         outbox=f"{workdir}/decision-inbox-{group}-outbox.json", hub=hub,
                         plan=f"{workdir}/decision-inbox-{group}-plan.json")
