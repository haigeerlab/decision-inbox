import contextlib
import io
import json

from helpers import TempHomeTestCase

from decision_inbox import query, store

E = [  # (type, ref, actor, at, data)
    ("items.received", 1, "dev", "2026-10-17T10:00:00+08:00", {"relayId": 101}),
    ("items.answered", 1, "user", "2026-10-17T10:10:00+08:00", {"letter": "A"}),
    ("items.closed", 1, "dev", "2026-10-17T10:40:00+08:00", {}),
    ("items.received", 2, "dev", "2026-10-17T11:00:00+08:00", {"relayId": 102}),
    ("items.answered", 2, "user", "2026-10-17T11:30:00+08:00", {"letter": "B"}),
    ("items.closed", 2, "dev", "2026-10-17T11:35:00+08:00", {}),
    ("items.received", 3, "dev", "2026-10-17T12:00:00+08:00", {"relayId": 103}),
    ("items.closed", 3, "dev", "2026-10-17T12:20:00+08:00", {}),                 # ended without the user
    ("items.received", 4, "lead", "2026-10-18T09:00:00+08:00", {"relayId": 104}),
    ("items.superseded", 4, "lead", "2026-10-18T09:05:00+08:00", {"by": 5, "auto": True}),
    ("items.received", 5, "lead", "2026-10-18T09:05:00+08:00", {"relayId": 105}),
    ("items.superseded", 5, "lead", "2026-10-18T09:06:00+08:00", {"by": 6}),
    ("items.returned", None, "dev", "2026-10-18T09:07:00+08:00", {"relayId": 106}),
    ("hub.relayed-input", None, "hub", "2026-10-18T09:08:00+08:00", {"from": "lead"}),
]


class StatsCase(TempHomeTestCase):
    def setUp(self):
        super().setUp()
        self.g, _ = store.init_group("g")
        with open(self.g.path / "events.jsonl", "a", encoding="utf-8") as f:
            for seq, (t, ref, actor, at, data) in enumerate(E, start=1):
                f.write(json.dumps({"seq": seq, "at": at, "type": t, "ref": ref, "actor": actor, "data": data},
                                   ensure_ascii=False) + "\n")
        with self.g.transaction() as tx:
            tx.write_state("hub", {"unknown": {
                "107": {"sender": "dev", "at": "2026-10-18T09:09:00+08:00", "returned": True},
                "108": {"sender": "dev", "at": "2026-10-18T09:10:00+08:00", "returned": False}}})


class StatsTest(StatsCase):
    def test_numbers(self):
        s = query.stats(self.g)
        self.assertEqual((s.raised, s.answered, s.closed), (5, 2, 3))
        self.assertEqual(s.bypassed, (3,))
        self.assertEqual((s.to_answer.median, s.to_answer.longest, s.to_answer.count), (20, 30, 2))
        self.assertEqual((s.to_resume.median, s.to_resume.longest, s.to_resume.count), (17.5, 30, 2))
        self.assertEqual((s.superseded, s.auto_superseded, s.returned, s.questions_returned, s.relayed_refused),
                         (2, 1, 1, 1, 1))

    def test_since_filters_by_day(self):
        s = query.stats(self.g, since="2026-10-18")
        self.assertEqual((s.raised, s.answered, s.bypassed, s.superseded), (2, 0, (), 2))
        self.assertIsNone(s.to_answer.median)

    def test_render(self):
        text = query.render_stats(query.stats(self.g), "g", None)
        self.assertIn("绕过收件枢纽结束：1 项（#3）", text)
        self.assertIn("抛出→答复：中位 20 分钟，最长 30 分钟（2 项）", text)
        self.assertIn("答复→恢复：中位 17.5 分钟，最长 30 分钟（2 项）", text)
        self.assertIn("被取代 2 项（其中自动 1 项） · 退回 1 次 · 追问被退回 1 次 · 拒收转述 1 次", text)
        self.assertIn("现在开着的等待单 0 单", text)
        empty = query.render_stats(query.stats(self.g, since="2030-01-01"), "g", "2030-01-01")
        self.assertIn("抛出→答复：没有数据", empty)


class EventsTest(StatsCase):
    def test_fixed_fields_and_since(self):
        rows = query.events(self.g, since="2026-10-18")
        self.assertEqual(len(rows), 6)
        self.assertEqual(list(rows[0]), ["at", "kind", "actor", "item", "data"])
        self.assertEqual((rows[0]["kind"], rows[0]["item"]), ("items.received", 4))

    def test_cli(self):
        from decision_inbox.__main__ import main
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(main(["query", "events", "g", "--json"]), 0)
        self.assertEqual(len(json.loads(buf.getvalue())), len(E))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(main(["query", "stats", "g", "--since", "2026-10-18"]), 0)
        self.assertIn("自 2026-10-18 起", buf.getvalue())
