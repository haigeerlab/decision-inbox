import os
import subprocess
import time
import unittest

from helpers import REPO, TempHomeTestCase

from decision_inbox import hub, install, onboard, patrol

NOW = "2026-10-17T01:00:00Z"
HUB_DESKTOP = "local_00000000-0000-0000-0000-00000000hub0"


class ShimTest(TempHomeTestCase):
    def test_path_and_cli(self):
        self.assertEqual(install.shim_path(), self.home / "bin" / "decision-inbox")
        self.assertEqual(install.cli(), str(self.home / "bin" / "decision-inbox"))

    def test_write_then_unchanged(self):
        self.assertTrue(install.write_shim(REPO))
        shim = install.shim_path()
        self.assertTrue(os.access(shim, os.X_OK))
        self.assertIn(str(REPO / "bin" / "decision-inbox"), shim.read_text(encoding="utf-8"))
        before = shim.stat().st_mtime_ns
        time.sleep(0.01)
        self.assertFalse(install.write_shim(REPO))
        self.assertEqual(shim.stat().st_mtime_ns, before)

    def test_new_plugin_root_rewrites(self):
        install.write_shim(REPO)
        self.assertTrue(install.write_shim(self.home / "other-plugin"))
        self.assertIn(str(self.home / "other-plugin" / "bin" / "decision-inbox"),
                      install.shim_path().read_text(encoding="utf-8"))

    def test_if_installed_without_home_does_nothing(self):
        missing = self.home / "not-here"
        os.environ["DECISION_INBOX_HOME"] = str(missing)
        self.assertFalse(install.write_shim(REPO, if_installed=True))
        self.assertFalse(missing.exists())

    def test_shim_runs_the_plugin(self):
        install.write_shim(REPO)
        env = dict(os.environ, DECISION_INBOX_HOME=str(self.home))
        done = subprocess.run([str(install.shim_path()), "store", "show", "nope"], capture_output=True, text=True,
                              env=env, cwd=self.home, timeout=60)
        self.assertEqual(done.returncode, 2)
        self.assertIn("协作组不存在", done.stderr)

    def test_plugin_root_default(self):
        old = os.environ.pop("DECISION_INBOX_PLUGIN_ROOT", None)
        try:
            self.assertEqual(install.plugin_root(), REPO)
            os.environ["DECISION_INBOX_PLUGIN_ROOT"] = "/opt/plugin"
            self.assertEqual(str(install.plugin_root()), "/opt/plugin")
        finally:
            os.environ.pop("DECISION_INBOX_PLUGIN_ROOT", None)
            if old is not None:
                os.environ["DECISION_INBOX_PLUGIN_ROOT"] = old

    def test_cli_subcommand(self):
        import contextlib
        import io
        from decision_inbox.__main__ import main
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["shim"]), 0)
        self.assertTrue(install.shim_path().is_file())
        os.environ["DECISION_INBOX_HOME"] = str(self.home / "not-here")
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(main(["shim", "--if-installed"]), 0)
        self.assertEqual(out.getvalue(), "")
        self.assertFalse((self.home / "not-here").exists())


class FixedCliTest(TempHomeTestCase):
    def test_defaults_use_the_fixed_path(self):
        cli = install.cli()
        self.assertIn(f"{cli} inbox receive demo", hub.convention("demo"))
        self.assertIn(f"{cli} patrol plan demo", patrol.prompt("demo"))
        self.assertNotIn("python3 -m decision_inbox", hub.convention("demo") + patrol.prompt("demo"))

    def test_onboard_steps_and_shim(self):
        project = self.home / "hub"
        project.mkdir()
        preview = onboard.hub("demo", "di-hub", HUB_DESKTOP, project, confirm=False, now=NOW)
        self.assertFalse(install.shim_path().exists())
        self.assertIn(f"{install.cli()} onboard patrol-session demo", "\n".join(preview.steps))
        self.assertNotIn("python3 -m decision_inbox", "\n".join(preview.steps) + preview.patrol_prompt)
        onboard.hub("demo", "di-hub", HUB_DESKTOP, project, confirm=True, now=NOW)
        self.assertTrue(install.shim_path().is_file())
        fe = self.home / "fe"
        fe.mkdir()
        os.chmod(install.shim_path(), 0o600)
        install.shim_path().write_text("old", encoding="utf-8")
        onboard.join("demo", "dev", "fe-codex", "前端", "codex-desktop", ["前端"], None, fe, None, [], True, NOW)
        self.assertIn("bin/decision-inbox", install.shim_path().read_text(encoding="utf-8"))
        self.assertTrue(os.access(install.shim_path(), os.X_OK))


if __name__ == "__main__":
    unittest.main()


class LocateCase(TempHomeTestCase):
    def setUp(self):
        super().setUp()
        self.hub_dir, self.fe_dir, self.api_dir = (self.home / n for n in ("hub", "fe", "api"))
        for d in (self.hub_dir, self.fe_dir, self.api_dir):
            d.mkdir()
        self.group("demo")

    def group(self, name, fe_dir=None):
        hub_dir = self.hub_dir if name == "demo" else self.home / f"hub-{name}"
        hub_dir.mkdir(exist_ok=True)
        onboard.hub(name, "di-hub", HUB_DESKTOP, hub_dir, True, NOW)
        onboard.join(name, "dev", "fe-codex", "前端", "codex-desktop", ["前端"], None, fe_dir or self.fe_dir,
                     None, [], True, NOW)
        onboard.join(name, "dev", "api-codex", "API", "codex-desktop", ["API"], None, self.api_dir, None, [], True, NOW)

    def run_cli(self, *argv, stdin=""):
        import contextlib
        import io
        import sys
        from unittest import mock
        from decision_inbox.__main__ import main
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), mock.patch.object(sys, "stdin", io.StringIO(stdin)):
            code = main(list(argv))
        return code, out.getvalue(), err.getvalue()


class LocateTest(LocateCase):
    def test_repo_subdir_and_rules_dir(self):
        sub = self.fe_dir / "src" / "pages"
        sub.mkdir(parents=True)
        self.assertEqual([(g, e["relayName"]) for g, e in install.locate(str(self.fe_dir))], [("demo", "fe-codex")])
        self.assertEqual([(g, e["relayName"]) for g, e in install.locate(str(sub))], [("demo", "fe-codex")])
        self.assertEqual([(g, e["relayName"]) for g, e in install.locate(str(self.hub_dir))], [("demo", "di-hub")])
        self.assertEqual(install.locate(str(self.home)), [])

    def test_symlinked_path(self):
        link = self.home / "link-to-fe"
        os.symlink(self.fe_dir, link)
        self.assertEqual([e["relayName"] for _, e in install.locate(str(link))], ["fe-codex"])

    def test_whoami(self):
        import json
        code, out, _ = self.run_cli("whoami", "--cwd", str(self.fe_dir))
        self.assertEqual((code, json.loads(out)), (0, {"group": "demo", "relayName": "fe-codex", "role": "dev"}))
        self.assertEqual(self.run_cli("whoami", "--cwd", str(self.home))[0], 4)
        self.group("other", fe_dir=self.fe_dir)
        code, _, err = self.run_cli("whoami", "--cwd", str(self.fe_dir))
        self.assertEqual(code, 5)
        self.assertIn("demo", err)
        self.assertIn("other", err)


class LeftSessionsTest(LocateCase):
    """Task 6 实测发现：退出后名册还在，钩子不能再拦这个目录。"""

    def test_left_session_is_not_found_until_it_rejoins(self):
        import json
        from decision_inbox import store, tickets
        tickets.receive(store.open_group("demo"), "【等待其他会话】\n结束：无\n在等谁：前端\n等什么：Mock 数据\n",
                        sender="api-codex", relay_id=1, sent_at=NOW)
        onboard.leave("demo", relay_name="fe-codex", project=None, confirm=True, now=NOW)
        self.assertEqual(install.locate(str(self.fe_dir)), [])
        self.assertEqual(self.run_cli("whoami", "--cwd", str(self.fe_dir))[0], 4)
        payload = json.dumps({"cwd": str(self.fe_dir), "stop_hook_active": False})
        self.assertEqual(self.run_cli("hook", "stop", stdin=payload), (0, "", ""))
        self.assertIsNotNone(store.find_session(store.open_group("demo"), relay_name="fe-codex"))
        onboard.join("demo", "dev", "fe-codex", "前端", "codex-desktop", ["前端"], None, self.fe_dir, None, [], True, NOW)
        self.assertEqual([e["relayName"] for _, e in install.locate(str(self.fe_dir))], ["fe-codex"])
        self.assertEqual(json.loads(self.run_cli("hook", "stop", stdin=payload)[1])["decision"], "block")

    def test_leave_preview_marks_nothing(self):
        onboard.leave("demo", relay_name="fe-codex", project=None, confirm=False, now=NOW)
        self.assertEqual([e["relayName"] for _, e in install.locate(str(self.fe_dir))], ["fe-codex"])

    def test_teardown_marks_hub_left(self):
        onboard.teardown("demo", project=None, confirm=True, now=NOW)
        self.assertEqual(install.locate(str(self.hub_dir)), [])


class HookWithoutGroupTest(LocateCase):
    def payload(self, cwd):
        import json
        return json.dumps({"cwd": str(cwd), "stop_hook_active": False})

    def waiting_on_fe(self, group="demo"):
        from decision_inbox import store, tickets
        tickets.receive(store.open_group(group), "【等待其他会话】\n结束：无\n在等谁：前端\n等什么：Mock 数据\n",
                        sender="api-codex", relay_id=1, sent_at=NOW)

    def test_blocks_when_someone_waits(self):
        import json
        self.waiting_on_fe()
        code, out, _ = self.run_cli("hook", "stop", stdin=self.payload(self.fe_dir))
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["decision"], "block")

    def test_not_joined_passes_silently(self):
        self.assertEqual(self.run_cli("hook", "stop", stdin=self.payload(self.home)), (0, "", ""))

    def test_several_groups_pass_with_note(self):
        self.group("other", fe_dir=self.fe_dir)
        self.waiting_on_fe()
        code, out, err = self.run_cli("hook", "stop", stdin=self.payload(self.fe_dir))
        self.assertEqual((code, out), (0, ""))
        self.assertIn("demo", err)
        self.assertIn("other", err)

    def test_with_group_unchanged(self):
        import json
        self.waiting_on_fe()
        code, out, _ = self.run_cli("hook", "stop", "--group", "demo", stdin=self.payload(self.fe_dir))
        self.assertEqual(json.loads(out)["decision"], "block")
