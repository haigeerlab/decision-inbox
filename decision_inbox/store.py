"""Group state store: ~/.decision-inbox/<group>/ (see spec/group-store.md)."""

from __future__ import annotations

import fcntl
import json
import os
import re
from datetime import datetime
from pathlib import Path

VERSION = 1
_NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$")
_EVENT_TYPE_RE = re.compile(r"^[a-z0-9-]+\.[a-z0-9-]+$")


class StoreError(Exception):
    """Base class for every store failure."""


class InvalidName(StoreError):
    """A group or domain name breaks the naming rule."""


class GroupNotFound(StoreError):
    """The group directory does not exist."""


class StoreCorrupt(StoreError):
    """A state file exists but cannot be trusted; never overwrite it."""


class InvalidSession(StoreError):
    """A roster entry breaks the roster rules."""


ROLES = ("hub", "coordinator", "owner", "dev")
HOSTS = ("claude-desktop", "codex-desktop")


def _validate_session(entry: dict, others: list[dict]) -> dict:
    """Check one roster entry against the rest of the roster (spec: 会话名册条目)."""
    def bad(msg: str) -> InvalidSession:
        return InvalidSession(f"名册条目不合法（{entry.get('relayName')!r}）：{msg}")

    relay, short = entry.get("relayName"), entry.get("shortName")
    role, host, line = entry.get("role"), entry.get("host"), entry.get("line", [])
    repo = entry.get("repo")
    if not isinstance(relay, str) or not relay:
        raise bad("relayName 必填")
    if not isinstance(short, str) or not 1 <= len(short) <= 12:
        raise bad("shortName 必填，1～12 个字符")
    if role not in ROLES:
        raise bad(f"role 只能是 {'／'.join(ROLES)}")
    if host not in HOSTS:
        raise bad(f"host 只能是 {'／'.join(HOSTS)}")
    if not isinstance(line, list) or not all(isinstance(x, str) and x for x in line):
        raise bad("line 必须是短名数组")
    if repo is not None and (not isinstance(repo, str) or not os.path.isabs(repo)):
        raise bad("repo 必须是绝对路径")
    if "desktopSession" in entry:
        desktop = entry["desktopSession"]
        if not isinstance(desktop, str) or not desktop.startswith("local_") or len(desktop) <= len("local_"):
            raise bad("desktopSession 必须是桌面版会话编号（local_ 开头）")
    if role == "dev" and (len(line) != 1 or repo is None):
        raise bad("开发线必须恰好属于一条线，并填写 repo")
    for flag in ("crewCoordinator", "localRules"):
        if flag in entry and not isinstance(entry[flag], bool):
            raise bad(f"{flag} 只能是 true 或 false")
    if entry.get("crewCoordinator") and role != "dev":
        raise bad("只有开发线能标为并行开发协调会话")
    if entry.get("localRules") and host != "claude-desktop":
        raise bad("只有 Claude 桌面版的会话能把约定块写进 CLAUDE.local.md")
    if role == "owner" and not line:
        raise bad("负责人至少负责一条线")
    if role in ("hub", "coordinator") and line:
        raise bad("收件枢纽和总协调不属于任何线")
    if role == "hub" and host != "claude-desktop":
        raise bad("收件枢纽只能是 Claude 桌面版")
    for other in others:
        if other["shortName"] == short:
            raise bad(f"shortName 与 {other['relayName']} 重复")
        if role == "hub" and other["role"] == "hub":
            raise bad(f"每组只能有一个收件枢纽，已有 {other['relayName']}")
    return dict(entry, line=list(line))


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def root_dir() -> Path:
    override = os.environ.get("DECISION_INBOX_HOME")
    return Path(override) if override else Path.home() / ".decision-inbox"


def validate_name(name: str) -> str:
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise InvalidName(
            f"名称不合法：{name!r}。只能用小写字母、数字、连字符，1～40 个字符，不以连字符开头或结尾"
        )
    return name


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def _dump(doc: dict) -> bytes:
    return (json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _atomic_write_json(path: Path, doc: dict) -> None:
    _atomic_write_bytes(path, _dump(doc))


def _read_json(path: Path, default: dict | None = None) -> dict:
    """Read a versioned JSON file; raise StoreCorrupt instead of guessing."""
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        if default is None:
            raise StoreCorrupt(f"状态文件缺失：{path}")
        return dict(default)
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise StoreCorrupt(f"状态文件无法解析：{path}（{e}）") from None
    if not isinstance(doc, dict):
        raise StoreCorrupt(f"状态文件顶层不是对象：{path}")
    if doc.get("version") != VERSION:
        raise StoreCorrupt(f"状态文件版本不认识：{path}（version={doc.get('version')!r}）")
    return doc


def _scan_log(path: Path) -> tuple[list[dict], list[str], bool]:
    """Parse events.jsonl. Returns (events, warnings, ends_with_newline).

    A crash mid-append leaves a partial last line; the next append closes it
    with a newline, so it later sits mid-file. Unparsable lines are therefore
    skipped with a warning rather than treated as corruption.
    """
    raw = path.read_bytes()
    lines = raw.split(b"\n")
    events: list[dict] = []
    warnings: list[str] = []
    for i, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            doc = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            doc = None
        if not isinstance(doc, dict) or not isinstance(doc.get("seq"), int):
            where = "末尾" if i == len(lines) else f"第 {i} 行"
            warnings.append(f"事件日志{where}有一行不完整或无法解析，已跳过：{path}")
            continue
        events.append(doc)
    return events, warnings, raw == b"" or raw.endswith(b"\n")


def _state_path(group: "Group", domain: str) -> Path:
    return group.path / "state" / f"{validate_name(domain)}.json"


def _snapshot_lag(group: "Group", events: list[dict]) -> dict[str, int]:
    """Per domain: how many of its events are newer than its snapshot's lastSeq.

    An event belongs to the domain named before the dot in its type.
    Unreadable snapshots are skipped here; check() reports them separately.
    """
    lag: dict[str, int] = {}
    state_dir = group.path / "state"
    if not state_dir.is_dir():
        return lag
    for path in sorted(state_dir.glob("*.json")):
        domain = path.stem
        try:
            last = int(_read_json(path).get("lastSeq", 0))
        except (StoreError, TypeError, ValueError):
            continue
        behind = sum(1 for e in events
                     if str(e.get("type", "")).split(".")[0] == domain and e["seq"] > last)
        if behind:
            lag[domain] = behind
    return lag


def _lag_warnings(group: "Group", events: list[dict]) -> list[str]:
    return [f"快照落后于日志 {n} 条：{domain}"
            for domain, n in _snapshot_lag(group, events).items()]


def _empty_state() -> dict:
    return {"version": VERSION, "lastSeq": 0}


class Transaction:
    """Holds the group lock; buffers every change and writes on clean exit.

    Commit order: append events first, then replace snapshots and the counter.
    On exception nothing touches the disk.
    """

    def __init__(self, group: "Group"):
        self.group = group
        self._lock_fd: int | None = None
        self._states: dict[str, dict] = {}
        self._counter: dict | None = None
        self._counter_dirty = False
        self._roster: dict | None = None
        self._events: list[dict] = []
        self._last_seq: int | None = None
        self.warnings: list[str] = []

    def __enter__(self) -> "Transaction":
        lock = self.group.path / ".lock"
        self._lock_fd = os.open(lock, os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.flock(self._lock_fd, fcntl.LOCK_EX)
        try:
            events, self.warnings, _ = _scan_log(self.group.path / "events.jsonl")
            self.warnings += _lag_warnings(self.group, events)
        except BaseException:
            fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            os.close(self._lock_fd)
            raise
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        try:
            if exc_type is None:
                self._commit()
        finally:
            fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            os.close(self._lock_fd)
        return False

    def read_state(self, domain: str) -> dict:
        if domain in self._states:
            return self._states[domain]
        return _read_json(_state_path(self.group, domain), _empty_state())

    def write_state(self, domain: str, doc: dict) -> None:
        _state_path(self.group, domain)
        if not isinstance(doc, dict):
            raise TypeError("state document must be a dict")
        self._states[domain] = doc

    def allocate_number(self) -> int:
        if self._counter is None:
            self._counter = _read_json(self.group.path / "counter.json")
            if not isinstance(self._counter.get("next"), int) or self._counter["next"] < 1:
                raise StoreCorrupt(f"编号序列取值不合法：{self.group.path / 'counter.json'}")
        n = self._counter["next"]
        self._counter["next"] = n + 1
        self._counter_dirty = True
        return n

    def append_event(self, type: str, ref: int | None = None, actor: str = "system",
                     data: dict | None = None) -> int:
        if not _EVENT_TYPE_RE.match(type):
            raise ValueError(f"event type must look like <domain>.<action>: {type!r}")
        if self._last_seq is None:
            events, _, _ = _scan_log(self.group.path / "events.jsonl")
            self._last_seq = max((e.get("seq", 0) for e in events), default=0)
        self._last_seq += 1
        self._events.append({
            "seq": self._last_seq, "at": now(), "type": type,
            "ref": ref, "actor": actor, "data": data or {},
        })
        return self._last_seq

    def _sessions(self) -> list[dict]:
        if self._roster is None:
            self._roster = _read_json(self.group.path / "roster.json")
        return self._roster.setdefault("sessions", [])

    def add_session(self, entry: dict) -> None:
        """Add a new roster entry; a duplicate relayName is rejected."""
        sessions = self._sessions()
        if any(s.get("relayName") == entry.get("relayName") for s in sessions):
            raise InvalidSession(f"名册条目不合法（{entry.get('relayName')!r}）：relayName 已存在")
        sessions.append(_validate_session(entry, sessions))

    def replace_session(self, entry: dict) -> None:
        """Replace the existing entry with the same relayName."""
        sessions = self._sessions()
        for i, s in enumerate(sessions):
            if s.get("relayName") == entry.get("relayName"):
                sessions[i] = _validate_session(entry, sessions[:i] + sessions[i + 1:])
                return
        raise InvalidSession(f"名册里没有 {entry.get('relayName')!r}，无法替换")

    def _commit(self) -> None:
        # Validate every file we are about to replace before writing anything.
        for domain in self._states:
            _read_json(_state_path(self.group, domain), _empty_state())
        if self._events:
            log = self.group.path / "events.jsonl"
            _, _, clean_end = _scan_log(log)
            payload = b"".join(
                (json.dumps(e, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
                for e in self._events
            )
            with open(log, "ab") as f:
                f.write((b"" if clean_end else b"\n") + payload)
                f.flush()
                os.fsync(f.fileno())
        if self._states:
            (self.group.path / "state").mkdir(mode=0o700, exist_ok=True)
        for domain, doc in self._states.items():
            # lastSeq = newest event of this domain the snapshot reflects.
            mine = [e["seq"] for e in self._events if e["type"].split(".")[0] == domain]
            out = dict(doc, version=VERSION)
            out["lastSeq"] = max([int(doc.get("lastSeq", 0)), *mine])
            _atomic_write_json(_state_path(self.group, domain), out)
        if self._counter_dirty:
            _atomic_write_json(self.group.path / "counter.json", self._counter)
        if self._roster is not None:
            _atomic_write_json(self.group.path / "roster.json", self._roster)


class Group:
    def __init__(self, name: str, path: Path):
        self.name = name
        self.path = path

    def transaction(self) -> Transaction:
        return Transaction(self)


def check(group: Group) -> dict:
    """Read-only health report used by `store show`.

    problems make `show` exit 3; warnings do not.
    """
    report: dict = {"path": str(group.path), "files": {}, "problems": [], "warnings": [],
                    "next": None, "sessions": None, "events": 0}
    targets = [group.path / n for n in ("group.json", "roster.json", "counter.json")]
    state_dir = group.path / "state"
    if state_dir.is_dir():
        targets += sorted(state_dir.glob("*.json"))
    docs = {}
    for path in targets:
        rel = str(path.relative_to(group.path))
        try:
            docs[rel] = _read_json(path)
            report["files"][rel] = f"version {docs[rel]['version']}"
        except StoreCorrupt as e:
            report["files"][rel] = "无法使用"
            report["problems"].append(str(e))
    if "counter.json" in docs:
        report["next"] = docs["counter.json"].get("next")
    if "roster.json" in docs:
        report["sessions"] = len(docs["roster.json"].get("sessions", []))
    events, warnings, _ = _scan_log(group.path / "events.jsonl")
    report["events"] = len(events)
    report["warnings"] += warnings
    report["problems"] += _lag_warnings(group, events)
    return report


def read_events(group: Group, ref: int | None = None,
                warnings: list[str] | None = None) -> list[dict]:
    """Lock-free read of the event log, sorted by seq; optionally one ref only."""
    events, found, _ = _scan_log(group.path / "events.jsonl")
    if warnings is not None:
        warnings.extend(found)
    if ref is not None:
        events = [e for e in events if e.get("ref") == ref]
    return sorted(events, key=lambda e: e["seq"])


def roster(group: Group) -> list[dict]:
    """Lock-free read of the roster entries, in insertion order."""
    return list(_read_json(group.path / "roster.json").get("sessions", []))


def find_session(group: Group, relay_name: str | None = None,
                 short_name: str | None = None) -> dict | None:
    for s in roster(group):
        if relay_name is not None and s.get("relayName") == relay_name:
            return s
        if short_name is not None and s.get("shortName") == short_name:
            return s
    return None


def read_state(group: Group, domain: str) -> dict:
    """Lock-free read of a domain snapshot."""
    return _read_json(_state_path(group, domain), _empty_state())


def init_group(name: str) -> tuple[Group, bool]:
    """Create the group if absent. Returns (group, created)."""
    validate_name(name)
    root = root_dir()
    path = root / name
    if path.exists():
        return Group(name, path), False
    root.mkdir(parents=True, exist_ok=True)
    path.mkdir(mode=0o700)
    os.chmod(path, 0o700)
    _atomic_write_json(path / "group.json", {"version": VERSION, "name": name, "createdAt": now()})
    _atomic_write_json(path / "roster.json", {"version": VERSION, "sessions": []})
    _atomic_write_json(path / "counter.json", {"version": VERSION, "next": 1})
    _atomic_write_bytes(path / "events.jsonl", b"")
    _atomic_write_bytes(path / ".lock", b"")
    return Group(name, path), True


def open_group(name: str) -> Group:
    validate_name(name)
    path = root_dir() / name
    if not (path / "group.json").is_file():
        raise GroupNotFound(f"协作组不存在：{name}（{path}）")
    return Group(name, path)
