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
        self.assertIn(f"{install.cli()} onboard task demo", "\n".join(preview.steps))
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
