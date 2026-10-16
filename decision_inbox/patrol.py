"""Patrol: decide wakes, owner alerts and user notices; remember what was done (see spec/patrol.md).

`plan` is read-only and returns the actions for the scheduled task session to
carry out; `record` is the only writer of the `patrol` domain. Every "only
once" rule is kept in that domain, so catch-up runs never repeat an action.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from decision_inbox import health, items, store, view

DOMAIN = "patrol"
OFFLINE = ("offline", "unreachable")
PROGRESS_SIGNALS = (3, 6, 7, 8, 9)
HUB_REMINDER_MINUTES = 30  # spec 已定事项 5
NOTICES_PER_ROUND = 3      # spec 关键决策 5
WAKE_GRACE_MINUTES = 5     # one patrol interval before a wake counts as failed (spec 关键决策 3)


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

    def to_json(self) -> dict:
        return {"version": 1, "now": self.now,
                "actions": [a.__dict__ for a in self.actions],
                "snapshot": self.snapshot, "live": self.live, "merged": self.merged}


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def signal_key(signal) -> str:
    return "|".join([str(signal.no), *signal.sessions])


def notice_text(text: str) -> str:
    """Desktop notification wording (spec 关键决策 5)."""
    return f"decision-inbox：{text}，详见收件枢纽"


@dataclass
class _Context:
    g: store.Group
    now: str
    relay: object | None
    state: dict
    plan: Plan

    def notify(self, key: str, text: str) -> None:
        """Queue a user notice once per live episode of `key`."""
        self.plan.live["notices"].append(key)
        if key not in self.state.get("notices", {}):
            self.plan.actions.append(Action(f"notify:{key}", "notify", None, notice_text(text)))


def _fact(ctx: _Context, name: str):
    return ctx.relay.agents.get(name) if ctx.relay is not None else None


def _wake(ctx: _Context, entry: dict, text: str) -> None:
    """Wake a stopped Claude session once per offline episode; tell the user if that did not help."""
    name, short = entry["relayName"], entry["shortName"]
    ctx.plan.live["wakes"].append(name)
    if not entry.get("desktopSession"):
        ctx.notify(f"unwakeable:{name}", f"{short} 停着，名册里没登记它的桌面版会话，叫不醒，请手动打开")
        return
    tried = ctx.state.get("wakes", {}).get(name)
    if tried is None:
        ctx.plan.actions.append(Action(f"wake:{name}", "wake", entry["desktopSession"], text))
    elif (_instant(ctx.now) - _instant(tried["at"])).total_seconds() >= WAKE_GRACE_MINUTES * 60:
        ctx.notify(f"unwakeable:{name}", f"叫不醒 {short}，它还停着，请手动打开")


def _wakes(ctx: _Context) -> None:
    """Spec 关键决策 3: stopped Claude sessions with messages waiting."""
    for entry in store.roster(ctx.g):
        fact = _fact(ctx, entry["relayName"])
        if (entry["host"] == "claude-desktop" and entry["role"] != "hub" and fact is not None
                and fact.presence in OFFLINE and fact.waiting_count):
            _wake(ctx, entry, f"【decision-inbox 巡视】你有 {fact.waiting_count} 条消息在等，请查看收件箱后继续。")


def _wake_hub(ctx: _Context) -> None:
    """Spec 关键决策 3: wake the hub too when the user is about to be notified and it is stopped."""
    hub = next((e for e in store.roster(ctx.g) if e["role"] == "hub"), None)
    fact = _fact(ctx, hub["relayName"]) if hub else None
    if hub is None or fact is None or fact.presence not in OFFLINE:
        return
    if not any(a.kind == "notify" for a in ctx.plan.actions) and hub["relayName"] not in ctx.state.get("wakes", {}):
        return
    ctx.plan.live["wakes"].append(hub["relayName"])
    if hub.get("desktopSession") and hub["relayName"] not in ctx.state.get("wakes", {}):
        ctx.plan.actions.append(Action(f"wake:{hub['relayName']}", "wake", hub["desktopSession"],
                                       "【decision-inbox 巡视】有新的事要告诉用户，请刷新收件枢纽主视图。"))


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
            ctx.notify(f"escalate:{key}", f"{short}：{signal.text}；负责人 {health.ESCALATE_MINUTES} 分钟没处理")


def _user_notices(ctx: _Context, signals, relay_error: str | None) -> None:
    """Signal 1, items holding lines up too long, and an unreadable agent-relay (spec 已定事项 5, 关键决策 5)."""
    for signal in signals:
        if signal.no == 1:
            ctx.notify("all-waiting", signal.text)
    for it in items.pending(ctx.g):
        waited = (_instant(ctx.now) - _instant(it["receivedAt"])).total_seconds() / 60
        if it["blocks"] and waited >= HUB_REMINDER_MINUTES:
            topic = it["decide"].splitlines()[0]
            ctx.notify(f"item:{it['no']}", f"#{it['no']}「{topic}」已等 {int(waited)} 分钟，挡住 {it['blocks']} 条线")
    if relay_error:
        ctx.notify("relay-unreadable", "巡视读不到 agent-relay 的状态")


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
         relay_error: str | None = None) -> Plan:
    """Read-only: what this round should do (spec 关键决策 1)."""
    state = store.read_state(g, DOMAIN)
    assessment = health.assess(g, now=now, relay=relay, maps=maps or {}, previous=state.get("snapshot"))
    result = Plan(now=now, snapshot=assessment.snapshot)
    result.live["signals"] = sorted({signal_key(s) for s in assessment.signals})
    ctx = _Context(g, now, relay, state, result)
    _user_notices(ctx, assessment.signals, relay_error)
    _wakes(ctx)
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
        state.update(snapshot=plan_doc["snapshot"], signals=signals, wakes=wakes, notices=notices, lastRunAt=at)
        tx.write_state(DOMAIN, state)
        tx.append_event("patrol.run", ref=None, actor="patrol",
                        data={"now": at, "recordedAt": now or store.now(), "done": done, "failed": failed})


PROMPT = """这是 decision-inbox 协作组「{group}」的巡视任务，每 5 分钟运行一次。按下面三步做完就结束，不做别的事，不催任何会话干活。

第 1 步：用 agent-relay 的 bridge_agents 工具（不带参数）读取各会话状态，把返回的 JSON 原文原样写入文件 {agents}。

第 2 步：运行
{cli} patrol plan {group} --agents {agents} --out {plan}
它打印本轮要做的动作（JSON 的 actions），每个动作有 id、kind、target、text。没有动作就直接到第 3 步。

逐条执行：
- kind 为 wake：用桌面版的会话消息工具 send_message，把 text 原样发给会话 target（桌面版会话编号）。
- kind 为 owner-alert：用 agent-relay 的 bridge_send，把 text 原样发给身份 target，不要求回复。
- kind 为 notify：用 Bash 发桌面通知（文字作为参数传入，不要拼进脚本）：
  osascript -e 'on run argv' -e 'display notification (item 1 of argv) with title "decision-inbox"' -e 'end run' "<text>"

第 3 步：运行
{cli} patrol record {group} --plan {plan} --done <做成的动作 id…> --failed <失败的动作 id…>
做成的写在 --done 后，失败的写在 --failed 后，没有的一项可以省略。

注意：只执行计划里的动作；不要读或转述任何消息正文；某一步出错就把出错的那一条记为失败，继续做完其余的。
"""


def prompt(group: str, cli: str = "python3 -m decision_inbox", workdir: str = "$TMPDIR") -> str:
    """The self-contained scheduled-task prompt (spec 关键决策 7); onboarding installs it."""
    return PROMPT.format(group=group, cli=cli, agents=f"{workdir}/decision-inbox-{group}-agents.json",
                         plan=f"{workdir}/decision-inbox-{group}-plan.json")
