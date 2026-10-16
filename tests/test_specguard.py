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


def fixture(name):
    return (FIX / name).read_text(encoding="utf-8")


class ParseTest(unittest.TestCase):
    def test_0_63_fields(self):
        m = specguard.parse_map(fixture("map-0.63.json"))
        self.assertEqual((m.generator_version, m.stage, m.active_module, m.history),
                         ("0.63.0", "BUILDING", "spec-guard-reader", "complete"))
        self.assertEqual(m.project_root, "/repo/demo")
        self.assertEqual((m.head_branch, m.unmerged_count, m.unmerged_base), ("feature-x", 3, "origin/main"))
        self.assertIsNone(m.unpushed_count)
        self.assertIsNone(m.unpushed_upstream)
        self.assertEqual([x.id for x in m.modules], ["group-store", "spec-guard-reader", "line-health"])
        done = m.modules[0]
        self.assertEqual((done.status, done.position, done.tick_commits), ("done", 1, 7))
        self.assertEqual(done.last_tick_at, "2026-10-16T14:10:44+08:00")
        self.assertEqual(done.first_tick_at, "2026-10-16T14:00:33+08:00")
        reader = m.modules[1]
        self.assertEqual((reader.status, reader.step), ("in_progress", "spec"))
        self.assertIn("line-health", reader.blocks)
        self.assertEqual(m.awaiting_review[0], specguard.AwaitingReview("line-health", "spec", "pending"))
        self.assertEqual(m.totals["done"], 6)

    def test_0_62_shape(self):
        m = specguard.parse_map(fixture("map-0.62.json"))
        self.assertEqual(m.history, "unavailable")
        self.assertIsNone(m.unmerged_count)
        for mod in m.modules:
            self.assertEqual((mod.last_tick_at, mod.first_tick_at, mod.tick_commits, mod.suspended_at),
                             (None, None, None, None))

    def test_bad_inputs(self):
        with self.assertRaises(specguard.BadOutput):
            specguard.parse_map("not json")
        with self.assertRaises(specguard.SchemaMismatch):
            specguard.parse_map(json.dumps({"schemaVersion": 2, "modules": []}))
        with self.assertRaises(specguard.BadOutput):
            specguard.parse_map(json.dumps({"schemaVersion": 1}))


if __name__ == "__main__":
    unittest.main()
