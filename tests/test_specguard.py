import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from decision_inbox import specguard

FIX = Path(__file__).resolve().parent / "fixtures" / "specguard"


class LocateCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="di-sg-"))
        self.records = self.tmp / "installed_plugins.json"
        self._old = os.environ.get("DECISION_INBOX_PLUGINS_FILE")
        os.environ["DECISION_INBOX_PLUGINS_FILE"] = str(self.records)
        self.project = self.tmp / "repo"
        self.project.mkdir()

    def tearDown(self):
        if self._old is None:
            os.environ.pop("DECISION_INBOX_PLUGINS_FILE", None)
        else:
            os.environ["DECISION_INBOX_PLUGINS_FILE"] = self._old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def install(self, name, version, script=True):
        root = self.tmp / name / version
        (root / "hooks").mkdir(parents=True)
        if script:
            (root / "hooks" / "map_view.py").write_text("print('{}')\n", encoding="utf-8")
        return root

    def write_records(self, entries):
        self.records.write_text(json.dumps({"version": 2, "plugins": entries}), encoding="utf-8")


class LocateTest(LocateCase):
    def test_user_scope(self):
        root = self.install("user", "0.63.0")
        self.write_records({"spec-guard@spec-guard-marketplace": [
            {"scope": "user", "installPath": str(root), "version": "0.63.0"}]})
        found = specguard.locate(project=str(self.project))
        self.assertIsInstance(found, specguard.Located)
        self.assertEqual((found.path, found.version), (str(root / "hooks" / "map_view.py"), "0.63.0"))

    def test_project_scope_wins(self):
        user = self.install("user", "0.63.0")
        local = self.install("local", "0.62.0")
        other = self.install("other", "0.61.0")
        self.write_records({"spec-guard@m": [
            {"scope": "user", "installPath": str(user), "version": "0.63.0"},
            {"scope": "local", "projectPath": str(self.tmp / "elsewhere"), "installPath": str(other), "version": "0.61.0"},
            {"scope": "local", "projectPath": str(self.project), "installPath": str(local), "version": "0.62.0"}]})
        found = specguard.locate(project=str(self.project))
        self.assertEqual(found.version, "0.62.0")

    def test_missing_cases_have_distinct_reasons(self):
        reasons = set()
        found = specguard.locate(project=str(self.project))           # no records file
        self.assertIsInstance(found, specguard.Missing)
        reasons.add(found.reason)
        self.write_records({"agent-relay@m": [{"scope": "user", "installPath": "/x", "version": "1"}]})
        found = specguard.locate(project=str(self.project))           # no spec-guard entry
        self.assertIsInstance(found, specguard.Missing)
        reasons.add(found.reason)
        root = self.install("user", "0.63.0", script=False)
        self.write_records({"spec-guard@m": [{"scope": "user", "installPath": str(root), "version": "0.63.0"}]})
        found = specguard.locate(project=str(self.project))           # script missing
        self.assertIsInstance(found, specguard.Missing)
        reasons.add(found.reason)
        self.assertEqual(len(reasons), 3)


if __name__ == "__main__":
    unittest.main()
