import hashlib
import unittest
from datetime import datetime, timedelta
from unittest import mock

from helpers import TempHomeTestCase
from test_health import NOW, agent, snapshot

from decision_inbox import patrol, store
from decision_inbox.health import Assessment, Signal

HUB_DESKTOP = "local_00000000-0000-0000-0000-00000000hub0"
OWNER_DESKTOP = "local_00000000-0000-0000-0000-0000000own1"


def later(minutes: float) -> str:
    """An instant `minutes` after NOW (rounds move forward in time)."""
    return (datetime.fromisoformat(NOW) + timedelta(minutes=minutes)).isoformat()


class PatrolCase(TempHomeTestCase):
    def setUp(self):
        super().setUp()
        self.g, _ = store.init_group("demo")
        people = [
            ("hub", "收件枢纽", "hub", [], "claude-desktop", None, HUB_DESKTOP),
            ("fe", "前端", "dev", ["前端"], "codex-desktop", "/tmp/fe", None),
            ("api", "API", "dev", ["API"], "codex-desktop", "/tmp/api", None),
            ("fe-owner", "前端负责人", "owner", ["前端"], "claude-desktop", None, OWNER_DESKTOP),
            ("api-owner", "API负责人", "owner", ["API"], "claude-desktop", None, None),
        ]
        with self.g.transaction() as tx:
            for name, short, role, line, host, repo, desktop in people:
                entry = {"relayName": name, "shortName": short, "role": role, "line": line, "host": host}
                if repo:
                    entry["repo"] = repo
                if desktop:
                    entry["desktopSession"] = desktop
                tx.add_session(entry)

    def run_round(self, minutes, agents=(), maps=None, failed=(), relay="build"):
        now = later(minutes)
        relay_snapshot = snapshot(*agents) if relay == "build" else relay
        p = patrol.plan(self.g, now=now, relay=relay_snapshot, maps=maps or {})
        ids = [a.id for a in p.actions]
        patrol.record(self.g, p.to_json(), done=[i for i in ids if i not in failed], failed=list(failed), now=now)
        return p

    def ids(self, p):
        return [a.id for a in p.actions]

    def digest(self):
        return {str(f.relative_to(self.g.path)): hashlib.sha256(f.read_bytes()).hexdigest()
                for f in sorted(self.g.path.rglob("*")) if f.is_file()}


STOPPED_OWNER = dict(state="stopped", waiting=(2, ["fe"], 5))


class WakeTest(PatrolCase):
    def test_wake_then_unwakeable_then_quiet_then_cleared(self):
        owner = agent("fe-owner", **STOPPED_OWNER)
        first = self.run_round(0, [owner])
        self.assertIn("wake:fe-owner", self.ids(first))
        wake = next(a for a in first.actions if a.id == "wake:fe-owner")
        self.assertEqual((wake.kind, wake.target), ("wake", OWNER_DESKTOP))
        self.assertEqual(wake.text, "【decision-inbox 巡视】你有 2 条消息在等，请查看收件箱后继续。")
        second = self.run_round(5, [owner])
        self.assertEqual([i for i in self.ids(second) if "fe-owner" in i], ["notify:unwakeable:fe-owner"])
        self.assertTrue(next(a for a in second.actions if a.id.startswith("notify:unwakeable")).text
                        .startswith("decision-inbox：叫不醒 前端负责人"))
        for minutes in (10, 12):  # still stopped: neither another wake nor another notice
            quiet = self.run_round(minutes, [owner])
            self.assertEqual([i for i in self.ids(quiet) if "fe-owner" in i], [], minutes)
        self.run_round(15, [agent("fe-owner", state="running", activity_ago=0)])
        again = self.run_round(20, [owner])
        self.assertIn("wake:fe-owner", self.ids(again))

    def test_unregistered_desktop_session_notifies(self):
        p = self.run_round(0, [agent("api-owner", **dict(STOPPED_OWNER, waiting=(1, ["api"], 5)))])
        self.assertEqual([i for i in self.ids(p) if "api-owner" in i], ["notify:unwakeable:api-owner"])
        self.assertIn("没登记", next(a.text for a in p.actions if a.id == "notify:unwakeable:api-owner"))

    def test_codex_and_quiet_sessions_get_nothing(self):
        p = self.run_round(0, [agent("fe", app="codex", state="stopped", waiting=(3, ["api"], 30)),
                               agent("fe-owner", state="stopped")])
        self.assertEqual(self.ids(p), [])

    def test_hub_woken_when_there_is_news(self):
        hub = agent("hub", state="stopped")
        p = self.run_round(0, [hub, agent("api-owner", **STOPPED_OWNER)])
        self.assertIn("wake:hub", self.ids(p))
        self.assertIn("notify:unwakeable:api-owner", self.ids(p))
        quiet = self.run_round(5, [hub, agent("api-owner", **STOPPED_OWNER)])
        self.assertNotIn("wake:hub", self.ids(quiet))
        alone = self.run_round(10, [hub])
        self.assertNotIn("wake:hub", self.ids(alone))

    def test_same_now_twice_is_quiet(self):
        owner = agent("fe-owner", **STOPPED_OWNER)
        self.assertTrue(self.ids(self.run_round(0, [owner])))
        self.assertEqual(self.ids(self.run_round(0, [owner])), [])


class RecordTest(PatrolCase):
    def test_plan_is_read_only_and_record_writes_patrol_only(self):
        owner = agent("fe-owner", **STOPPED_OWNER)
        self.run_round(0, [owner])
        before = self.digest()
        p = patrol.plan(self.g, now=later(5), relay=snapshot(owner), maps={})
        self.assertEqual(self.digest(), before)
        patrol.record(self.g, p.to_json(), done=[a.id for a in p.actions], now=later(5))
        changed = {k for k, v in self.digest().items() if before.get(k) != v}
        self.assertTrue(changed <= {"state/patrol.json", "events.jsonl"}, changed)
        last = store.read_events(self.g)[-1]
        self.assertEqual(last["type"], "patrol.run")
        self.assertEqual(last["data"]["done"], [a.id for a in p.actions])

    def test_snapshot_saved_for_line_health(self):
        self.run_round(0)
        self.assertEqual(store.read_state(self.g, "patrol")["snapshot"]["at"], later(0))

    def test_failed_wake_counts_as_tried(self):
        owner = agent("fe-owner", **STOPPED_OWNER)
        self.run_round(0, [owner], failed=["wake:fe-owner"])
        self.assertIn("notify:unwakeable:fe-owner", self.ids(self.run_round(5, [owner])))


def with_signals(*signals):
    """Patch line-health so a round sees exactly these signals."""
    return mock.patch("decision_inbox.patrol.health.assess",
                      lambda g, now, relay, maps, previous: Assessment({}, tuple(signals), {"version": 1, "at": now,
                                                                                             "sessions": {}}))


STALL = Signal(3, "silent-stop", ("fe",), "前端 停住 2 小时：当前模块 pay 还有 3 项没勾，也没在等任何人")


class AlertTest(PatrolCase):
    def rounds(self, signal, minutes_list, agents=(), failed=()):
        out = []
        with with_signals(signal):
            for minutes in minutes_list:
                out.append(self.ids(self.run_round(minutes, agents, failed=failed if minutes == minutes_list[0] else ())))
        return out

    def test_alert_wait_escalate_once(self):
        key = "3|fe"
        rounds = self.rounds(STALL, [0, 5, 29, 30, 35])
        self.assertEqual(rounds[0], [f"alert:{key}"])
        self.assertEqual(rounds[1:3], [[], []])
        self.assertEqual(rounds[3], [f"notify:escalate:{key}"])
        self.assertEqual(rounds[4], [])

    def test_alert_text_and_target(self):
        with with_signals(STALL):
            p = self.run_round(0)
        alert = p.actions[0]
        self.assertEqual((alert.kind, alert.target), ("owner-alert", "fe-owner"))
        self.assertEqual(alert.text, "【进度预警】前端：前端 停住 2 小时：当前模块 pay 还有 3 项没勾，也没在等任何人。"
                                     "建议：问 前端 是否卡住，或让它继续或上抛")

    def test_each_progress_signal_goes_to_owner(self):
        for no in (3, 6, 7, 8, 9):
            with self.subTest(no=no):
                signal = Signal(no, "x", ("api",), f"API 的说明 {no}，等待单 #7")
                with with_signals(signal):
                    p = self.run_round(no * 100)
                self.assertEqual([(a.kind, a.target) for a in p.actions], [("owner-alert", "api-owner")])

    def test_cleared_signal_starts_over(self):
        self.rounds(STALL, [0])
        with with_signals():
            self.run_round(5)
        self.assertEqual(self.rounds(STALL, [10])[0], ["alert:3|fe"])

    def test_no_owner_offline_owner_or_failed_alert_goes_to_user(self):
        with self.g.transaction() as tx:
            tx.add_session({"relayName": "bg", "shortName": "后台", "role": "dev", "line": ["后台"],
                            "host": "codex-desktop", "repo": "/tmp/bg"})
        orphan = Signal(8, "slow-progress", ("bg",), "后台 的 jobs 已 3 小时没有新进展，明显慢于平时")
        self.assertEqual(self.rounds(orphan, [0, 5]), [["notify:signal:8|bg"], []])
        offline_owner = agent("fe-owner", state="stopped")
        self.assertEqual(self.rounds(STALL, [10], agents=[offline_owner])[0], ["notify:signal:3|fe"])
        with with_signals():
            self.run_round(15)
        self.assertEqual(self.rounds(STALL, [20, 25], failed=["alert:3|fe"]), [["alert:3|fe"], ["notify:signal:3|fe"]])

    def test_other_signals_do_nothing(self):
        for no in (2, 4, 5, 10):
            with self.subTest(no=no):
                with with_signals(Signal(no, "x", ("fe", "api"), "说明")):
                    self.assertEqual(self.ids(self.run_round(no * 100)), [])


if __name__ == "__main__":
    unittest.main()
