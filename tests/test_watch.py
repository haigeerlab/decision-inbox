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
