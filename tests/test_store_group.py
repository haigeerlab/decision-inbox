import json
import os
import stat
import subprocess
import sys
import unittest
from pathlib import Path

from helpers import REPO, TempHomeTestCase

from decision_inbox import store


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "decision_inbox", *args],
        cwd=REPO, env=os.environ.copy(), capture_output=True, text=True,
    )


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


class InitTest(TempHomeTestCase):
    def test_init_creates_group_with_tight_permissions(self):
        r = run_cli("store", "init", "demo")
        self.assertEqual(r.returncode, 0, r.stderr)
        d = self.home / "demo"
        self.assertEqual(mode(d), 0o700)
        for name in ("group.json", "roster.json", "counter.json", "events.jsonl"):
            self.assertEqual(mode(d / name), 0o600, name)
        group = json.loads((d / "group.json").read_text(encoding="utf-8"))
        self.assertEqual(group["version"], 1)
        self.assertEqual(group["name"], "demo")

    def test_second_init_changes_nothing(self):
        self.assertEqual(run_cli("store", "init", "demo").returncode, 0)
        d = self.home / "demo"
        before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in d.iterdir()}
        r = run_cli("store", "init", "demo")
        self.assertEqual(r.returncode, 0)
        self.assertIn("已存在", r.stdout)
        after = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in d.iterdir()}
        self.assertEqual(before, after)

    def test_invalid_names_rejected(self):
        for bad in ("../x", "Demo", "-a", "a-", "", "a" * 41, "前端", "a/b", ".."):
            with self.subTest(name=bad):
                r = run_cli("store", "init", bad)
                self.assertEqual(r.returncode, 2)
                self.assertEqual(list(self.home.iterdir()), [])

    def test_valid_names_accepted(self):
        for good in ("a", "shop-redesign", "a1-b2", "a" * 40):
            with self.subTest(name=good):
                self.assertEqual(store.validate_name(good), good)

    def test_open_missing_group(self):
        with self.assertRaises(store.GroupNotFound):
            store.open_group("nope")


class RootTest(unittest.TestCase):
    def test_default_root_is_home_dot_dir(self):
        old = os.environ.pop("DECISION_INBOX_HOME", None)
        try:
            self.assertEqual(store.root_dir(), Path.home() / ".decision-inbox")
        finally:
            if old is not None:
                os.environ["DECISION_INBOX_HOME"] = old


if __name__ == "__main__":
    unittest.main()
