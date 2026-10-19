"""The fixed command path and finding a session's group by directory (see spec/plugin-packaging.md).

Plugins live in versioned directories, so rules files and the patrol task
call a forwarding script at a fixed path; the plugin rewrites it whenever
it changes.
"""

from __future__ import annotations

import os
import shlex
import shutil
import tempfile
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


def runtime_dir() -> Path:
    """patrol-watch-runtime: the copy launchd runs, kept under the home because launchd may not read ~/Documents."""
    return store.root_dir() / "runtime"


def _runtime_files(root: Path) -> dict[str, bytes]:
    files = {"bin/decision-inbox": (root / "bin" / "decision-inbox").read_bytes()}
    for p in sorted((root / "decision_inbox").glob("*.py")):
        files[f"decision_inbox/{p.name}"] = p.read_bytes()
    return files


def write_runtime(root, if_present: bool = False) -> bool:
    """Copy bin/decision-inbox and the package from root into runtime_dir(); True when it changed.

    Replaced whole (built beside it, then renamed in), so a failure never leaves half of one version.
    With if_present, only refresh one that is already there (SessionStart does this after a plugin upgrade).
    """
    dest = runtime_dir()
    if if_present and not dest.is_dir():
        return False
    files = _runtime_files(Path(root))
    old = None
    if dest.is_dir():
        try:
            old = _runtime_files(dest)
        except OSError:
            pass
    if old == files and os.access(dest / "bin" / "decision-inbox", os.X_OK):
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=".runtime-", dir=dest.parent))
    try:
        for rel, data in files.items():
            (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
            (tmp / rel).write_bytes(data)
        os.chmod(tmp / "bin" / "decision-inbox", 0o755)
        gone = None
        if dest.exists():
            gone = dest.parent / f".runtime-old-{os.getpid()}"
            os.rename(dest, gone)
        os.rename(tmp, dest)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if gone is not None:
        shutil.rmtree(gone, ignore_errors=True)
    return True


def _inside(path: str, root: str) -> bool:
    path, root = os.path.realpath(path), os.path.realpath(root)
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def locate(cwd: str) -> list[tuple[str, dict]]:
    """Every (group, roster entry) this directory belongs to: a dev line's repo, or a recorded rules file's folder.

    Sessions that left (onboard leave/teardown) are skipped; their roster entries stay.
    """
    found = []
    home = store.root_dir()
    if not home.is_dir():
        return found
    for folder in sorted(p for p in home.iterdir() if (p / "group.json").is_file()):
        try:
            g = store.open_group(folder.name)
            state = store.read_state(g, "onboarding")
            files, left = state.get("files", {}), state.get("left", {})
            for entry in store.roster(g):
                if entry["relayName"] in left:
                    continue
                repo = entry.get("repo")
                rules = files.get(entry["relayName"])
                if (repo and _inside(cwd, repo)) or (
                        rules and os.path.realpath(cwd) == os.path.realpath(os.path.dirname(rules))):
                    found.append((g.name, entry))
        except store.StoreError:
            continue  # a broken or foreign folder is not ours to judge here
    return found
