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


from helpers import TempHomeTestCase  # noqa: E402

from decision_inbox import store, tickets  # noqa: E402


class WiringTest(TempHomeTestCase):
    """crew-line-status Task 3: every entry point reads the coordinator's modules."""

    def setUp(self):
        super().setUp()
        self.tmp = Path(tempfile.mkdtemp(prefix="di-crew-cli-"))
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        self._old = os.environ.get("DECISION_INBOX_PLUGINS_FILE")
        os.environ["DECISION_INBOX_PLUGINS_FILE"] = str(self.tmp / "installed_plugins.json")
        self.g, _ = store.init_group("demo")
        with self.g.transaction() as tx:
            tx.add_session({"relayName": "hub", "shortName": "收件枢纽", "role": "hub", "line": [],
                            "host": "claude-desktop"})
            tx.add_session({"relayName": "coord", "shortName": "门店", "role": "dev", "line": ["门店"],
                            "host": "claude-desktop", "repo": str(self.repo), "crewCoordinator": True})
        tickets.receive(self.g, "【等待其他会话】\n结束：无\n在等谁：API\n等什么：接口\n", sender="coord",
                        relay_id=1, sent_at="2026-10-18T10:00:00+08:00")

    def tearDown(self):
        if self._old is None:
            os.environ.pop("DECISION_INBOX_PLUGINS_FILE", None)
        else:
            os.environ["DECISION_INBOX_PLUGINS_FILE"] = self._old
        shutil.rmtree(self.tmp, ignore_errors=True)
        super().tearDown()

    def agents(self, busy=True):
        rows = [{"name": "coord", "host": {"app": "claude"}, "unread": 0, "lastActivity": None,
                 "presence": {"state": "running", "activity": "idle"}},
                {"name": "shop-a", "host": {"app": "claude"}, "unread": 0, "lastActivity": None,
                 "presence": {"state": "running", "activity": "busy" if busy else "idle"}}]
        path = self.tmp / f"agents-{os.urandom(4).hex()}.json"
        path.write_text(json.dumps({"count": len(rows), "agents": rows}), encoding="utf-8")
        return str(path)

    def cli(self, *argv):
        import contextlib
        import io
        from decision_inbox.__main__ import main
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(argv))
        self.assertEqual(code, 0, err.getvalue())
        return out.getvalue()

    def test_lines_view_and_reply_show_modules(self):
        FakeCrew(self.tmp)
        want = "干活中（模块 a 在忙·构建、b 挂起：等接口；还在等 API #1）"
        self.assertIn(want, self.cli("query", "lines", "demo", "--agents", self.agents()))
        self.assertIn(want, self.cli("view", "demo", "--agents", self.agents()))
        text = self.tmp / "said.txt"
        text.write_text("卡住了吗", encoding="utf-8")
        shown = json.loads(self.cli("inbox", "reply", "demo", "--text-file", str(text), "--agents", self.agents()))
        self.assertIn(want, shown["show"])

    def test_patrol_gives_no_all_waiting_verdict_when_unknown(self):
        FakeCrew(self.tmp, out="", code=2, err="状态库还没建")
        out = self.tmp / "plan.json"
        self.cli("patrol", "plan", "demo", "--agents", self.agents(busy=False), "--out", str(out))
        self.assertNotIn("all-waiting", json.dumps(json.loads(out.read_text(encoding="utf-8"))))
        self.assertIn("模块状态未知：状态库还没建", self.cli("view", "demo", "--agents", self.agents(busy=False)))
