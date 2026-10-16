"""Group state store: ~/.decision-inbox/<group>/ (see spec/group-store.md)."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path

VERSION = 1
_NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$")


class StoreError(Exception):
    """Base class for every store failure."""


class InvalidName(StoreError):
    """A group or domain name breaks the naming rule."""


class GroupNotFound(StoreError):
    """The group directory does not exist."""


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


class Group:
    def __init__(self, name: str, path: Path):
        self.name = name
        self.path = path


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
    return Group(name, path), True


def open_group(name: str) -> Group:
    validate_name(name)
    path = root_dir() / name
    if not (path / "group.json").is_file():
        raise GroupNotFound(f"协作组不存在：{name}（{path}）")
    return Group(name, path)
