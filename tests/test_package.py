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
        banned = {"unlink", "rmtree", "truncate", "remove", "rmdir"}
        for path in _sources():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    fn = node.func
                    name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                    self.assertNotIn(name, banned, f"{path.name}:{node.lineno} calls {name}")


if __name__ == "__main__":
    unittest.main()
