"""patrol-launchd Task 3: the patrol's script identity, the alarm that knows launchd runs the patrol, and the hub
taking the identity's mail without returning or recording it."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import FakeAgentRelay
from test_hub import NOW as HUB_NOW, HubCase, message
from test_onboard import NOW, OnboardCase

from decision_inbox import hub, items, onboard, store


class PatrolIdentityTest(OnboardCase):
    def setUp(self):
        super().setUp()
        self.hub()
        self.fake = FakeAgentRelay(Path(tempfile.mkdtemp(prefix="di-relay-")))
        env = mock.patch.dict(os.environ, self.fake.env())
        env.start()
        self.addCleanup(env.stop)

    def registered(self, *names):
        rows = [{"name": n, "host": {"app": "script"}, "presence": {"state": "stopped"}} for n in names]
        self.fake.answer("agents", json.dumps({"count": len(rows), "agents": rows}))

    def state(self):
        return store.read_state(store.open_group("demo"), "onboarding")

    def test_preview_writes_nothing_and_confirm_records(self):
        self.registered("di-hub-patrol")
        before = self.files()
        out = onboard.patrol_identity("demo", "di-hub-patrol", confirm=False, now=NOW)
        self.assertEqual(self.files(), before)
        self.assertTrue(out.registered)
        self.assertIsNone(out.previous)
        onboard.patrol_identity("demo", "di-hub-patrol", confirm=True, now=NOW)
        self.assertEqual((self.state()["patrolIdentity"], self.state()["patrolIdentityAt"]), ("di-hub-patrol", NOW))

    def test_not_registered_yet_is_only_a_reminder(self):
        self.registered()
        out = onboard.patrol_identity("demo", "di-hub-patrol", confirm=True, now=NOW)
        self.assertFalse(out.registered)
        self.assertEqual(self.state()["patrolIdentity"], "di-hub-patrol")

    def test_relay_unreadable_is_unknown(self):
        self.fake.fail("agents", 3, "down")
        self.assertIsNone(onboard.patrol_identity("demo", "di-hub-patrol", confirm=False, now=NOW).registered)

    def test_a_member_mailbox_name_is_refused(self):
        with self.assertRaises(onboard.JoinError):
            onboard.patrol_identity("demo", "di-hub", confirm=True, now=NOW)
        self.assertNotIn("patrolIdentity", self.state())

    def test_default_name(self):
        self.assertEqual(onboard.default_patrol_identity("di-hub"), "di-hub-patrol")

    def test_command_line(self):
        import contextlib
        import io
        from decision_inbox.__main__ import main
        self.registered()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(["onboard", "patrol-identity", "demo", "--name", "di-hub-patrol"]), 0)
        text = out.getvalue()
        self.assertIn("register-script-identity di-hub-patrol --confirm", text)
        self.assertIn("预览", text)
        self.assertNotIn("patrolIdentity", self.state())
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["onboard", "patrol-identity", "demo", "--name", "di-hub", "--confirm"]), 2)


class LaunchdAlarmTest(HubCase):
    def identity(self, at=None, last_run=None):
        with self.g.transaction() as tx:
            doc = tx.read_state("onboarding")
            doc.update(patrolIdentity="di-hub-patrol", patrolIdentityAt=at or "2026-10-16T04:00:00Z",
                       patrolSession="local_oldpatrol")
            tx.write_state("onboarding", doc)
            if last_run:
                tx.write_state("patrol", {"lastRunAt": last_run})

    def test_launchd_wins_over_an_old_patrol_session(self):
        self.identity(last_run="2026-10-16T05:00:00Z")
        alarm = hub.patrol_alarm(self.g, HUB_NOW)
        self.assertTrue(alarm.startswith("⚠ 巡视 30 分钟没跑："), alarm)
        self.assertIn("doctor", alarm)
        self.assertIn("onboard watch demo --confirm", alarm)
        self.assertNotIn("local_oldpatrol", alarm)
        self.assertTrue(alarm.endswith("（来源：macOS launchd）"), alarm)

    def test_quiet_while_it_runs(self):
        self.identity(last_run="2026-10-16T05:28:00Z")
        self.assertIsNone(hub.patrol_alarm(self.g, HUB_NOW))


class IdentityMailTest(HubCase):
    def setUp(self):
        super().setUp()
        with self.g.transaction() as tx:
            doc = tx.read_state("onboarding")
            doc["patrolIdentity"] = "di-hub-patrol"
            tx.write_state("onboarding", doc)

    def test_only_acknowledged(self):
        wake = message(2001, "di-hub-patrol", "【decision-inbox 巡视】有新的事要告诉用户，请刷新决策收件箱主视图。")
        r = self.receive(wake)
        self.assertEqual(r.ack, [2001])
        self.assertEqual(r.sends, [])
        self.assertEqual(r.notes, [])
        doc = store.read_state(self.g, "hub")
        self.assertNotIn("2001", doc.get("unknown", {}))
        self.assertEqual(doc["received"]["2001"]["kind"], "patrol")
        self.assertEqual(items.pending(self.g), [])

    def test_a_wait_user_from_the_identity_is_not_recorded_either(self):
        from test_hub import WAIT_USER
        r = self.receive(message(2002, "di-hub-patrol", WAIT_USER))
        self.assertEqual(r.sends, [])
        self.assertEqual(items.pending(self.g), [])


if __name__ == "__main__":
    unittest.main()
