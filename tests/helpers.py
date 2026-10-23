import os
import shutil
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


class TempHomeTestCase(unittest.TestCase):
    """Points DECISION_INBOX_HOME at a fresh temp dir for every test."""

    def setUp(self):
        self._old_home = os.environ.get("DECISION_INBOX_HOME")
        self.home = Path(tempfile.mkdtemp(prefix="di-test-"))
        os.environ["DECISION_INBOX_HOME"] = str(self.home)
        real = Path.home() / ".decision-inbox"
        self.assertNotEqual(Path(os.environ["DECISION_INBOX_HOME"]).resolve(), real.resolve())

    def tearDown(self):
        if self._old_home is None:
            os.environ.pop("DECISION_INBOX_HOME", None)
        else:
            os.environ["DECISION_INBOX_HOME"] = self._old_home
        shutil.rmtree(self.home, ignore_errors=True)


class FakeAgentRelay:
    """A fake agent-relay plugin whose interface.json has a `script` section and a launcher under ~ (patrol-launchd).

    The launcher logs each call (argv, then stdin) to `log` and answers from `answers/<command>.json`;
    `fail/<command>` holds an exit code and a stderr line to fail with instead.
    """

    def __init__(self, root: Path, script: bool = True):
        import json
        self.root = root
        self.home = root / "home"
        self.bin = self.home / ".agent-relay" / "bin" / "agent-relay"
        self.log = root / "relay-calls.log"
        self.answers = root / "answers"
        self.fails = root / "fail"
        for d in (self.bin.parent, self.answers, self.fails):
            d.mkdir(parents=True, exist_ok=True)
        self.bin.write_text(
            "#!/bin/sh\n"
            f'LOG="{self.log}"\n'
            'echo "ARGV $*" >> "$LOG"\n'
            'if [ "$1" = "send" ]; then echo "STDIN $(cat)" >> "$LOG"; fi\n'
            f'F="{self.fails}/$1"\n'
            'if [ -f "$F" ]; then read code msg < "$F"; echo "$msg" >&2; exit "$code"; fi\n'
            f'A="{self.answers}/$1.json"\n'
            'if [ -f "$A" ]; then cat "$A"; else echo "{}"; fi\n', encoding="utf-8")
        self.bin.chmod(0o755)
        plugin = root / "plugin"
        plugin.mkdir(exist_ok=True)
        launcher = "~/.agent-relay/bin/agent-relay"
        data = {"interface": "2.8"}
        if script:
            data["script"] = {"agents": [launcher, "agents"], "outbox": [launcher, "outbox", "<agent>"],
                              "sessions": [launcher, "sessions"],
                              "send": [launcher, "send", "--from", "<script identity>", "--to", "<agent>"]}
        (plugin / "interface.json").write_text(json.dumps(data), encoding="utf-8")
        self.records = root / "installed_plugins.json"
        self.records.write_text(json.dumps({"plugins": {"agent-relay@m": [
            {"scope": "user", "installPath": str(plugin), "version": "0.9.0" if script else "0.8.5"}]}}),
            encoding="utf-8")

    def answer(self, command: str, text: str) -> None:
        (self.answers / f"{command}.json").write_text(text, encoding="utf-8")

    def fail(self, command: str, code: int, message: str) -> None:
        (self.fails / command).write_text(f"{code} {message}\n", encoding="utf-8")

    def heal(self, command: str) -> None:
        (self.fails / command).unlink(missing_ok=True)

    def calls(self) -> list[str]:
        return self.log.read_text(encoding="utf-8").splitlines() if self.log.is_file() else []

    def env(self) -> dict:
        """What the fake needs in the environment: its plugin records and its home."""
        return {"DECISION_INBOX_PLUGINS_FILE": str(self.records), "HOME": str(self.home)}
