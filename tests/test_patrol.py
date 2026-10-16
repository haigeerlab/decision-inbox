import hashlib
import unittest
from datetime import datetime, timedelta

from helpers import TempHomeTestCase
from test_health import NOW, agent, snapshot

from decision_inbox import patrol, store

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


if __name__ == "__main__":
    unittest.main()
