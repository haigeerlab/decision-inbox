import json
import os
import shutil
import stat
import tempfile
import unittest
from pathlib import Path

from decision_inbox import crew

INTERFACE = {"interface": "1.0", "plugin": "module-crew", "version": "0.0.1", "contract": "1.7",
             "sessions": {"command": ["bin/module-crew", "sessions", "--json"], "schemaVersion": 1}}
SESSIONS = {"schemaVersion": 1, "sessions": [
    {"module": "a", "relayName": "shop-a", "worktree": "/w/a", "stage": "build", "stageText": "可以构建",
     "suspended": None, "lastActivity": "2026-10-18T12:00:00+08:00", "ago": "3 分钟"},
    {"module": "b", "relayName": "shop-b", "worktree": "/w/b", "stage": "wait-merge", "stageText": "等合并",
     "suspended": "等接口", "lastActivity": None},
]}


class FakeCrew:
    """A module-crew install in a temp dir: interface.json plus a script that prints `out`."""

    def __init__(self, tmp: Path, interface=INTERFACE, out=SESSIONS, code=0, err="", sleep=0):
        self.root = tmp / "module-crew" / "0.0.1"
        (self.root / "bin").mkdir(parents=True)
        if interface is not None:
            (self.root / "interface.json").write_text(
                interface if isinstance(interface, str) else json.dumps(interface), encoding="utf-8")
        body = out if isinstance(out, str) else json.dumps(out)
        script = self.root / "bin" / "module-crew"
        script.write_text(
            "#!/usr/bin/env python3\nimport os, sys, time\n"
            f"time.sleep({sleep})\n"
            "open(os.path.join(os.environ['CREW_LOG'], 'cwd'), 'w').write(os.getcwd()) if os.environ.get('CREW_LOG') else None\n"
            f"sys.stdout.write({body!r})\nsys.stderr.write({err!r})\nsys.exit({code})\n", encoding="utf-8")
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
        records = tmp / "installed_plugins.json"
        records.write_text(json.dumps({"version": 2, "plugins": {"module-crew@m": [
            {"scope": "user", "installPath": str(self.root), "version": "0.0.1"}]}}), encoding="utf-8")


class CrewCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="di-crew-"))
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        self._old = {k: os.environ.get(k) for k in ("DECISION_INBOX_PLUGINS_FILE", "CREW_LOG")}
        os.environ["DECISION_INBOX_PLUGINS_FILE"] = str(self.tmp / "installed_plugins.json")

    def tearDown(self):
        for k, v in self._old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    def read(self, **kw):
        FakeCrew(self.tmp, **kw)
        return crew.read_modules(str(self.repo), timeout=kw.get("sleep", 0) and 0.5 or 3.0)


class ReadModulesTest(CrewCase):
    def test_reads_contract_fields_in_the_repo(self):
        os.environ["CREW_LOG"] = str(self.tmp)
        r = self.read()
        self.assertEqual(r.status, "ok", r.reason)
        self.assertEqual(r.modules, (crew.Module("a", "shop-a", "build", None),
                                     crew.Module("b", "shop-b", "wait-merge", "等接口")))
        self.assertEqual(os.path.realpath((self.tmp / "cwd").read_text()), os.path.realpath(self.repo))

    def test_unknown_stage_is_kept(self):
        out = {"schemaVersion": 1, "sessions": [dict(SESSIONS["sessions"][0], stage="review")]}
        r = self.read(out=out)
        self.assertEqual((r.status, r.modules[0].stage), ("ok", "review"))

    def assertUnknown(self, r, words):
        self.assertEqual(r.status, "unknown")
        self.assertEqual(r.modules, ())
        self.assertIn(words, r.reason)

    def test_not_installed(self):
        (self.tmp / "installed_plugins.json").write_text(json.dumps({"version": 2, "plugins": {}}))
        self.assertUnknown(crew.read_modules(str(self.repo)), "没有安装 module-crew")

    def test_interface_major(self):
        self.assertUnknown(self.read(interface=dict(INTERFACE, interface="2.0")), "接口版本 2.0")

    def test_no_interface(self):
        self.assertUnknown(self.read(interface=None), "interface.json")

    def test_sessions_schema_in_interface(self):
        bad = dict(INTERFACE, sessions=dict(INTERFACE["sessions"], schemaVersion=2))
        self.assertUnknown(self.read(interface=bad), "schemaVersion 2")

    def test_sessions_schema_in_output(self):
        self.assertUnknown(self.read(out=dict(SESSIONS, schemaVersion=2)), "schemaVersion 2")

    def test_exit_code_two_gives_stderr(self):
        self.assertUnknown(self.read(out="", code=2, err="❌ /x 不在 git 仓库里\n第二行"), "不在 git 仓库里")

    def test_timeout(self):
        self.assertUnknown(self.read(sleep=2), "秒没有结束")

    def test_bad_json(self):
        self.assertUnknown(self.read(out="{oops"), "读不懂")

    def test_missing_field(self):
        broken = {"schemaVersion": 1, "sessions": [{"module": "a", "stage": "build", "suspended": None}]}
        self.assertUnknown(self.read(out=broken), "relayName")

    def test_command_must_stay_in_plugin_root(self):
        for first in ("../../../bin/sh", "/bin/sh", ""):
            with self.subTest(first=first):
                shutil.rmtree(self.tmp / "module-crew", ignore_errors=True)
                bad = dict(INTERFACE, sessions=dict(INTERFACE["sessions"], command=[first, "-c", "echo hi"]))
                self.assertUnknown(self.read(interface=bad), "插件目录")


if __name__ == "__main__":
    unittest.main()
