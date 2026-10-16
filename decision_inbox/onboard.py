"""Join and leave a collaboration group (see spec/onboarding.md).

Convention blocks are placed into and stripped from a project's rules file
as plain text, so everything outside the block stays byte for byte.
"""

from __future__ import annotations

import re

_MARK_RE = re.compile(r"^<!-- (BEGIN|END) decision-inbox ([a-z]+) -->$")


class BlockConflict(ValueError):
    """The rules file holds another role's block or broken markers; nothing is guessed."""


def _find(lines: list[str]) -> tuple[int, int, str] | None:
    """(begin index, end index, role) of the one decision-inbox block, or None."""
    marks = [(i, *m.groups()) for i, line in enumerate(lines) if (m := _MARK_RE.match(line.rstrip("\n")))]
    if not marks:
        return None
    if len(marks) != 2 or marks[0][1] != "BEGIN" or marks[1][1] != "END" or marks[0][2] != marks[1][2]:
        raise BlockConflict("规则文件里的 decision-inbox 标记不成对或不止一块，请手动检查")
    return marks[0][0], marks[1][0], marks[0][2]


def place(text: str, role: str, block: str) -> str:
    """Put `block` into `text`: append it, or replace the same role's block in place."""
    lines = text.splitlines(keepends=True)
    found = _find(lines)
    if found is None:
        if not text:
            return block
        return (text if text.endswith("\n") else text + "\n") + "\n" + block
    begin, end, existing = found
    if existing != role:
        raise BlockConflict(f"规则文件里已有 decision-inbox 的 {existing} 约定块，请先卸载")
    return "".join(lines[:begin]) + block + "".join(lines[end + 1:])


def strip(text: str) -> tuple[str, bool]:
    """Remove the decision-inbox block and the blank line `place` put next to it."""
    lines = text.splitlines(keepends=True)
    found = _find(lines)
    if found is None:
        return text, False
    begin, end, _ = found
    if end + 1 < len(lines) and lines[end + 1] == "\n":
        end += 1
    elif end + 1 == len(lines) and begin > 0 and lines[begin - 1] == "\n":
        begin -= 1
    return "".join(lines[:begin] + lines[end + 1:]), True
