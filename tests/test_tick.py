import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import REPO, FakeAgentRelay
from test_health import agent
from test_patrol import OWNER_DESKTOP, STOPPED_OWNER, PatrolCase, later

from decision_inbox import patrol, store, tick

IDENTITY = "hub-patrol"


class TickCase(PatrolCase):
    def setUp(self):
        super().setUp()
        self.fake = FakeAgentRelay(Path(tempfile.mkdtemp(prefix="di-relay-")))
        env = mock.patch.dict(os.environ, self.fake.env())
        env.start()
        self.addCleanup(env.stop)
        self.notices = []
        with self.g.transaction() as tx:
            doc = tx.read_state("onboarding")
            doc.update(patrolIdentity=IDENTITY, patrolIdentityAt=later(-60))
            tx.write_state("onboarding", doc)

    def agents(self, *rows):
        self.fake.answer("agents", json.dumps({"count": len(rows), "agents": list(rows)}))

    def notify(self, title, text):
        self.notices.append(text)
        return True

    def run_tick(self, minutes):
        return tick.tick(self.g, later(minutes), notify=self.notify)

    def sends(self):
        return [c for c in self.fake.calls() if c.startswith("ARGV send")]


class RoundTest(TickCase):
    def test_reads_state_sends_as_script_identity_and_records(self):
        self.agents(agent("fe-owner", **STOPPED_OWNER))
        result = self.run_tick(0)
        calls = self.fake.calls()
        self.assertIn("ARGV agents", calls)
        self.assertIn("ARGV outbox hub", calls)
        self.assertIn("ARGV sessions", calls)
        # wake goes to the mailbox name, never the desktop session id
        self.assertIn(f"ARGV send --from {IDENTITY} --to fe-owner", calls)
        self.assertNotIn(OWNER_DESKTOP, "\n".join(calls))
        self.assertIn("STDIN 【decision-inbox 巡视】你有 2 条消息在等，请查看收件箱后继续。", calls)
        self.assertEqual(result.done, ["wake:fe-owner"])
        state = store.read_state(self.g, "patrol")
        self.assertIn("fe-owner", state["wakes"])
        self.assertEqual(state["lastRunAt"], later(0))

    def test_owner_alert_is_mailed_and_notify_pops_a_notice(self):
        plan = patrol.Plan(now=later(0), actions=[
            patrol.Action("alert:8|fe", "owner-alert", "fe-owner", "【进度预警】前端"),
            patrol.Action("notify:all-waiting", "notify", None, "decision-inbox：都在等，详见决策收件箱")])
        self.agents()
        with mock.patch.object(patrol, "plan", return_value=plan):
            result = self.run_tick(0)
        self.assertIn(f"ARGV send --from {IDENTITY} --to fe-owner", self.fake.calls())
        self.assertIn("decision-inbox：都在等，详见决策收件箱", self.notices)
        self.assertEqual(sorted(result.done), ["alert:8|fe", "notify:all-waiting"])

    def test_stall_wake_is_mailed_to_the_line(self):
        plan = patrol.Plan(now=later(0), actions=[patrol.Action("stall:fe-owner|stalled", "wake", OWNER_DESKTOP, "催")])
        self.agents()
        with mock.patch.object(patrol, "plan", return_value=plan):
            self.run_tick(0)
        self.assertEqual(self.sends(), [f"ARGV send --from {IDENTITY} --to fe-owner"])

    def test_failed_send_is_recorded_failed(self):
        self.agents(agent("fe-owner", **STOPPED_OWNER))
        self.fake.fail("send", 1, "recipient retired")
        result = self.run_tick(0)
        self.assertEqual(result.failed, ["wake:fe-owner"])
        self.assertEqual(self.notices, [])

    def test_watch_check_still_runs(self):
        self.agents()
        with mock.patch.object(tick.watch, "check") as check:
            self.run_tick(0)
        check.assert_called_once()


class RelayDownTest(TickCase):
    def down(self):
        return [n for n in self.notices if n.startswith("巡视读不到")]

    def test_told_once_in_thirty_minutes_then_cleared_when_back(self):
        self.fake.fail("agents", 3, "mailbox locked by upgrade")
        result = self.run_tick(0)
        self.assertEqual(result.skipped, "relay")
        self.assertEqual(self.down(), ["巡视读不到 agent-relay：mailbox locked by upgrade"])
        self.assertNotIn("lastRunAt", store.read_state(self.g, "patrol"))
        self.run_tick(5)
        self.run_tick(25)
        self.assertEqual(len(self.down()), 1)
        self.run_tick(31)
        self.assertEqual(len(self.down()), 2)
        self.fake.heal("agents")
        self.agents()
        back = self.run_tick(36)
        self.assertIsNone(back.skipped)
        self.assertEqual(store.read_state(self.g, tick.DOMAIN).get("relayDownAt"), None)
        self.assertEqual(store.read_state(self.g, "patrol")["lastRunAt"], later(36))
        self.fake.fail("agents", 3, "again")
        self.run_tick(40)  # a new episode is told at once
        self.assertEqual(len(self.down()), 3)

    def test_unparsable_agents_counts_as_down(self):
        self.fake.answer("agents", "not json")
        self.assertEqual(self.run_tick(0).skipped, "relay")
        self.assertTrue(self.notices[0].startswith("巡视读不到 agent-relay："))

    def test_relay_without_script_commands(self):
        older = FakeAgentRelay(Path(tempfile.mkdtemp(prefix="di-relay-")), script=False)
        with mock.patch.dict(os.environ, older.env()):
            self.assertEqual(self.run_tick(0).skipped, "relay")
        self.assertIn("0.9.0", self.notices[0])


class IdentityTest(TickCase):
    def test_send_refused_marks_failed_and_tells_once_until_a_send_works(self):
        self.agents(agent("fe-owner", **STOPPED_OWNER), agent("api-owner", **STOPPED_OWNER))
        self.fake.fail("send", 1, f'"{IDENTITY}" is not a script identity; register one with register-script-identity')
        first = self.run_tick(0)
        self.assertEqual([i for i in first.done if not i.startswith("notify:")], [])  # api-owner: a notice, no mail
        self.assertIn("wake:fe-owner", first.failed)
        expected = f"巡视发不出信：请在终端登记脚本身份 {IDENTITY}"
        self.assertEqual([n for n in self.notices if n.startswith("巡视发不出信")], [expected])
        self.run_tick(5)
        self.assertEqual(len([n for n in self.notices if n.startswith("巡视发不出信")]), 1)
        self.fake.heal("send")
        later_wake = patrol.Plan(now=later(10), actions=[patrol.Action("wake:api", "wake", "x", "醒醒")])
        with mock.patch.object(patrol, "plan", return_value=later_wake):
            self.run_tick(10)
        self.assertIsNone(store.read_state(self.g, tick.DOMAIN).get("identityMissingAt"))

    def test_no_identity_recorded(self):
        with self.g.transaction() as tx:
            doc = tx.read_state("onboarding")
            doc.pop("patrolIdentity")
            tx.write_state("onboarding", doc)
        self.agents(agent("fe-owner", **STOPPED_OWNER))
        result = self.run_tick(0)
        self.assertEqual(result.failed, ["wake:fe-owner"])
        self.assertEqual(self.sends(), [])
        self.assertTrue(any(n.startswith("巡视发不出信：请在终端登记脚本身份") for n in self.notices))


class LockTest(TickCase):
    def test_skips_while_the_hub_holds_the_lock(self):
        self.assertTrue(tick.acquire(self.g, "hub", later(0)))
        self.agents(agent("fe-owner", **STOPPED_OWNER))
        result = self.run_tick(1)
        self.assertEqual(result.skipped, "locked")
        self.assertEqual(self.sends(), [])
        self.assertNotIn("ARGV agents", self.fake.calls())
        tick.release(self.g, "hub")
        self.assertIsNone(self.run_tick(2).skipped)

    def test_a_stale_lock_is_taken_over(self):
        self.assertTrue(tick.acquire(self.g, "hub", later(0)))
        self.agents()
        self.assertEqual(self.run_tick(tick.LOCK_STALE_MINUTES - 1).skipped, "locked")
        self.assertIsNone(self.run_tick(tick.LOCK_STALE_MINUTES + 1).skipped)
        self.assertFalse(tick.lock_path(self.g).exists())

    def test_release_leaves_someone_elses_lock(self):
        self.assertTrue(tick.acquire(self.g, "schedule", later(0)))
        tick.release(self.g, "hub")
        self.assertTrue(tick.lock_path(self.g).exists())


class HubLockTest(TickCase):
    def run_cli(self, *argv):
        import contextlib
        import io
        from decision_inbox.__main__ import main
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_hub_round_takes_and_releases_the_lock(self):
        agents = self.home / "io-agents.json"
        agents.write_text(json.dumps({"count": 1, "agents": [agent("fe-owner", **STOPPED_OWNER)]}), encoding="utf-8")
        plan_file = self.home / "plan.json"
        code, _, _ = self.run_cli("patrol", "plan", "demo", "--agents", str(agents), "--out", str(plan_file),
                                  "--from-hub")
        self.assertEqual(code, 0)
        self.assertTrue(tick.lock_path(self.g).exists())
        self.assertEqual(self.run_tick(1).skipped, "locked")
        ids = [a["id"] for a in json.loads(plan_file.read_text(encoding="utf-8"))["actions"]]
        self.assertEqual(self.run_cli("patrol", "record", "demo", "--plan", str(plan_file), "--done", *ids)[0], 0)
        self.assertFalse(tick.lock_path(self.g).exists())

    def test_hub_round_skipped_while_tick_holds_the_lock(self):
        self.assertTrue(tick.acquire(self.g, "schedule", store.now()))
        agents = self.home / "io-agents.json"
        agents.write_text(json.dumps({"count": 1, "agents": [agent("fe-owner", **STOPPED_OWNER)]}), encoding="utf-8")
        plan_file = self.home / "plan.json"
        before = store.read_state(self.g, "patrol")
        code, out, _ = self.run_cli("patrol", "plan", "demo", "--agents", str(agents), "--out", str(plan_file),
                                    "--from-hub")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["actions"], [])
        self.assertTrue(json.loads(plan_file.read_text(encoding="utf-8"))["skipped"])
        self.assertEqual(self.run_cli("patrol", "record", "demo", "--plan", str(plan_file))[0], 0)
        self.assertEqual(store.read_state(self.g, "patrol"), before)
        self.assertTrue(tick.lock_path(self.g).exists())  # the tick's lock is not the hub's to release


class BareEnvironmentTest(TickCase):
    """验收 1：launchd 那样只有 /usr/bin:/bin 的环境。"""

    def test_runs_under_env_i(self):
        self.agents(agent("fe-owner", **STOPPED_OWNER))
        osascript = self.home / "osascript"
        osascript.write_text(f'#!/bin/sh\necho "$@" >> "{self.home}/notices.log"\n', encoding="utf-8")
        osascript.chmod(0o755)
        env = {"PATH": "/usr/bin:/bin", "DECISION_INBOX_HOME": str(self.home), "HOME": str(self.fake.home),
               "DECISION_INBOX_PLUGINS_FILE": str(self.fake.records), "DECISION_INBOX_OSASCRIPT": str(osascript)}
        r = subprocess.run(["/usr/bin/env", "-i", *[f"{k}={v}" for k, v in env.items()],
                            sys.executable, "-m", "decision_inbox", "patrol", "tick", "demo"],
                           cwd=REPO, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f"ARGV send --from {IDENTITY} --to fe-owner", self.fake.calls())
        self.assertIn("fe-owner", store.read_state(self.g, "patrol")["wakes"])

    def test_bad_group_still_exits_zero(self):
        from decision_inbox.__main__ import main
        import contextlib
        import io
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["patrol", "tick", "nope"]), 0)


if __name__ == "__main__":
    unittest.main()
