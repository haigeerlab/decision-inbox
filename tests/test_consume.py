"""Hub and patrol commands delete the input files they read (p0-field-fixes F-P0-5).

The host's write tool will not overwrite a file the session has not read, so a file
left behind by the previous run made the next patrol stumble.
"""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from decision_inbox import store
from decision_inbox.__main__ import _consume, main
from helpers import TempHomeTestCase


def run_cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


def agents_json(*names):
    return json.dumps({"count": len(names), "agents": [
        {"name": n, "unread": 0, "presence": {"state": "running", "activity": "idle"}} for n in names]})


class ConsumeTest(unittest.TestCase):
    def test_deletes_only_under_disposable_roots(self):
        with tempfile.TemporaryDirectory() as d:
            inside, outside = Path(d, "in"), Path(d, "out")
            inside.mkdir()
            outside.mkdir()
            a, b = inside / "agents.json", outside / "agents.json"
            a.write_text("{}", encoding="utf-8")
            b.write_text("{}", encoding="utf-8")
            _consume(str(a), roots=[inside])
            _consume(str(b), roots=[inside])
            self.assertFalse(a.exists())
            self.assertTrue(b.exists())

    def test_missing_file_and_none_are_fine(self):
        _consume(None)
        _consume("/nonexistent/decision-inbox-x.json")


class CommandsConsumeTest(TempHomeTestCase):
    def setUp(self):
        super().setUp()
        import os
        self._plugins = os.environ.get("DECISION_INBOX_PLUGINS_FILE")
        os.environ["DECISION_INBOX_PLUGINS_FILE"] = str(self.home / "no-plugins.json")
        store.init_group("demo")
        self.g = store.open_group("demo")
        with self.g.transaction() as tx:
            tx.add_session({"relayName": "hub", "shortName": "收件枢纽", "role": "hub", "line": [],
                            "host": "claude-desktop"})

    def tearDown(self):
        import os
        if self._plugins is None:
            os.environ.pop("DECISION_INBOX_PLUGINS_FILE", None)
        else:
            os.environ["DECISION_INBOX_PLUGINS_FILE"] = self._plugins
        super().tearDown()

    def write(self, name, text):
        p = self.home / name
        p.write_text(text, encoding="utf-8")
        return p

    def test_patrol_plan_and_record(self):
        agents = self.write("agents.json", agents_json())
        plan = self.home / "plan.json"
        self.assertEqual(run_cli("patrol", "plan", "demo", "--agents", str(agents), "--out", str(plan))[0], 0)
        self.assertFalse(agents.exists())
        self.assertTrue(plan.exists())
        self.assertEqual(run_cli("patrol", "record", "demo", "--plan", str(plan))[0], 0)
        self.assertFalse(plan.exists())

    def test_patrol_keeps_unreadable_agents_and_unknown_actions(self):
        bad = self.write("agents.json", "not json")
        plan = self.home / "plan.json"
        self.assertEqual(run_cli("patrol", "plan", "demo", "--agents", str(bad), "--out", str(plan))[0], 0)
        self.assertTrue(bad.exists())
        self.assertEqual(run_cli("patrol", "record", "demo", "--plan", str(plan), "--done", "wake:nobody")[0], 2)
        self.assertTrue(plan.exists())

    def test_record_without_plan_file_is_an_error(self):
        code, _, err = run_cli("patrol", "record", "demo", "--plan", str(self.home / "gone.json"))
        self.assertEqual(code, 2)
        self.assertIn("gone.json", err)

    def test_inbox_receive(self):
        inbox = self.write("inbox.json", json.dumps({"agent": "hub", "messages": [], "hasMore": False}))
        self.assertEqual(run_cli("inbox", "receive", "demo", "--inbox", str(inbox))[0], 0)
        self.assertFalse(inbox.exists())

    def test_inbox_reply(self):
        said = self.write("said.txt", "看等待")
        agents = self.write("agents.json", agents_json())
        self.assertEqual(run_cli("inbox", "reply", "demo", "--text-file", str(said), "--agents", str(agents))[0], 0)
        self.assertFalse(said.exists())
        self.assertFalse(agents.exists())

    def test_view(self):
        agents = self.write("agents.json", agents_json())
        outbox = self.write("outbox.json", json.dumps({"agent": "hub", "entries": [], "hasMore": False}))
        self.assertEqual(run_cli("view", "demo", "--agents", str(agents), "--outbox", str(outbox))[0], 0)
        self.assertFalse(agents.exists())
        self.assertFalse(outbox.exists())

    def test_hub_commands_say_whether_a_patrol_is_due(self):
        """hub-patrol: inbox receive / reply tell the hub to run a round itself."""
        from decision_inbox import onboard
        inbox = self.write("inbox.json", json.dumps({"agent": "hub", "messages": [], "hasMore": False}))
        self.assertIs(json.loads(run_cli("inbox", "receive", "demo", "--inbox", str(inbox))[1])["patrolDue"], False)
        onboard.record_task("demo", "decision-inbox-patrol-demo", "2026-01-01T00:00:00+08:00")
        inbox = self.write("inbox.json", json.dumps({"agent": "hub", "messages": [], "hasMore": False}))
        self.assertIs(json.loads(run_cli("inbox", "receive", "demo", "--inbox", str(inbox))[1])["patrolDue"], True)
        said = self.write("said.txt", "看等待")
        self.assertIs(json.loads(run_cli("inbox", "reply", "demo", "--text-file", str(said))[1])["patrolDue"], True)

    def test_patrol_plan_from_hub(self):
        agents = self.write("agents.json", agents_json())
        plan = self.home / "plan.json"
        self.assertEqual(run_cli("patrol", "plan", "demo", "--agents", str(agents), "--out", str(plan),
                                 "--from-hub")[0], 0)
        self.assertEqual(json.loads(plan.read_text(encoding="utf-8"))["by"], "hub")

    def test_hub_round_without_agents_file_is_an_error_not_a_notice(self):
        """hub-patrol Task 5: a file an earlier command already consumed is not 'agent-relay unreadable'."""
        plan = self.home / "plan.json"
        code, _, err = run_cli("patrol", "plan", "demo", "--agents", str(self.home / "gone.json"), "--out", str(plan),
                               "--from-hub")
        self.assertEqual(code, 2)
        self.assertIn("bridge_agents", err)
        self.assertFalse(plan.exists())
        code, _, _ = run_cli("patrol", "plan", "demo", "--agents", str(self.home / "gone.json"), "--out", str(plan))
        self.assertEqual(code, 0)  # the scheduled round still plans and tells the user
        self.assertIn("notify:relay-unreadable", [a["id"] for a in json.loads(plan.read_text())["actions"]])

    def test_read_only_query_keeps_its_input(self):
        agents = self.write("agents.json", agents_json())
        run_cli("query", "lines", "demo", "--agents", str(agents))
        self.assertTrue(agents.exists())


if __name__ == "__main__":
    unittest.main()
