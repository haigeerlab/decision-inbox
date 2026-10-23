import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import FakeAgentRelay

from decision_inbox import relayscript


class ScriptArgvTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeAgentRelay(Path(tempfile.mkdtemp(prefix="di-relay-")))
        self.env = mock.patch.dict(os.environ, self.fake.env())
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_commands_from_interface_with_home_expanded(self):
        launcher = str(self.fake.bin)
        self.assertEqual(relayscript.script_argv("agents"), [launcher, "agents"])
        self.assertEqual(relayscript.script_argv("outbox", agent="di-p0-hub"), [launcher, "outbox", "di-p0-hub"])
        self.assertEqual(relayscript.script_argv("sessions"), [launcher, "sessions"])
        self.assertEqual(relayscript.script_argv("send", agent="dev-a", identity="di-p0-hub-patrol"),
                         [launcher, "send", "--from", "di-p0-hub-patrol", "--to", "dev-a"])

    def test_read_returns_stdout(self):
        self.fake.answer("agents", '{"agents": []}')
        r = relayscript.run_script("agents")
        self.assertEqual((r.code, r.stdout.strip(), r.error), (0, '{"agents": []}', ""))
        self.assertEqual(self.fake.calls(), ["ARGV agents"])

    def test_send_body_goes_through_stdin(self):
        r = relayscript.run_script("send", agent="dev-a", identity="hub-patrol", body="请查看收件箱")
        self.assertEqual(r.code, 0)
        self.assertEqual(self.fake.calls(), ["ARGV send --from hub-patrol --to dev-a", "STDIN 请查看收件箱"])

    def test_failure_gives_code_and_first_stderr_line(self):
        self.fake.fail("agents", 3, "mailbox is being upgraded")
        r = relayscript.run_script("agents")
        self.assertEqual((r.code, r.error), (3, "mailbox is being upgraded"))

    def test_launcher_missing_is_a_failure_not_a_crash(self):
        self.fake.bin.unlink()
        r = relayscript.run_script("agents")
        self.assertNotEqual(r.code, 0)
        self.assertTrue(r.error)


class NoScriptTest(unittest.TestCase):
    def test_older_relay_without_script_section_asks_to_upgrade(self):
        fake = FakeAgentRelay(Path(tempfile.mkdtemp(prefix="di-relay-")), script=False)
        with mock.patch.dict(os.environ, fake.env()):
            with self.assertRaises(relayscript.ScriptUnavailable) as e:
                relayscript.script_argv("agents")
        self.assertIn("0.9.0", str(e.exception))

    def test_relay_not_installed(self):
        root = Path(tempfile.mkdtemp(prefix="di-relay-"))
        with mock.patch.dict(os.environ, {"DECISION_INBOX_PLUGINS_FILE": str(root / "none.json")}):
            with self.assertRaises(relayscript.ScriptUnavailable):
                relayscript.script_argv("agents")
            r = relayscript.run_script("agents")
        self.assertNotEqual(r.code, 0)
        self.assertTrue(r.error)


if __name__ == "__main__":
    unittest.main()
