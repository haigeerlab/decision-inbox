"""Claude sessions stuck on a permission prompt that nobody reported (decision-cards DI-9, I-14).

Reads agent-relay's `bridge_sessions` output, which lists every running Claude session on this Mac,
module sessions included. A session counts as stuck when `status` is `waiting` and `waitingFor` names a
permission prompt (rh2-coord's account from stage 3, confirmed on raw output 2026-10-19). Read-only.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone

from decision_inbox import items, stall, store

LINK = "claude://claude.ai/epitaxy/{}"
ALLOW = "合并 main、装依赖、跑测试"
DENY = "推送、删除、reset、改它目录以外的文件"


class DesktopDataError(ValueError):
    """bridge_sessions output that cannot be read."""


@dataclass(frozen=True)
class Session:
    host: str | None          # hostSessionId, the local_… id a link opens
    name: str
    cwd: str | None
    status: str | None
    waiting_for: str | None
    since: datetime | None    # statusUpdatedAt


def parse_sessions(text: str) -> tuple[Session, ...]:
    try:
        doc = json.loads(text)
    except ValueError as e:
        raise DesktopDataError(f"bridge_sessions 读不懂（{e}）") from e
    rows = doc.get("claude") if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        raise DesktopDataError("bridge_sessions 里没有 claude 列表")
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        at = row.get("statusUpdatedAt")
        since = datetime.fromtimestamp(at / 1000, tz=timezone.utc) if isinstance(at, (int, float)) else None
        text_or_none = (lambda key: row[key] if isinstance(row.get(key), str) else None)
        out.append(Session(text_or_none("hostSessionId"), text_or_none("name") or text_or_none("sessionId") or "?",
                           text_or_none("cwd"), text_or_none("status"), text_or_none("waitingFor"), since))
    return tuple(out)


def _inside(path: str, root: str) -> bool:
    path, root = os.path.realpath(path), os.path.realpath(root)
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def _owner(g: store.Group, s: Session) -> dict | None:
    """The roster entry a session belongs to: its own link, a roster repo, or a module-crew module workspace."""
    roster = [e for e in store.roster(g) if e["relayName"] not in store.left_relays(g)]
    by_link = next((e for e in roster if s.host and e.get("desktopSession") == s.host), None)
    if by_link is not None or not s.cwd:
        return by_link
    for e in roster:
        repo = e.get("repo")
        if repo and (_inside(s.cwd, repo) or _inside(s.cwd, repo.rstrip(os.sep) + "-crew")):
            return e
    return None


def stuck(g: store.Group, now: str, sessions) -> list[tuple[Session, int, dict]]:
    """(session, minutes on the prompt, roster entry) for prompts nobody has reported yet."""
    patrol_session = store.read_state(g, "onboarding").get("patrolSession")
    minutes_needed = stall.settings(g)["promptMinutes"]
    reported = {it["sender"] for it in items.pending(g) if items.is_go_to_session(it)}
    at = datetime.fromisoformat(now.replace("Z", "+00:00"))
    out = []
    for s in sessions or ():
        if s.status != "waiting" or "permission" not in (s.waiting_for or "").lower() or s.since is None:
            continue
        owner = _owner(g, s)
        if owner is None or owner["role"] == "hub" or (s.host and s.host == patrol_session):
            continue
        if owner["relayName"] in reported:
            continue
        minutes = max(0, int((at - s.since).total_seconds() // 60))
        if minutes >= minutes_needed:
            out.append((s, minutes, owner))
    return out


def card(s: Session, waited: str) -> str:
    """Class 7: nothing to answer, so no copy block."""
    lines = [f"**去 {s.name} 点一下弹窗**（收件箱发现的，提出方没报）· 等了 {waited}"]
    if s.host:
        lines.append(f"去：{LINK.format(s.host)}")
    lines += [f"点「允许」：{ALLOW}", f"点「拒绝」：{DENY}", "点完不用回复，弹窗消失后这条自己消失。"]
    return "\n".join(lines)


def notice_key(s: Session) -> str:
    return f"prompt:{s.host or s.name}|{int(s.since.timestamp()) if s.since else 0}"
