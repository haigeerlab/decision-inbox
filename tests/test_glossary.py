"""Glossary v1.1 (spec/glossary-rename.md): no old name in anything shown to people.

Contract message tags (【…】) and contract field names stay as the contract writes them, so they are
stripped before looking; everything else that still says an old name is a failure, unless listed in
ALLOWED with the reason.
"""

import ast
import re
import unittest
from pathlib import Path

from decision_inbox import protocol

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "decision_inbox"

# Old name -> new name (术语表 v1.1). 事项 is handled separately: compounds that are glossary terms pass.
OLD = {
    "收件枢纽": "决策收件箱", "总协调": "跨线协调", "负责人": "审查者", "短名": "线名", "身份名": "邮箱名",
    "协调会话": "模块协调", "并行协调": "模块协调", "适用会话": "适用的线", "等待单": "等待记录",
    "已恢复": "已结项", "约定块": "协作规则段", "用户答复": "你的答复", "待用户决定": "待你决定",
    "审批": "批准", "评审": "审查",
}
_ITEM = re.compile(r"(?<!待决)(?<!多线)(?<!单线)事项")
_FIELD_NAMES = {name for names in protocol.FIELDS.values() for name in names}
_TAG = re.compile(r"【[^】]*】")
_QUOTED_FIELD = re.compile(r"[「『](" + "|".join(map(re.escape, sorted(_FIELD_NAMES, key=len, reverse=True))) + r")[」』：:]")
_PROBLEM_CODE = re.compile(r"^[a-z][a-z-]*:")  # stable issue codes such as missing-field:事项 (protocol.PROBLEM_CODES)
_LINE_FIELD = re.compile(r"^(\s*[-*]?\s*)(" + "|".join(map(re.escape, sorted(_FIELD_NAMES, key=len, reverse=True)))
                         + r")[：:]", re.M)

# (where, old name) -> why it may stay. `where` is a file name relative to the repo, or "module.py:literal".
# KIND_TAGS keys are the contract's tag names and are always skipped.
ALLOWED: dict[tuple[str, str], str] = {
    ("store.py:literal", "收件枢纽"): "OLD_HUB_NAMES：旧组名册里存的收件箱线名，读出时换成决策收件箱",
    ("protocol.py:literal", "负责人"): "【答复告知】的说明行是契约 v2.1 生成样例原文（answer-notice/basic.json），契约改标签前不动",
    ("tickets.py:literal", "收件枢纽"): "USER_TARGETS 兼容旧写法：线写「在等谁：收件枢纽」照样认作等用户",
}


def strip_contract(text: str) -> str:
    """Remove what the contract fixes: 【tags】, 「field names」, and `field：` at line start."""
    text = _TAG.sub("", text)
    text = _QUOTED_FIELD.sub("", text)
    return _LINE_FIELD.sub(r"\1", text)


def old_terms(text: str) -> list[tuple[str, str]]:
    """(old name, line) for every old name left once the contract's own words are removed."""
    hits = []
    for line in strip_contract(text).splitlines():
        hits += [(old, line.strip()) for old in OLD if old in line]
        if _ITEM.search(line):
            hits.append(("事项", line.strip()))
    return hits


def _docstrings(tree) -> set[int]:
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                ids.add(id(first.value))
    return ids


def _kind_tag_keys(tree) -> set[int]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "KIND_TAGS" for t in node.targets):
            return {id(k) for k in node.value.keys}
    return set()


def literal_hits(path: Path) -> list[tuple[str, str]]:
    """Old names in a module's string literals (not docstrings, not comments, not bare field names)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    skip, tag_keys = _docstrings(tree), _kind_tag_keys(tree)
    hits = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)) or id(node) in skip:
            continue
        if node.value in _FIELD_NAMES or id(node) in tag_keys or _PROBLEM_CODE.match(node.value):
            continue
        hits += [(old, line) for old, line in old_terms(node.value) if (f"{path.name}:literal", old) not in ALLOWED]
    return hits


def file_hits(rel: str) -> list[tuple[str, str]]:
    text = (ROOT / rel).read_text(encoding="utf-8")
    return [(old, line) for old, line in old_terms(text) if (rel, old) not in ALLOWED]


def _report(hits) -> str:
    return "\n".join(f"  {old} → {OLD.get(old, '待决事项')}：{line}" for old, line in hits[:40])


class HelperTest(unittest.TestCase):
    def test_tags_and_fields_are_not_hits(self):
        self.assertEqual(old_terms("发【已恢复】，写「适用会话」一行"), [])
        self.assertEqual(old_terms("事项：#3\n适用会话：前端、API"), [])

    def test_compound_item_names_pass(self):
        self.assertEqual(old_terms("多线事项、单线事项和待决事项"), [])

    def test_old_names_hit(self):
        self.assertEqual([o for o, _ in old_terms("收件枢纽里有 2 个事项")], ["收件枢纽", "事项"])
        self.assertEqual([o for o, _ in old_terms("等待单 #3 已恢复")], ["等待单", "已恢复"])

    def test_docstrings_and_field_constants_are_skipped(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "m.py"
            src.write_text('"""收件枢纽"""\nKIND_TAGS = {"已恢复": "resumed"}\nF = ("适用会话",)\n'
                           'X = "看事项"\n', encoding="utf-8")
            self.assertEqual(literal_hits(src), [("事项", "看事项")])


def _module_test(name):
    def test(self):
        hits = literal_hits(PACKAGE / name)
        self.assertFalse(hits, f"{name} 里还有旧称：\n{_report(hits)}")
    return test


def _file_test(rel):
    def test(self):
        hits = file_hits(rel)
        self.assertFalse(hits, f"{rel} 里还有旧称：\n{_report(hits)}")
    return test


# Areas still being renamed are marked expectedFailure; each task removes its own (plan Task 1).
PENDING = {
    "__main__.py", "doctor.py", "health.py", "hub.py", "items.py", "onboard.py", "patrol.py", "protocol.py",
    "query.py", "stall.py", "stophook.py", "tickets.py", "view.py", "approval.py", "mapview.py", "crew.py",
    "install.py", "store.py", "reviews.py", "relay.py", "specguard.py", "sources.py", "deps.py", "consume.py",
    "README.md", "skills/decision-inbox-join/SKILL.md",
    *(f"commands/{p.name}" for p in (ROOT / "commands").glob("*.md")),
}


class ScanTest(unittest.TestCase):
    pass


for _path in sorted(PACKAGE.glob("*.py")):
    _t = _module_test(_path.name)
    setattr(ScanTest, f"test_module_{_path.stem}", unittest.expectedFailure(_t) if _path.name in PENDING
            and literal_hits(_path) else _t)

for _rel in ["README.md", "skills/decision-inbox-join/SKILL.md",
             *sorted(f"commands/{p.name}" for p in (ROOT / "commands").glob("*.md"))]:
    _t = _file_test(_rel)
    _name = "test_file_" + re.sub(r"\W", "_", _rel)
    setattr(ScanTest, _name, unittest.expectedFailure(_t) if _rel in PENDING and file_hits(_rel) else _t)


if __name__ == "__main__":
    unittest.main()
