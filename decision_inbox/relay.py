"""Read-only view of agent-relay facts (see spec/relay-reader.md).

Input is the JSON text a session got back from the MCP tools `bridge_agents`,
`bridge_outbox` and `bridge_wake_status` (agent-relay >= 0.6.10, interface 2.x). Message bodies and
previews are never copied into the output, except by `parse_inbox`, whose job is to hand the hub's
own incoming messages to hub-loop (spec/hub-loop.md).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

MIN_VERSION = (0, 6, 10)
_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
_PRESENCE = {
    "running": "active",
    "waiting-input": "needs-user",
    "waiting-approval": "needs-user",
    "stopped": "offline",
    "unreachable": "unreachable",
}
UPGRADE_HINT = "agent-relay 需升级到 0.6.10"


class RelayDataError(ValueError):
    """The relay output as a whole cannot be trusted; no partial result."""


@dataclass(frozen=True)
class AgentFact:
    name: str
    host_app: str | None
    presence_raw: str | None
    presence: str
    presence_since: str | None
    unread: int | None
    waiting_count: int | None
    waiting_from: tuple[str, ...]
    waiting_ids: tuple[int, ...]
    waiting_oldest_at: str | None
    last_activity_at: str | None
    wake_bound: bool | None
    retired: bool
    presence_detail: str | None = None
    activity: str | None = None            # "busy" | "idle" while a Claude session runs (0.8.1+)
    doubtful_ids: tuple[int, ...] = ()      # accepted but unread Codex deliveries (0.8.2+)


@dataclass(frozen=True)
class AgentsSnapshot:
    relay_status: str
    agents: dict[str, AgentFact]
    warnings: tuple[str, ...] = field(default=())


@dataclass(frozen=True)
class MessageFact:
    id: int
    sender: str
    recipient: str
    sent_at: str | None
    delivery_state: str | None
    acknowledged_at: str | None
    expires_at: str | None
    reply_ids: tuple[int, ...]
    reply_to: int | None
    wake_doubt: bool = False                # wake.doubt: accepted but unread (0.8.2+)
    wake_pending: str | None = None         # wake.pendingReason: offline, unreachable or busy (stall-and-patrol R19)


@dataclass(frozen=True)
class Outbox:
    sender: str
    messages: tuple[MessageFact, ...]
    warnings: tuple[str, ...] = field(default=())


@dataclass(frozen=True)
class InboxMessage:
    id: int
    sender: str
    body: str
    created_at: str | None
    reply_to: int | None
    expects_reply: bool
    truncated: bool
    next_offset: int | None


@dataclass(frozen=True)
class Inbox:
    agent: str | None
    messages: tuple[InboxMessage, ...]
    has_more: bool
    warnings: tuple[str, ...] = field(default=())


def _load(text: str, key: str, tool: str) -> list:
    try:
        doc = json.loads(text)
    except (TypeError, json.JSONDecodeError) as e:
        raise RelayDataError(f"{tool} 的返回不是合法 JSON：{e}") from None
    if not isinstance(doc, dict) or not isinstance(doc.get(key), list):
        raise RelayDataError(f"{tool} 的返回缺少 {key} 数组")
    return doc[key]


def _int_or_none(value) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _str_or_none(value) -> str | None:
    return value if isinstance(value, str) else None


def _parse_version(version: str | None, warnings: list[str]) -> tuple[int, int, int] | None:
    if version is None:
        return None
    m = _VERSION_RE.match(version) if isinstance(version, str) else None
    if not m:
        warnings.append(f"给出的 agent-relay 版本号看不懂，已忽略：{version!r}")
        return None
    return tuple(int(x) for x in m.groups())  # type: ignore[return-value]


def _relay_status(raw_agents: list[dict], version, warnings: list[str]) -> str:
    """Evidence only (spec 关键决策 2): explicit version, else any oldestAt, else undetermined."""
    if version is not None:
        if version < MIN_VERSION:
            warnings.append(UPGRADE_HINT)
            return "too-old"
        return "ok"
    if any(isinstance(a.get("waiting"), dict) and "oldestAt" in a["waiting"] for a in raw_agents):
        return "ok"
    return "undetermined"


ACTIVITIES = ("busy", "idle")


def _doubt(wake) -> bool:
    return isinstance(wake, dict) and isinstance(wake.get("doubt"), dict)


def parse_agents(text: str, relay_version: str | None = None) -> AgentsSnapshot:
    raw = _load(text, "agents", "bridge_agents")
    warnings: list[str] = []
    entries = [a for a in raw if isinstance(a, dict)]
    status = _relay_status(entries, _parse_version(relay_version, warnings), warnings)
    agents: dict[str, AgentFact] = {}
    for a in entries:
        name = a.get("name")
        if not isinstance(name, str) or not name:
            warnings.append("bridge_agents 有一条记录缺少 name，已跳过")
            continue
        host = a.get("host") if isinstance(a.get("host"), dict) else None
        host_app = _str_or_none(host.get("app")) if host else None
        presence = a.get("presence") if isinstance(a.get("presence"), dict) else {}
        presence_raw = _str_or_none(presence.get("state"))
        retired = a.get("retiredAt") is not None
        waiting = a.get("waiting") if isinstance(a.get("waiting"), dict) else None
        if retired:
            count = 0
        elif status == "too-old" and host_app != "codex":
            count = None  # an old relay's Claude waiting list is not trustworthy
        elif waiting is not None:
            count = _int_or_none(waiting.get("count"))
        elif host_app == "codex" or status == "ok":
            count = 0
        else:
            count = None
        agents[name] = AgentFact(
            name=name,
            host_app=host_app,
            presence_raw=presence_raw,
            presence=_PRESENCE.get(presence_raw, "unknown"),
            presence_since=_str_or_none(presence.get("since")),
            presence_detail=_str_or_none(presence.get("detail")) or None,
            unread=_int_or_none(a.get("unread")),
            waiting_count=count,
            waiting_from=tuple(x for x in (waiting or {}).get("from", []) if isinstance(x, str)),
            waiting_ids=tuple(x for x in (waiting or {}).get("ids", []) if _int_or_none(x) is not None),
            waiting_oldest_at=_str_or_none((waiting or {}).get("oldestAt")),
            last_activity_at=_str_or_none(a.get("lastActivity")),
            wake_bound=(a["wake"] is not None) if "wake" in a else None,
            retired=retired,
            activity=presence.get("activity") if presence.get("activity") in ACTIVITIES else None,
            doubtful_ids=tuple(x for x in (waiting or {}).get("doubtfulIds", []) if _int_or_none(x) is not None),
        )
    return AgentsSnapshot(relay_status=status, agents=agents, warnings=tuple(warnings))


def parse_outbox(text: str, sender: str) -> Outbox:
    """bridge_outbox output for `sender`; previews and bodies are dropped."""
    raw = _load(text, "entries", "bridge_outbox")
    warnings: list[str] = []
    messages: list[MessageFact] = []
    for e in raw:
        if not isinstance(e, dict) or _int_or_none(e.get("id")) is None:
            warnings.append("bridge_outbox 有一条记录缺少 id，已跳过")
            continue
        messages.append(MessageFact(
            id=e["id"],
            sender=sender,
            recipient=_str_or_none(e.get("toAgent")) or "",
            sent_at=_str_or_none(e.get("createdAt")),
            delivery_state=_str_or_none(e.get("deliveryState")),
            acknowledged_at=_str_or_none(e.get("acknowledgedAt")),
            expires_at=_str_or_none(e.get("expiresAt")),
            reply_ids=tuple(x for x in e.get("replies") or [] if _int_or_none(x) is not None),
            reply_to=_int_or_none(e.get("replyTo")),
            wake_doubt=_doubt(e.get("wake")),
            wake_pending=_str_or_none((e.get("wake") or {}).get("pendingReason"))
            if isinstance(e.get("wake"), dict) else None,
        ))
    return Outbox(sender=sender, messages=tuple(messages), warnings=tuple(warnings))


@dataclass(frozen=True)
class MessageStatusFact:
    id: int
    sender: str
    recipient: str
    sent_at: str | None
    delivery_state: str | None
    acknowledged_at: str | None
    reply_ids: tuple[int, ...]
    wake_state: str | None
    wake_detail: str | None
    outcome: str | None
    wake_doubt: bool = False


def parse_message_status(text: str) -> MessageStatusFact:
    """bridge_wake_status(messageId) output; the preview is dropped."""
    try:
        doc = json.loads(text)
    except (TypeError, json.JSONDecodeError) as e:
        raise RelayDataError(f"bridge_wake_status 的返回不是合法 JSON：{e}") from None
    message = doc.get("message") if isinstance(doc, dict) else None
    if not isinstance(message, dict) or _int_or_none(message.get("id")) is None:
        raise RelayDataError("bridge_wake_status 的返回缺少 message.id")
    wake = doc.get("wake") if isinstance(doc.get("wake"), dict) else {}
    return MessageStatusFact(
        id=message["id"],
        sender=_str_or_none(message.get("fromAgent")) or "",
        recipient=_str_or_none(message.get("toAgent")) or "",
        sent_at=_str_or_none(message.get("createdAt")),
        delivery_state=_str_or_none(doc.get("deliveryState")),
        acknowledged_at=_str_or_none(doc.get("acknowledgedAt")),
        reply_ids=tuple(x for x in doc.get("replies") or [] if _int_or_none(x) is not None),
        wake_state=_str_or_none(wake.get("state")),
        wake_detail=_str_or_none(wake.get("detail")) or None,
        outcome=_str_or_none(doc.get("outcome")),
        wake_doubt=_doubt(wake),
    )


def parse_wake_jobs(text: str) -> dict[str, dict[str, int]]:
    """bridge_wake_status without arguments -> {agent: {wake state: count}}; malformed jobs are skipped."""
    counts: dict[str, dict[str, int]] = {}
    for job in _load(text, "jobs", "bridge_wake_status"):
        if not isinstance(job, dict):
            continue
        agent, state = _str_or_none(job.get("agent")), _str_or_none(job.get("state"))
        if agent and state:
            per = counts.setdefault(agent, {})
            per[state] = per.get(state, 0) + 1
    return counts


def parse_inbox(text: str) -> Inbox:
    """bridge_inbox output (a page with `messages`, or one `message` read by id), bodies kept."""
    try:
        doc = json.loads(text)
    except (TypeError, json.JSONDecodeError) as e:
        raise RelayDataError(f"bridge_inbox 的返回不是合法 JSON：{e}") from None
    if isinstance(doc, dict) and isinstance(doc.get("message"), dict) and "messages" not in doc:
        raw = [doc["message"]]
    elif isinstance(doc, dict) and isinstance(doc.get("messages"), list):
        raw = doc["messages"]
    else:
        raise RelayDataError("bridge_inbox 的返回缺少 messages 数组")
    warnings: list[str] = []
    messages: list[InboxMessage] = []
    for m in raw:
        if not isinstance(m, dict) or _int_or_none(m.get("id")) is None or not _str_or_none(m.get("fromAgent")):
            warnings.append("bridge_inbox 有一条消息缺少 id 或发件人，已跳过")
            continue
        messages.append(InboxMessage(
            id=m["id"],
            sender=m["fromAgent"],
            body=_str_or_none(m.get("body")) or "",
            created_at=_str_or_none(m.get("createdAt")),
            reply_to=_int_or_none(m.get("replyTo")),
            expects_reply=m.get("expectsReply") is True,
            truncated=m.get("bodyTruncated") is True,
            next_offset=_int_or_none(m.get("nextOffset")),
        ))
    return Inbox(agent=_str_or_none(doc.get("agent")), messages=tuple(messages),
                 has_more=doc.get("hasMore") is True, warnings=tuple(warnings))
