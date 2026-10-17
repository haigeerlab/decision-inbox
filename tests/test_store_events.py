import json
import multiprocessing as mp
import os
import unittest

from helpers import TempHomeTestCase

from decision_inbox import store


def _worker(home, count):
    os.environ["DECISION_INBOX_HOME"] = home
    g = store.open_group("demo")
    got = []
    for _ in range(count):
        with g.transaction() as tx:
            n = tx.allocate_number()
            tx.append_event("items.created", ref=n, actor="前端", data={})
        got.append(n)
    return got


class EventsTest(TempHomeTestCase):
    def setUp(self):
        super().setUp()
        self.g, _ = store.init_group("demo")

    def test_concurrent_allocation_is_unique_and_complete(self):
        ctx = mp.get_context("spawn")
        with ctx.Pool(20) as pool:
            results = pool.starmap(_worker, [(str(self.home), 50)] * 20)
        numbers = sorted(n for r in results for n in r)
        self.assertEqual(numbers, list(range(1, 1001)))
        events = store.read_events(self.g)
        self.assertEqual([e["seq"] for e in events], list(range(1, 1001)))
        self.assertEqual(sorted(e["ref"] for e in events), list(range(1, 1001)))

    def test_read_events_by_ref_sorted(self):
        with self.g.transaction() as tx:
            tx.append_event("items.created", ref=7, actor="前端")
            tx.append_event("tickets.created", ref=8, actor="API")
        with self.g.transaction() as tx:
            tx.append_event("items.answered", ref=7, actor="user", data={"text": "12 B"})
        got = store.read_events(self.g, ref=7)
        self.assertEqual([e["type"] for e in got], ["items.created", "items.answered"])
        self.assertEqual(got[1]["data"], {"text": "12 B"})
        self.assertEqual([e["seq"] for e in got], [1, 3])

    def test_truncated_tail_is_skipped_then_repaired(self):
        with self.g.transaction() as tx:
            tx.append_event("items.created", ref=1, actor="前端")
        log = self.g.path / "events.jsonl"
        with open(log, "ab") as f:
            f.write(b'{"seq": 2, "at": "2026')
        warnings = []
        events = store.read_events(self.g, warnings=warnings)
        self.assertEqual([e["seq"] for e in events], [1])
        self.assertEqual(len(warnings), 1)
        with self.g.transaction() as tx:
            tx.append_event("items.created", ref=2, actor="前端")
        lines = log.read_bytes().split(b"\n")
        self.assertEqual(json.loads(lines[-2])["ref"], 2)
        self.assertEqual([e["ref"] for e in store.read_events(self.g)], [1, 2])

    def test_unparsable_middle_line_skipped_with_warning(self):
        log = self.g.path / "events.jsonl"
        log.write_bytes(b'garbage\n{"seq": 1, "ref": null}\n')
        warnings = []
        self.assertEqual([e["seq"] for e in store.read_events(self.g, warnings=warnings)], [1])
        self.assertEqual(len(warnings), 1)

    def test_bad_event_type_rejected(self):
        with self.assertRaises(ValueError):
            with self.g.transaction() as tx:
                tx.append_event("created", ref=1)


if __name__ == "__main__":
    unittest.main()
