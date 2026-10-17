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
