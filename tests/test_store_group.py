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


class ShowTest(TempHomeTestCase):
    def test_show_healthy_group(self):
        g, _ = store.init_group("demo")
        with g.transaction() as tx:
            n = tx.allocate_number()
            tx.append_event("items.created", ref=n, actor="前端")
            tx.write_state("items", tx.read_state("items"))
        r = run_cli("store", "show", "demo")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(str(g.path), r.stdout)
        self.assertIn("下一个编号：2", r.stdout)
        self.assertIn("事件：1 条", r.stdout)
        self.assertIn("名册：0 个会话", r.stdout)
        self.assertIn("一致性：正常", r.stdout)

    def test_show_missing_group(self):
        self.assertEqual(run_cli("store", "show", "nope").returncode, 2)

    def test_show_reports_snapshot_behind_log(self):
        g, _ = store.init_group("demo")
        lines = [
            json.dumps({"seq": i, "at": store.now(), "type": "items.created",
                        "ref": i, "actor": "前端", "data": {}})
            for i in range(1, 43)
        ]
        (g.path / "events.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (g.path / "state").mkdir()
        (g.path / "state" / "items.json").write_text(
            json.dumps({"version": 1, "lastSeq": 41}), encoding="utf-8")
        r = run_cli("store", "show", "demo")
        self.assertEqual(r.returncode, 3)
        self.assertIn("快照落后于日志 1 条", r.stdout)
        self.assertIn("items", r.stdout)
        with g.transaction() as tx:
            self.assertTrue(any("落后" in w for w in tx.warnings))
            tx.append_event("tickets.created", ref=43, actor="API")
            tx.write_state("tickets", tx.read_state("tickets"))
        self.assertEqual(store.read_state(g, "tickets")["lastSeq"], 43)


class StartNumberTest(TempHomeTestCase):
    """hub-cutover-settings: a new group may start numbering at N, only before any number is given out."""

    def allocate(self, g):
        with g.transaction() as tx:
            return tx.allocate_number()

    def test_start_then_allocate(self):
        g, _ = store.init_group("demo")
        store.set_start_number(g, 1001)
        store.set_start_number(g, 1001)  # a rerun before any number is fine
        self.assertEqual([self.allocate(g), self.allocate(g)], [1001, 1002])

    def test_refused_once_numbers_are_given_out(self):
        g, _ = store.init_group("demo")
        self.allocate(g)
        before = (g.path / "counter.json").read_bytes()
        with self.assertRaises(store.StartNumberError):
            store.set_start_number(g, 1001)
        self.assertEqual((g.path / "counter.json").read_bytes(), before)

    def test_bad_values(self):
        g, _ = store.init_group("demo")
        for bad in (0, -5, 1000001, "1001", 10.5, True):
            with self.subTest(bad=bad):
                with self.assertRaises(store.StartNumberError):
                    store.set_start_number(g, bad)
        self.assertEqual(self.allocate(g), 1)
