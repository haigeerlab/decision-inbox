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
        self.assertEqual((reader.status, reader.step), ("in_progress", "build"))
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


FAKE = """import json, sys, time
from pathlib import Path
b = json.loads((Path(__file__).parent / "behavior.json").read_text(encoding="utf-8"))
time.sleep(b.get("sleep", 0))
sys.stdout.write(b.get("stdout", ""))
sys.stderr.write(b.get("stderr", ""))
sys.exit(b.get("code", 0))
"""


class ReadLineTest(LocateCase):
    def setUp(self):
        super().setUp()
        root = self.install("user", "0.63.0")
        (root / "hooks" / "map_view.py").write_text(FAKE, encoding="utf-8")
        self.behavior = root / "hooks" / "behavior.json"
        self.write_records({"spec-guard@m": [{"scope": "user", "installPath": str(root), "version": "0.63.0"}]})

    def behave(self, **kw):
        self.behavior.write_text(json.dumps(kw), encoding="utf-8")
        return specguard.read_line(project=str(self.project), timeout=kw.pop("timeout", 5) if "timeout" in kw else 5)

    def test_ok(self):
        r = self.behave(stdout=fixture("map-0.63.json"))
        self.assertEqual((r.status, r.reason, r.exit_code), ("ok", None, 0))
        self.assertEqual(r.map.generator_version, "0.63.0")

    def test_exit_codes(self):
        r = self.behave(code=2, stderr="map-view: 项目路径不存在或不是目录：/x\n")
        self.assertEqual((r.status, r.exit_code), ("bad-args", 2))
        self.assertIn("项目路径不存在", r.reason)
        r = self.behave(code=3, stdout=json.dumps({"schemaVersion": 1, "error": "no-capability-map"}))
        self.assertEqual((r.status, r.reason), ("no-map", "无能力图"))
        r = self.behave(code=4, stdout=json.dumps({"schemaVersion": 1, "error": "unreadable", "detail": "todo 编码错误"}))
        self.assertEqual(r.status, "unreadable")
        self.assertIn("todo 编码错误", r.reason)
        r = self.behave(code=1, stderr="Traceback " + "x" * 500)
        self.assertEqual(r.status, "bad-output")
        self.assertLessEqual(len(r.reason), 260)
        self.assertIn("Traceback", r.reason)

    def test_bad_json_and_schema(self):
        self.assertEqual(self.behave(stdout="hello").status, "bad-output")
        self.assertEqual(self.behave(stdout=json.dumps({"schemaVersion": 2, "modules": []})).status, "schema-mismatch")

    def test_timeout(self):
        self.behavior.write_text(json.dumps({"sleep": 3}), encoding="utf-8")
        r = specguard.read_line(project=str(self.project), timeout=1)
        self.assertEqual((r.status, r.exit_code), ("timeout", None))

    def test_bad_project_does_not_spawn(self):
        self.behavior.write_text(json.dumps({"stdout": fixture("map-0.63.json")}), encoding="utf-8")
        for project in (str(self.tmp / "nope"), "relative/path"):
            with self.subTest(project=project):
                r = specguard.read_line(project=project)
                self.assertEqual((r.status, r.exit_code), ("bad-args", None))

    def test_not_installed(self):
        self.write_records({})
        r = specguard.read_line(project=str(self.project))
        self.assertEqual((r.status, r.exit_code), ("not-installed", None))


class IntegrationTest(unittest.TestCase):
    """Runs the spec-guard actually installed on this machine against this repository."""

    def test_real_spec_guard_reads_this_repo(self):
        repo = str(Path(__file__).resolve().parent.parent)
        old = os.environ.pop("DECISION_INBOX_PLUGINS_FILE", None)
        try:
            found = specguard.locate(project=repo)
            if isinstance(found, specguard.Missing):
                self.skipTest(f"本机没有可用的 spec-guard：{found.reason}")
            r = specguard.read_line(project=repo)
        finally:
            if old is not None:
                os.environ["DECISION_INBOX_PLUGINS_FILE"] = old
        self.assertEqual(r.status, "ok", r.reason)
        self.assertEqual(r.map.generator_version, found.version)
        self.assertIn("group-store", [m.id for m in r.map.modules])


class NoShellTest(unittest.TestCase):
    def test_no_shell_true(self):
        import ast
        tree = ast.parse((Path(specguard.__file__)).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg == "shell":
                self.fail("specguard.py must not pass shell=")


if __name__ == "__main__":
    unittest.main()


class InterfaceTest(LocateCase):
    """doctor-and-observer Task 1: read spec-guard through its interface.json."""

    def setUp(self):
        super().setUp()
        self.root = self.install("user", "0.67.0", script=False)
        (self.root / "hooks" / "mv2.py").write_text(FAKE, encoding="utf-8")
        (self.root / "hooks" / "map_view.py").write_text(FAKE, encoding="utf-8")
        (self.root / "hooks" / "behavior.json").write_text(
            json.dumps({"stdout": fixture("map-0.63.json")}), encoding="utf-8")
        self.write_records({"spec-guard@m": [{"scope": "user", "installPath": str(self.root), "version": "0.67.0"}]})

    def write_interface(self, text):
        (self.root / "interface.json").write_text(text, encoding="utf-8")

    def iface(self, version="1.0", script="hooks/mv2.py"):
        return json.dumps({"interface": version, "mapView": {
            "command": ["python3", "-B", script, "--json", "--project", "<project-root>"], "schemaVersion": 1}})

    def test_command_from_interface(self):
        self.write_interface(self.iface())
        found = specguard.locate(project=str(self.project))
        self.assertIsInstance(found, specguard.Located)
        self.assertEqual(found.path, str(self.root / "hooks" / "mv2.py"))
        self.assertEqual((found.interface.state, found.interface.version), ("ok", "1.0"))
        self.assertEqual(specguard.read_line(project=str(self.project)).status, "ok")

    def test_absent_and_unreadable_fall_back(self):
        found = specguard.locate(project=str(self.project))
        self.assertEqual((found.path, found.interface.state), (str(self.root / "hooks" / "map_view.py"), "absent"))
        self.write_interface("{not json")
        found = specguard.locate(project=str(self.project))
        self.assertEqual((found.path, found.interface.state), (str(self.root / "hooks" / "map_view.py"), "unreadable"))
        self.assertEqual(specguard.read_line(project=str(self.project)).status, "ok")

    def test_incompatible_major_is_not_read(self):
        self.write_interface(self.iface(version="2.0"))
        found = specguard.locate(project=str(self.project))
        self.assertIsInstance(found, specguard.Incompatible)
        r = specguard.read_line(project=str(self.project))
        self.assertEqual(r.status, "incompatible")
        self.assertEqual(r.reason, "spec-guard 接口版本不兼容（2.0），本插件只认 1.x")
        self.assertNotIn("没", r.reason)

    def test_unknown_schema_version_in_interface_is_incompatible(self):
        self.write_interface(json.dumps({"interface": "1.1", "mapView": {
            "command": ["python3", "-B", "hooks/mv2.py", "--json", "--project", "<project-root>"], "schemaVersion": 2}}))
        r = specguard.read_line(project=str(self.project))
        self.assertEqual(r.status, "incompatible")
        self.assertIn("schemaVersion 2", r.reason)
