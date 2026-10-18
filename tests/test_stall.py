"""stall-and-patrol Task 4 (R14, user chose B): a stuck line is asked to raise the question itself."""

import json

from helpers import TempHomeTestCase
from test_health import NOW, WAIT_USER, line_map, module

from decision_inbox import health, items, reviews, stall, store

FE_DESKTOP = "local_00000000-0000-0000-0000-0000000fe001"


def hours(n):
    from datetime import datetime, timedelta
    return (datetime.fromisoformat(NOW) - timedelta(hours=n)).isoformat()


class StallCase(TempHomeTestCase):
    def setUp(self):
        super().setUp()
        self.g, _ = store.init_group("demo")
        people = [("hub", "收件枢纽", "hub", [], "claude-desktop", None, None),
                  ("fe", "前端", "dev", ["前端"], "claude-desktop", "/tmp/fe", FE_DESKTOP),
                  ("api", "API", "dev", ["API"], "codex-desktop", "/tmp/api", None),
                  ("owner", "前端负责人", "owner", ["前端"], "claude-desktop", None, None)]
        with self.g.transaction() as tx:
            for name, short, role, line, host, repo, desktop in people:
                entry = {"relayName": name, "shortName": short, "role": role, "line": line, "host": host}
                if repo:
                    entry["repo"] = repo
                if desktop:
                    entry["desktopSession"] = desktop
                tx.add_session(entry)

    def asks(self, lines=None, maps=None, state=None, now=NOW):
        return stall.asks(self.g, now, lines or {}, maps or {}, state or {})


class TriggerTest(StallCase):
    def test_stalled_twelve_hours(self):
        maps = {"fe": line_map([module("m1"), module("m2", 2, status="ready"), module("m3", 3, status="ready")])}
        short = {"fe": health.LineState("stalled", "停住 11 小时", since=hours(11))}
        self.assertEqual(self.asks(short, maps), [])
        long = {"fe": health.LineState("stalled", "停住 13 小时", since=hours(13))}
        [ask] = self.asks(long, maps)
        self.assertEqual((ask.key, ask.kind, ask.target), ("fe|stalled", "wake", FE_DESKTOP))
        for words in ("前端", "13 小时", "【等待用户】", "A 挂起", "m2、m3", "B 换做法", "C 继续等"):
            self.assertIn(words, ask.text)

    def test_rework_rounds(self):
        reviews.register(self.g, "fe", "owner", ("spec",), None, "用户批准", at=hours(30))
        msg = type("M", (), {})()
        for n in range(3):
            with self.g.transaction() as tx:
                doc = tx.read_state("reviews")
                doc.setdefault("reviews", {}).setdefault("R-1", {"submitter": "fe", "reviewer": "owner", "node": "spec",
                                                                 "rounds": [], "closed": False})["rounds"].append(
                    {"at": hours(3 - n), "verdict": "changes-required", "adviceCount": None})
                tx.write_state("reviews", doc)
        [ask] = self.asks()
        self.assertEqual(ask.key, "fe|rework")
        self.assertIn("审查 R-1（spec）来回 3 轮", ask.text)

    def test_same_question_three_times_codex_by_mail(self):
        for n, at in enumerate((hours(20), hours(10), hours(1))):
            items.receive(self.g, WAIT_USER, sender="api", relay_id=100 + n, received_at=at)
        [ask] = self.asks()
        self.assertEqual((ask.key, ask.kind, ask.target), ("api|repeat", "owner-alert", "api"))
        self.assertIn("24 小时内报批 3 次", ask.text)

    def test_not_asked_again_within_twelve_hours_and_thresholds_configurable(self):
        long = {"fe": health.LineState("stalled", "停住 13 小时", since=hours(13))}
        self.assertEqual(self.asks(long, state={"stallAsks": {"fe|stalled": hours(11)}}), [])
        self.assertEqual(len(self.asks(long, state={"stallAsks": {"fe|stalled": hours(13)}})), 1)
        doc = json.loads((self.g.path / "group.json").read_text(encoding="utf-8"))
        doc["stall"] = {"stalledHours": 20}
        (self.g.path / "group.json").write_text(json.dumps(doc), encoding="utf-8")
        self.assertEqual(self.asks(long), [])


class OverdueTest(StallCase):
    def test_no_new_item_in_thirty_minutes_lists_options(self):
        from datetime import datetime, timedelta
        asked = (datetime.fromisoformat(NOW) - timedelta(minutes=31)).isoformat()
        rows = stall.overdue_rows(self.g, NOW, {"stallAsks": {"fe|stalled": asked}})
        self.assertEqual(len(rows), 1)
        for words in ("前端", "A 挂起", "B 换做法", "C 继续等", f"claude://claude.ai/epitaxy/{FE_DESKTOP}"):
            self.assertIn(words, rows[0])
        items.receive(self.g, WAIT_USER, sender="fe", relay_id=7, received_at=NOW)
        self.assertEqual(stall.overdue_rows(self.g, NOW, {"stallAsks": {"fe|stalled": asked}}), [])


from decision_inbox import hub, patrol  # noqa: E402
from test_health import snapshot, agent  # noqa: E402


class PatrolWiringTest(StallCase):
    def test_patrol_asks_records_and_hub_shows_overdue(self):
        for n, at in enumerate((hours(20), hours(10), hours(1))):
            items.receive(self.g, WAIT_USER, sender="api", relay_id=100 + n, received_at=at)
        p = patrol.plan(self.g, now=NOW, relay=snapshot(agent("api", app="codex")))
        ask = next(a for a in p.actions if a.id == "stall:api|repeat")
        self.assertEqual((ask.kind, ask.target), ("owner-alert", "api"))
        patrol.record(self.g, p.to_json(), done=[a.id for a in p.actions], now=NOW)
        self.assertEqual(store.read_state(self.g, "patrol")["stallAsks"], {"api|repeat": NOW})
        again = patrol.plan(self.g, now=NOW, relay=snapshot(agent("api", app="codex")))
        self.assertNotIn("stall:api|repeat", [a.id for a in again.actions])
        from datetime import datetime, timedelta
        later = (datetime.fromisoformat(NOW) + timedelta(minutes=40)).isoformat()
        self.assertIn("⚠ 停滞：API", hub.main_view(self.g, now=later))
