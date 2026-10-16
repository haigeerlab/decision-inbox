import json
import unittest

from helpers import TempHomeTestCase

from decision_inbox import health, relay, specguard, store

NOW = "2026-10-16T12:00:00+08:00"


def at(minutes_ago):
    """ISO time `minutes_ago` minutes before NOW (UTC, like agent-relay)."""
    from datetime import datetime, timedelta
    t = datetime.fromisoformat(NOW) - timedelta(minutes=minutes_ago)
    return t.astimezone().isoformat()


def module(mid="m1", position=1, status="in_progress", step="build", done=1, total=5, plan="approved",
           last_tick=None, first_tick=None, ticks=None, suspended_at=None):
    return {"id": mid, "position": position, "responsibility": "r", "dependsOn": [], "status": status,
            "step": step, "progress": {"done": done, "total": total}, "suspendedReason": None,
            "blockedOn": [], "missingDeps": [], "blocks": {"count": 0, "ids": []},
            "review": {"spec": "approved", "plan": plan}, "lastTickAt": last_tick,
            "firstTickAt": first_tick, "tickCommits": ticks, "suspendedAt": suspended_at}


def line_map(modules, stage="BUILDING", active="m1", history="complete", bottlenecks=()):
    doc = {"schemaVersion": 1, "generatedAt": NOW, "generator": {"name": "spec-guard", "version": "0.63.0"},
           "project": {"root": "/repo", "title": "t"}, "head": {"sha": None, "branch": None, "unmerged": None,
                                                                "unpushed": None},
           "stage": stage, "activeModule": active, "nextGate": None, "history": history, "totals": {},
           "bottlenecks": list(bottlenecks), "awaitingReview": [], "modules": modules}
    return specguard.ReadResult("ok", None, 0, specguard.parse_map(json.dumps(doc)))


def agent(name, app="claude", state="running", activity_ago=60, since_ago=None, waiting=None):
    a = {"name": name, "host": {"app": app, "sessionId": name, "verified": app == "claude"},
         "unread": 0, "lastActivity": at(activity_ago) if activity_ago is not None else None,
         "presence": {"state": state}, "wake": None}
    if since_ago is not None:
        a["presence"]["since"] = at(since_ago)
    if waiting:
        count, senders, oldest_ago = waiting
        a["waiting"] = {"count": count, "from": list(senders), "ids": [1], "oldestAt": at(oldest_ago)}
        a["unread"] = count
    return a


def snapshot(*agents):
    return relay.parse_agents(json.dumps({"count": len(agents), "agents": list(agents)}), relay_version="0.6.10")


class HealthCase(TempHomeTestCase):
    def setUp(self):
        super().setUp()
        self.g, _ = store.init_group("demo")
        people = [
            ("hub", "收件枢纽", "hub", [], "claude-desktop", None),
            ("fe", "前端", "dev", ["前端"], "codex-desktop", "/tmp/fe"),
            ("api", "API", "dev", ["API"], "codex-desktop", "/tmp/api"),
            ("owner", "前端负责人", "owner", ["前端"], "claude-desktop", None),
        ]
        with self.g.transaction() as tx:
            for name, short, role, line, host, repo in people:
                entry = {"relayName": name, "shortName": short, "role": role, "line": line, "host": host}
                if repo:
                    entry["repo"] = repo
                tx.add_session(entry)

    def assess(self, relay_snapshot=None, maps=None, previous=None, now=NOW):
        return health.assess(self.g, now=now, relay=relay_snapshot, maps=maps or {}, previous=previous)


class SnapshotTest(HealthCase):
    def test_first_run_has_no_change_time(self):
        r = self.assess(maps={"fe": line_map([module(done=1)])})
        self.assertEqual(r.snapshot["sessions"]["fe"]["m1"], {"done": 1, "changedAt": None})
        json.dumps(r.snapshot)

    def test_change_time_kept_or_updated(self):
        first = self.assess(maps={"fe": line_map([module(done=1)])}, now=at(30)).snapshot
        first["sessions"]["fe"]["m1"]["changedAt"] = at(40)
        same = self.assess(maps={"fe": line_map([module(done=1)])}, previous=first).snapshot
        self.assertEqual(same["sessions"]["fe"]["m1"]["changedAt"], at(40))
        moved = self.assess(maps={"fe": line_map([module(done=2)])}, previous=first).snapshot
        self.assertEqual(moved["sessions"]["fe"]["m1"], {"done": 2, "changedAt": NOW})

    def test_constants_match_spec(self):
        self.assertEqual((health.REWORK_FALLBACK_ROUNDS, health.REWORK_HISTORY_MIN, health.REWORK_MARGIN), (3, 3, 2))
        self.assertEqual((health.SLOW_FALLBACK_MINUTES, health.SLOW_FACTOR, health.SLOW_FLOOR_MINUTES), (120, 3, 30))
        self.assertEqual((health.BUSY_MINUTES, health.BACKLOG_MINUTES, health.ESCALATE_MINUTES,
                          health.WORKING_MINUTES), (10, 10, 30, 10))

    def test_read_only(self):
        files = {p: p.read_bytes() for p in self.g.path.rglob("*") if p.is_file()}
        self.assess(snapshot(agent("fe")), maps={"fe": line_map([module()])})
        self.assertEqual({p: p.read_bytes() for p in self.g.path.rglob("*") if p.is_file()}, files)


if __name__ == "__main__":
    unittest.main()
