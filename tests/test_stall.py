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
        for words in ("前端", "13 小时", "【等待用户】", "A 挂起", "m2、m3", "B 换方案", "C 继续等"):
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

    def _answer(self, no, at):
        items.answer(self.g, [items.Answer(no, None, f"{no} 好")], answered_at=at)

    def test_repeat_count_resets_once_the_latest_is_answered(self):
        """decision-cards I-13: a settled matter is not asked about again."""
        for n, at in enumerate((hours(20), hours(10), hours(2))):
            items.receive(self.g, WAIT_USER, sender="api", relay_id=100 + n, received_at=at)
        self._answer(3, hours(1))
        self.assertEqual(self.asks(), [])

    def test_repeat_counts_only_after_the_last_answer(self):
        items.receive(self.g, WAIT_USER, sender="api", relay_id=99, received_at=hours(22))
        self._answer(1, hours(21))
        for n, at in enumerate((hours(20), hours(10))):
            items.receive(self.g, WAIT_USER, sender="api", relay_id=100 + n, received_at=at)
        self.assertEqual(self.asks(), [])
        items.receive(self.g, WAIT_USER, sender="api", relay_id=102, received_at=hours(1))
        [ask] = self.asks()
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
        for words in ("前端", "A 挂起", "B 换方案", "C 继续等", f"claude://claude.ai/epitaxy/{FE_DESKTOP}"):
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


from decision_inbox import crew  # noqa: E402

CREW_DESKTOP = "local_00000000-0000-0000-0000-00000000c0de"


def crew_module(name="alpha", stage="build", **facts):
    return crew.Module(name, f"rh-{name}", stage, facts.pop("suspended", None), facts.pop("review", None), **facts)


class ModuleStallTest(StallCase):
    """crew-stall-facts: a module under a module-crew coordinator, judged on module-crew 0.4.0 facts."""

    def setUp(self):
        super().setUp()
        with self.g.transaction() as tx:
            tx.add_session({"relayName": "coord", "shortName": "排练协调", "role": "dev",
                            "line": ["crew-rehearsal"], "host": "claude-desktop", "repo": "/tmp/crew",
                            "desktopSession": CREW_DESKTOP, "crewCoordinator": True})

    def crew_asks(self, *modules, state=None, now=NOW, status="ok"):
        crews = {"coord": crew.CrewRead(status, tuple(modules))}
        return stall.asks(self.g, now, {}, {}, state or {}, crews=crews)

    def test_no_commit_for_thirteen_hours_asks_the_coordinator_once(self):
        found = self.crew_asks(crew_module(started_at=hours(30), last_commit_at=hours(13)))
        self.assertEqual([(a.key, a.kind, a.target) for a in found],
                         [("coord|stalled:alpha", "wake", CREW_DESKTOP)])
        for words in ("模块 alpha", "13 小时没有新提交", "A 挂起", "B 换方案", "C 继续等", "module-crew"):
            self.assertIn(words, found[0].text)
        self.assertNotIn("module-suspend", found[0].text)
        self.assertEqual(self.crew_asks(crew_module(started_at=hours(30), last_commit_at=hours(13)),
                                        state={"stallAsks": {"coord|stalled:alpha": hours(1)}}), [])
        self.assertEqual(self.crew_asks(crew_module(started_at=hours(30), last_commit_at=hours(11))), [])

    def test_started_at_when_no_commit_and_error_or_nothing_skips(self):
        self.assertEqual([a.key for a in self.crew_asks(crew_module(started_at=hours(13)))],
                         ["coord|stalled:alpha"])
        self.assertEqual(self.crew_asks(crew_module(started_at=hours(30), commits_error="worktree 不存在")), [])
        self.assertEqual(self.crew_asks(crew_module()), [])

    def test_repeat_asks_within_window(self):
        three = (("final", (hours(20), hours(10), hours(1))),)
        self.assertEqual([a.key for a in self.crew_asks(crew_module(started_at=hours(2), asks=three))],
                         ["coord|repeat:alpha"])
        self.assertIn("24 小时内报批 3 次", self.crew_asks(crew_module(started_at=hours(2), asks=three))[0].text)
        for asks in ((("final", (hours(10), hours(1))),), (("final", (hours(30), hours(10), hours(1))),),
                     (("spec", (hours(10),)), ("plan", (hours(5),)), ("final", (hours(1),)))):
            with self.subTest(asks=asks):
                self.assertEqual(self.crew_asks(crew_module(started_at=hours(2), asks=asks)), [])

    def test_repeat_asks_counted_after_the_last_answer(self):
        """decision-cards I-13: module-crew asks before the user's last answer to the module do not count."""
        three = (("final", (hours(20), hours(10), hours(3))),)
        answered = (crew.Answer("C1", hours(2), 0, 0),)
        self.assertEqual(self.crew_asks(crew_module(started_at=hours(2), asks=three, answers=answered)), [])
        early = (crew.Answer("C1", hours(21), 0, 0),)
        self.assertEqual([a.key for a in self.crew_asks(crew_module(started_at=hours(2), asks=three, answers=early))],
                         ["coord|repeat:alpha"])

    def test_skipped_modules(self):
        old = {"started_at": hours(30), "last_commit_at": hours(20),
               "asks": (("final", (hours(3), hours(2), hours(1))),)}
        for name, m in (("merged", crew_module(stage="merged", **old)),
                        ("wait-merge", crew_module(stage="wait-merge", **old)),
                        ("suspended", crew_module(suspended="等设计稿", **old))):
            with self.subTest(name):
                self.assertEqual(self.crew_asks(m), [])

    def test_030_shape_or_unknown_read_adds_nothing(self):
        self.assertEqual(self.crew_asks(crew_module()), [])
        self.assertEqual(self.crew_asks(crew_module(started_at=hours(30)), status="unknown"), [])
        self.assertEqual(stall.asks(self.g, NOW, {}, {}, {}), [])

    def test_patrol_passes_crews(self):
        crews = {"coord": crew.CrewRead("ok", (crew_module(started_at=hours(30), last_commit_at=hours(13)),))}
        p = patrol.plan(self.g, now=NOW, relay=snapshot(agent("coord")), crews=crews)
        ask = next(a for a in p.actions if a.id == "stall:coord|stalled:alpha")
        self.assertIn("模块 alpha", ask.text)

    def test_overdue_row_names_the_module(self):
        asked = hours(1)
        rows = stall.overdue_rows(self.g, NOW, {"stallAsks": {"coord|stalled:alpha": asked}})
        self.assertEqual(len(rows), 1)
        for words in ("⚠ 停滞：排练协调（模块 alpha）", "A 挂起", "B 换方案", "C 继续等",
                      f"claude://claude.ai/epitaxy/{CREW_DESKTOP}"):
            self.assertIn(words, rows[0])
        items.receive(self.g, WAIT_USER, sender="coord", relay_id=9, received_at=NOW)
        self.assertEqual(stall.overdue_rows(self.g, NOW, {"stallAsks": {"coord|stalled:alpha": asked}}), [])


class WorkTimeStallTest(ModuleStallTest):
    """loop-detection 7: waiting for the user or in review no longer skips a module; waiting time is not stall."""

    def loop(self, waits=(), hit=None, module="alpha"):
        from types import SimpleNamespace as NS
        return NS(key=f"coord|{module}", line="coord", module=module, waits=tuple(waits), hit=hit)

    def asks_with(self, m, facts):
        crews = {"coord": crew.CrewRead("ok", (m,))}
        return stall.asks(self.g, NOW, {}, {}, {}, crews=crews, loop_facts=facts)

    def test_waiting_and_review_are_seen(self):
        old = {"started_at": hours(30), "last_commit_at": hours(20)}
        for m in (crew_module(waiting_user=True, **old), crew_module(review=("rework", 2), **old)):
            with self.subTest(m=m):
                self.assertEqual([a.key for a in self.crew_asks(m)], ["coord|stalled:alpha"])

    def test_waiting_for_the_user_is_not_stall_time(self):
        m = crew_module(started_at=hours(30), last_commit_at=hours(20), waiting_user=True)
        self.assertEqual(self.asks_with(m, [self.loop(waits=[(hours(19), hours(6))])]), [])  # 20 − 13 = 7 hours
        [ask] = self.asks_with(m, [self.loop(waits=[(hours(19), hours(15))])])               # 20 − 4 = 16 hours
        self.assertIn("16 小时没有新提交", ask.text)
        self.assertIn("等你答复的时间不算", ask.text)

    def test_a_looping_module_is_not_woken(self):
        m = crew_module(started_at=hours(30), last_commit_at=hours(20))
        self.assertEqual(self.asks_with(m, [self.loop(hit="你答了 2 次进度没动")]), [])
        self.assertEqual([a.key for a in self.asks_with(m, [self.loop(hit=None)])], ["coord|stalled:alpha"])

    def test_a_looping_plain_line_is_not_woken(self):
        from types import SimpleNamespace as NS
        maps = {"fe": line_map([module("m1")])}
        long = {"fe": health.LineState("stalled", "停住 13 小时", since=hours(13))}
        hit = [NS(key="fe|m1", line="fe", module="m1", waits=(), hit="你答了 2 次进度没动")]
        self.assertEqual(stall.asks(self.g, NOW, long, maps, {}, loop_facts=hit), [])
        self.assertEqual(len(stall.asks(self.g, NOW, long, maps, {})), 1)

    def test_patrol_passes_loop_facts(self):
        crews = {"coord": crew.CrewRead("ok", (crew_module(started_at=hours(30), last_commit_at=hours(20)),))}
        quiet = patrol.plan(self.g, now=NOW, relay=snapshot(agent("coord")), crews=crews,
                            loop_facts=[self.loop(hit="你答了 2 次进度没动")])
        self.assertFalse([a for a in quiet.actions if a.id.startswith("stall:")])
        loud = patrol.plan(self.g, now=NOW, relay=snapshot(agent("coord")), crews=crews)
        self.assertTrue([a for a in loud.actions if a.id == "stall:coord|stalled:alpha"])
