"""stage-c-fixes DI-11: patrol-watch, a launchd job outside the hub and the patrol session."""

import os
import subprocess
import sys

from helpers import REPO, TempHomeTestCase

from decision_inbox import store, watch

SESSION = "local_patrol-1"


def at(minute: int) -> str:
    return f"2026-10-20T01:{minute:02d}:00+00:00"


class WatchTest(TempHomeTestCase):
    def setUp(self):
        super().setUp()
        self.g, _ = store.init_group("demo")
        self.sent = []
        with self.g.transaction() as tx:
            tx.write_state("onboarding", {"patrolSession": SESSION, "patrolSessionAt": at(0)})
            tx.write_state("patrol", {"lastRunAt": at(0)})

    def send(self, title, text):
        self.sent.append((title, text))
        return True

    def run_at(self, minute):
        return watch.check(self.g, at(minute), send=self.send)

    def test_notifies_once_then_every_thirty_minutes_until_back(self):
        self.assertIsNone(self.run_at(10))
        self.run_at(20)
        self.assertEqual(len(self.sent), 1)
        title, text = self.sent[0]
        self.assertEqual(title, "决策收件箱：巡视停了")
        self.assertIn("巡视 20 分钟没跑", text)
        self.assertIn(f"claude://claude.ai/epitaxy/{SESSION}", text)
        self.assertNotIn("来源：", text)
        self.run_at(30)
        self.assertEqual(len(self.sent), 1)
        self.run_at(55)
        self.assertEqual(len(self.sent), 2)
        with self.g.transaction() as tx:
            tx.write_state("patrol", {"lastRunAt": at(56)})
        self.run_at(58)
        self.assertEqual(len(self.sent), 2)
        self.assertNotIn("lastNotifiedAt", store.read_state(self.g, "patrol-watch"))

    def test_failed_send_is_tried_again_next_run(self):
        watch.check(self.g, at(20), send=lambda title, text: False)
        self.run_at(25)
        self.assertEqual(len(self.sent), 1)

    def test_no_patrol_registered_is_quiet(self):
        with self.g.transaction() as tx:
            tx.write_state("onboarding", {})
        self.assertIsNone(self.run_at(59))
        self.assertEqual(self.sent, [])


class WatchCommandTest(TempHomeTestCase):
    def test_command_runs_the_notifier_and_never_fails_launchd(self):
        g, _ = store.init_group("demo")
        with g.transaction() as tx:
            tx.write_state("onboarding", {"patrolSession": SESSION, "patrolSessionAt": "2026-10-01T00:00:00Z"})
        log = self.home / "osascript.log"
        fake = self.home / "osascript"
        fake.write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" >> "{log}"\n', encoding="utf-8")
        fake.chmod(0o755)
        env = {**os.environ, "DECISION_INBOX_OSASCRIPT": str(fake), "PYTHONPATH": str(REPO)}
        r = subprocess.run([sys.executable, "-m", "decision_inbox", "patrol-watch", "demo"], env=env,
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("巡视还没跑完过一轮", log.read_text(encoding="utf-8"))
        r = subprocess.run([sys.executable, "-m", "decision_inbox", "patrol-watch", "nope"], env=env,
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0)
        self.assertIn("nope", r.stderr)


class InstallTest(TempHomeTestCase):
    """stage-c-fixes acceptance 5: the launchd job is previewed, written on confirm, removed by teardown."""

    def setUp(self):
        super().setUp()
        self.g, _ = store.init_group("demo")
        self.agents = self.home / "LaunchAgents"
        self.log = self.home / "launchctl.log"
        fake = self.home / "launchctl"
        # `print` answers 0 only while the last bootstrap/bootout was a bootstrap, like the real one
        fake.write_text(f'#!/bin/sh\necho "$@" >> "{self.log}"\n'
                        f'if [ "$1" = print ]; then grep -E "^boot(strap|out)" "{self.log}" | tail -1 | grep -q bootstrap; fi\n',
                        encoding="utf-8")
        fake.chmod(0o755)
        self._env = {k: os.environ.get(k) for k in ("DECISION_INBOX_LAUNCH_AGENTS", "DECISION_INBOX_LAUNCHCTL")}
        os.environ["DECISION_INBOX_LAUNCH_AGENTS"] = str(self.agents)
        os.environ["DECISION_INBOX_LAUNCHCTL"] = str(fake)

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        super().tearDown()

    def calls(self):
        return self.log.read_text(encoding="utf-8").splitlines() if self.log.is_file() else []

    def test_preview_writes_nothing(self):
        plan = watch.install("demo", confirm=False)
        self.assertEqual(plan.path, self.agents / "com.haigeerlab.decision-inbox.patrol-watch.demo.plist")
        self.assertIn("<string>patrol-watch</string>", plan.content)
        self.assertIn("<integer>300</integer>", plan.content)
        self.assertFalse(plan.path.exists())
        self.assertEqual(self.calls(), [])

    def test_confirm_writes_and_loads_then_remove_unloads(self):
        from decision_inbox import install as inst
        plan = watch.install("demo", confirm=True)
        self.assertTrue(plan.path.is_file())
        self.assertIn(f"<string>{inst.cli()}</string>", plan.path.read_text(encoding="utf-8"))
        self.assertTrue(any(c.startswith("bootstrap gui/") and c.endswith(str(plan.path)) for c in self.calls()))
        self.assertTrue(watch.loaded("demo"))
        self.assertTrue(watch.uninstall("demo", confirm=True))
        self.assertFalse(plan.path.exists())
        self.assertTrue(any(c.startswith("bootout gui/") for c in self.calls()))
        self.assertFalse(watch.uninstall("demo", confirm=True))

    def test_hub_steps_and_teardown(self):
        from decision_inbox import onboard
        project = self.home / "hub"
        project.mkdir()
        out = onboard.hub("demo", "demo-hub", "local_hub", project, confirm=True, now="2026-10-20T00:00:00Z")
        self.assertTrue(any("onboard watch demo" in s and "--confirm" in s for s in out.steps))
        watch.install("demo", confirm=True)
        out = onboard.teardown("demo", project, confirm=False, now="2026-10-20T01:00:00Z")
        self.assertTrue(any("巡视提醒" in s for s in out.steps))
        self.assertTrue(watch.plist_path("demo").exists())
        out = onboard.teardown("demo", project, confirm=True, now="2026-10-20T01:00:00Z")
        self.assertFalse(watch.plist_path("demo").exists())
        self.assertTrue(any("巡视提醒" in w for w in out.written))

    def test_doctor(self):
        from decision_inbox import doctor
        self.assertEqual(doctor._patrol_watch("demo").state, "bad")
        self.assertIn("onboard watch demo", doctor._patrol_watch("demo").fix)
        watch.install("demo", confirm=True)
        self.assertEqual(doctor._patrol_watch("demo").state, "ok")


class WatchOnboardCommandTest(InstallTest):
    def run_cli(self, *args):
        env = {**os.environ, "PYTHONPATH": str(REPO)}
        return subprocess.run([sys.executable, "-m", "decision_inbox", "onboard", "watch", "demo", *args], env=env,
                              capture_output=True, text=True, timeout=30)

    def test_preview_then_confirm(self):
        r = self.run_cli()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("这是预览", r.stdout)
        self.assertFalse(watch.plist_path("demo").exists())
        r = self.run_cli("--confirm")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("已加载", r.stdout)
        self.assertTrue(watch.plist_path("demo").exists())
