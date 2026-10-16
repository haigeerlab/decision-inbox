"""The fixed command path and finding a session's group by directory (see spec/plugin-packaging.md).

Plugins live in versioned directories, so rules files and the patrol task
call a forwarding script at a fixed path; the plugin rewrites it whenever
it changes.
"""

from __future__ import annotations

import os
import shlex
from pathlib import Path

from decision_inbox import store

SHIM = """#!/bin/sh
# decision-inbox: forwards to the installed plugin; rewritten when the plugin moves.
exec {target} "$@"
"""


def shim_path() -> Path:
    return store.root_dir() / "bin" / "decision-inbox"


def cli() -> str:
    """The command every convention block and the patrol prompt use."""
    return str(shim_path())


def plugin_root() -> Path:
    """Set by bin/decision-inbox; else the directory above this package."""
    env = os.environ.get("DECISION_INBOX_PLUGIN_ROOT")
    return Path(env) if env else Path(__file__).resolve().parent.parent


def write_shim(root, if_installed: bool = False) -> bool:
    """Write the forwarding script; True when it changed. With if_installed, only when the home exists."""
    if if_installed and not store.root_dir().is_dir():
        return False
    path = shim_path()
    text = SHIM.format(target=shlex.quote(str(Path(root) / "bin" / "decision-inbox")))
    if path.is_file() and path.read_text(encoding="utf-8") == text and os.access(path, os.X_OK):
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    store._atomic_write_bytes(path, text.encode("utf-8"))
    os.chmod(path, 0o755)
    return True
