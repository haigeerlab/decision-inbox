import json
import stat
import unittest

from helpers import TempHomeTestCase

from decision_inbox import store


def snapshot_dir(g):
    return {
        str(p.relative_to(g.path)): (p.read_bytes(), p.stat().st_mtime_ns)
        for p in sorted(g.path.rglob("*")) if p.is_file()
    }


class StateTest(TempHomeTestCase):
    def setUp(self):
        super().setUp()
        self.g, _ = store.init_group("demo")

    def test_missing_state_has_default(self):
        self.assertEqual(store.read_state(self.g, "items"), {"version": 1, "lastSeq": 0})

    def test_write_then_read_roundtrip(self):
        with self.g.transaction() as tx:
            doc = tx.read_state("items")
            doc["open"] = {"1": {"topic": "接口字段命名"}}
            tx.write_state("items", doc)
        path = self.g.path / "state" / "items.json"
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertIn("接口字段命名", path.read_text(encoding="utf-8"))
        got = store.read_state(self.g, "items")
        self.assertEqual(got["version"], 1)
        self.assertEqual(got["open"]["1"]["topic"], "接口字段命名")

    def test_transaction_sees_its_own_writes(self):
        with self.g.transaction() as tx:
            tx.write_state("items", {"version": 1, "lastSeq": 0, "x": 1})
            self.assertEqual(tx.read_state("items")["x"], 1)

    def test_exception_leaves_disk_untouched(self):
        with self.g.transaction() as tx:
            tx.write_state("items", {"version": 1, "lastSeq": 0, "x": 1})
            tx.allocate_number()
            tx.append_event("items.created", ref=1, actor="前端", data={})
        before = snapshot_dir(self.g)
        with self.assertRaises(RuntimeError):
            with self.g.transaction() as tx:
                n = tx.allocate_number()
                tx.append_event("items.created", ref=n, actor="前端", data={})
                tx.write_state("items", {"version": 1, "lastSeq": 0, "x": 2})
                tx.write_state("tickets", {"version": 1, "lastSeq": 0})
                raise RuntimeError("boom")
        self.assertEqual(snapshot_dir(self.g), before)
        with self.g.transaction() as tx:
            self.assertEqual(tx.allocate_number(), 2)

    def test_empty_transaction_changes_nothing(self):
        before = snapshot_dir(self.g)
        with self.g.transaction() as tx:
            tx.read_state("items")
        self.assertEqual(snapshot_dir(self.g), before)

    def test_corrupt_state_is_never_overwritten(self):
        path = self.g.path / "state" / "items.json"
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(b"{not json")
        with self.assertRaises(store.StoreCorrupt) as cm:
            store.read_state(self.g, "items")
        self.assertIn(str(path), str(cm.exception))
        with self.assertRaises(store.StoreCorrupt):
            with self.g.transaction() as tx:
                tx.write_state("items", {"version": 1, "lastSeq": 0})
        self.assertEqual(path.read_bytes(), b"{not json")

    def test_unknown_version_refused(self):
        path = self.g.path / "state" / "items.json"
        path.parent.mkdir(exist_ok=True)
        raw = json.dumps({"version": 2, "lastSeq": 0}).encode()
        path.write_bytes(raw)
        with self.assertRaises(store.StoreCorrupt):
            store.read_state(self.g, "items")
        with self.assertRaises(store.StoreCorrupt):
            with self.g.transaction() as tx:
                tx.write_state("items", {"version": 1, "lastSeq": 0})
        self.assertEqual(path.read_bytes(), raw)

    def test_unknown_counter_version_refused(self):
        path = self.g.path / "counter.json"
        raw = json.dumps({"version": 2, "next": 5}).encode()
        path.write_bytes(raw)
        with self.assertRaises(store.StoreCorrupt):
            with self.g.transaction() as tx:
                tx.allocate_number()
        self.assertEqual(path.read_bytes(), raw)

    def test_bad_domain_name_rejected(self):
        with self.assertRaises(store.InvalidName):
            store.read_state(self.g, "../group")


if __name__ == "__main__":
    unittest.main()


class ShowCorruptTest(TempHomeTestCase):
    def test_show_names_corrupt_file(self):
        from test_store_group import run_cli
        g, _ = store.init_group("demo")
        path = g.path / "state" / "items.json"
        path.parent.mkdir()
        path.write_bytes(b"{not json")
        r = run_cli("store", "show", "demo")
        self.assertEqual(r.returncode, 3)
        self.assertIn(str(path), r.stdout)
        self.assertIn("事件：0 条", r.stdout)
        self.assertEqual(path.read_bytes(), b"{not json")
