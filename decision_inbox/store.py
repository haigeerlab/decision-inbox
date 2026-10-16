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

    Only the last line may be incomplete (a crash mid-append); it is skipped
    with a warning. A bad line anywhere else means the log is corrupt.
    """
    raw = path.read_bytes()
    lines = raw.split(b"\n")
    complete, tail = lines[:-1], lines[-1]
    events: list[dict] = []
    warnings: list[str] = []
    for i, line in enumerate(complete, start=1):
        if not line.strip():
            continue
        try:
            events.append(json.loads(line.decode("utf-8")))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise StoreCorrupt(f"事件日志第 {i} 行无法解析：{path}") from None
    if tail.strip():
        warnings.append(f"事件日志末尾有一行不完整，已跳过：{path}")
    return events, warnings, raw == b"" or raw.endswith(b"\n")


def _state_path(group: "Group", domain: str) -> Path:
    return group.path / "state" / f"{validate_name(domain)}.json"


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
        self._events: list[dict] = []
        self._last_seq: int | None = None

    def __enter__(self) -> "Transaction":
        lock = self.group.path / ".lock"
        self._lock_fd = os.open(lock, os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.flock(self._lock_fd, fcntl.LOCK_EX)
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


class Group:
    def __init__(self, name: str, path: Path):
        self.name = name
        self.path = path

    def transaction(self) -> Transaction:
        return Transaction(self)


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
