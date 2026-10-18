import ast
import json
import sys
import unittest

from helpers import REPO

PKG = REPO / "decision_inbox"


def _sources():
    files = sorted(PKG.glob("*.py"))
    assert files, "decision_inbox package has no sources"
    return files


class ManifestTest(unittest.TestCase):
    def test_both_manifests_agree(self):
        claude = json.loads((REPO / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        codex = json.loads((REPO / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(claude["name"], "decision-inbox")
        self.assertEqual(codex["name"], "decision-inbox")
        self.assertEqual(claude["version"], codex["version"])


class StaticScanTest(unittest.TestCase):
    def test_stdlib_only_imports(self):
        allowed = set(sys.stdlib_module_names) | {"decision_inbox"}
        for path in _sources():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    if node.level:
                        continue
                    names = [node.module or ""]
                else:
                    continue
                for name in names:
                    self.assertIn(name.split(".")[0], allowed, f"{path.name} imports {name}")

    def test_no_deletion_calls(self):
        """Nothing is ever deleted, except two narrow cases: onboard's _drop_created_rules may unlink a
        rules file the join itself created (e2e-round1-fixes F6), and _consume drops an input file a hub or
        patrol command just read, only under the temp dirs or a group's io/ (p0-field-fixes F-P0-5)."""
        banned = {"unlink", "rmtree", "truncate", "remove", "rmdir"}
        # stall-and-patrol R19: save_snapshot rotates its own copies under the group's io/snapshots, keeping 24
        allowed = {("onboard.py", "_drop_created_rules", "unlink"), ("__main__.py", "_consume", "unlink"),
                   ("patrol.py", "save_snapshot", "unlink")}
        seen = set()
        for path in _sources():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            owners = {}  # node -> innermost enclosing function (walk is breadth-first: outer ones come first)
            for fn in ast.walk(tree):
                if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for node in ast.walk(fn):
                        owners[id(node)] = fn.name
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    fn = node.func
                    name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                    if name not in banned:
                        continue
                    key = (path.name, owners.get(id(node)), name)
                    self.assertIn(key, allowed, f"{path.name}:{node.lineno} calls {name}")
                    seen.add(key)
        self.assertEqual(seen, allowed)


if __name__ == "__main__":
    unittest.main()
