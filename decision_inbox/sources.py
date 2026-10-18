"""Read what the user is asked to approve, verbatim (see spec/approval-display.md).

Only reads: `git show` for an artifact at a commit, the file itself for a 交审原文／审查原文.
Nothing is cached or written; a source that cannot be read says why instead of standing in.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from dataclasses import dataclass

TIMEOUT = 5.0


@dataclass(frozen=True)
class Source:
    ok: bool
    text: str | None = None
    diff: str | None = None
    reason: str | None = None


def _fail(reason: str) -> Source:
    return Source(False, reason=reason)


def _git(root: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", root, *args], capture_output=True, timeout=TIMEOUT)


def read_artifact(path: str, commit: str, previous: str | None = None) -> Source:
    """The file at `path` as of `commit`, plus the diff from `previous` when given."""
    folder = os.path.dirname(path)
    try:
        top = subprocess.run(["git", "-C", folder, "rev-parse", "--show-toplevel"], capture_output=True,
                             text=True, timeout=TIMEOUT) if os.path.isdir(folder) else None
        if top is None or top.returncode != 0:
            return _fail(f"{path} 所在目录不存在或不在 git 仓库里")
        root = top.stdout.strip()
        rel = os.path.relpath(os.path.realpath(path), os.path.realpath(root))
        if _git(root, "cat-file", "-e", f"{commit}^{{commit}}").returncode != 0:
            return _fail(f"提交 {commit} 不存在（仓库 {root}）")
        shown = _git(root, "show", f"{commit}:{rel}")
        if shown.returncode != 0:
            return _fail(f"提交 {commit} 里没有这个文件：{rel}")
        diff = None
        if previous:
            if _git(root, "cat-file", "-e", f"{previous}^{{commit}}").returncode != 0:
                return _fail(f"上一版提交 {previous} 不存在（仓库 {root}）")
            diff = _git(root, "diff", previous, commit, "--", rel).stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return _fail(f"读取超时（超过 {TIMEOUT:g} 秒）")
    try:
        return Source(True, text=shown.stdout.decode("utf-8"), diff=diff)
    except UnicodeDecodeError:
        return _fail(f"提交 {commit} 里的 {rel} 不是 UTF-8 文本")


def read_original(path: str, fingerprint: str) -> Source:
    """A 交审原文／审查原文 file, accepted only when its sha256 starts with the given prefix."""
    try:
        data = open(path, "rb").read()
    except FileNotFoundError:
        return _fail(f"文件不存在：{path}")
    except OSError as e:
        return _fail(f"文件读不了：{path}（{e.strerror}）")
    digest = hashlib.sha256(data).hexdigest()
    if not digest.startswith(fingerprint.removeprefix("sha256:")):
        return _fail(f"指纹对不上：写的是 {fingerprint}，文件现在是 sha256:{digest[:12]}（文件可能被改过）")
    try:
        return Source(True, text=data.decode("utf-8"))
    except UnicodeDecodeError:
        return _fail(f"{path} 不是 UTF-8 文本")
