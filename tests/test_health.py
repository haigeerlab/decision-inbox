import json
import unittest

from helpers import TempHomeTestCase

from pathlib import Path

from decision_inbox import health, items, protocol, relay, reviews, specguard, store, tickets

WAIT_USER = (Path(__file__).resolve().parent / "fixtures" / "protocol" / "wait-user.txt").read_text(encoding="utf-8")

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

    def wait(self, waiter="fe", target="API", sent_ago=5, end="无"):
        text = f"【等待其他会话】\n结束：{end}\n在等谁：{target}\n等什么：接口\n"
        return tickets.receive(self.g, text, sender=waiter, relay_id=1, sent_at=at(sent_ago)).opened

    def ask_user(self, sender="fe", stopped=True):
        text = WAIT_USER if stopped else WAIT_USER.replace("是否完全停住：是", "是否完全停住：否")
        return items.receive(self.g, text, sender=sender, relay_id=2, received_at=at(5)).item

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


class StateTest(HealthCase):
    def word(self, r, name="fe"):
        return r.lines[name].word, r.lines[name].text

    def test_order(self):
        self.wait()
        r = self.assess(snapshot(agent("fe", state="stopped", activity_ago=1)))
        self.assertEqual(self.word(r), ("offline", "掉线"))
        r = self.assess(snapshot(agent("fe", state="waiting-approval", activity_ago=1)))
        self.assertEqual(self.word(r), ("needs-user", "等你确认"))
        self.assertNotIn("hub", r.lines)

    def test_blocked(self):
        self.wait(target="API")
        r = self.assess(snapshot(agent("fe", activity_ago=1)))
        self.assertEqual(self.word(r), ("blocked", "阻塞：等 API"))
        self.assertEqual(r.lines["fe"].target, "API")
        no = self.ask_user(sender="api")
        r = self.assess(snapshot(agent("api", activity_ago=1)))
        self.assertEqual(self.word(r, "api"), ("blocked", f"阻塞：等你决定 #{no}"))
        self.assertEqual(r.lines["api"].item, no)

    def test_not_fully_stopped_item_is_not_blocking(self):
        self.ask_user(sender="api", stopped=False)
        r = self.assess(snapshot(agent("api", activity_ago=1)))
        self.assertEqual(r.lines["api"].word, "working")

    def test_working(self):
        r = self.assess(snapshot(agent("fe", activity_ago=5)))
        self.assertEqual(self.word(r), ("working", "干活中"))
        r = self.assess(snapshot(agent("fe", activity_ago=120)))
        self.assertNotEqual(r.lines["fe"].word, "working")
        prev = self.assess(maps={"fe": line_map([module(done=1)])}).snapshot
        prev["sessions"]["fe"]["m1"]["changedAt"] = at(300)
        r = self.assess(snapshot(agent("fe", activity_ago=120)), maps={"fe": line_map([module(done=2)])},
                        previous=prev)
        self.assertEqual(r.lines["fe"].word, "working")

    def test_stalled(self):
        maps = {"fe": line_map([module(last_tick=at(130), first_tick=at(500), ticks=3)])}
        r = self.assess(snapshot(agent("fe", activity_ago=180)), maps=maps)
        self.assertEqual(self.word(r), ("stalled", "停住 2 小时"))
        unapproved = {"fe": line_map([module(plan="pending")])}
        self.assertNotEqual(self.assess(snapshot(agent("fe", activity_ago=180)), maps=unapproved).lines["fe"].word,
                            "stalled")
        finished = {"fe": line_map([module(done=5, total=5)])}
        self.assertNotEqual(self.assess(snapshot(agent("fe", activity_ago=180)), maps=finished).lines["fe"].word,
                            "stalled")

    def test_done_and_idle(self):
        done = {"fe": line_map([module(status="done", step=None, done=5, total=5)], stage="DONE", active=None)}
        r = self.assess(snapshot(agent("fe", activity_ago=180)), maps=done)
        self.assertEqual(self.word(r), ("done", "已结项（空闲）"))
        self.ask_user(sender="fe", stopped=False)
        self.assertEqual(self.assess(snapshot(agent("fe", activity_ago=180)), maps=done).lines["fe"].word, "idle")
        no_map = {"fe": specguard.ReadResult("no-map", "无能力图", 3)}
        r = self.assess(snapshot(agent("fe", activity_ago=180)), maps=no_map)
        self.assertEqual(self.word(r), ("idle", "3 小时无活动"))
        r = self.assess(snapshot(agent("owner", activity_ago=40)))
        self.assertEqual(self.word(r, "owner"), ("idle", "40 分钟无活动"))
        r = self.assess(None)
        self.assertEqual(r.lines["fe"].word, "idle")
        self.assertNotIn("未知", r.lines["fe"].text)


def codes(r):
    return [(x.no, x.code, x.sessions) for x in r.signals]


class SessionSignalTest(HealthCase):
    def test_all_waiting(self):
        self.wait(waiter="fe", target="API")
        quiet = snapshot(agent("fe", activity_ago=60), agent("api", activity_ago=60), agent("owner", activity_ago=60))
        self.assertIn((1, "all-waiting", ("api", "fe", "owner")), codes(self.assess(quiet)))
        busy = snapshot(agent("fe", activity_ago=60), agent("api", activity_ago=5), agent("owner", activity_ago=60))
        self.assertNotIn("all-waiting", [x.code for x in self.assess(busy).signals])

    def test_delivered_not_picked(self):
        self.wait(waiter="fe", target="API")
        r = self.assess(snapshot(agent("fe", activity_ago=60, waiting=(1, ["api"], 30)), agent("api", activity_ago=5)))
        self.assertIn((2, "delivered-not-picked", ("fe", "api")), codes(r))
        self.assertIn("API", [x for x in r.signals if x.code == "delivered-not-picked"][0].text)
        r = self.assess(snapshot(agent("fe", activity_ago=60, waiting=(1, ["owner"], 30)), agent("api", activity_ago=5)))
        self.assertNotIn("delivered-not-picked", [x.code for x in r.signals])

    def test_offline_backlog(self):
        r = self.assess(snapshot(agent("fe", state="stopped", waiting=(3, ["api"], 30))))
        self.assertIn((4, "offline-backlog", ("fe",)), codes(r))
        r = self.assess(snapshot(agent("fe", state="stopped")))
        self.assertNotIn("offline-backlog", [x.code for x in r.signals])

    def test_busy_backlog(self):
        r = self.assess(snapshot(agent("api", since_ago=10, activity_ago=1, waiting=(2, ["fe"], 5))))
        self.assertIn((5, "busy-backlog", ("api",)), codes(r))
        r = self.assess(snapshot(agent("api", since_ago=9, activity_ago=1, waiting=(2, ["fe"], 5))))
        self.assertNotIn("busy-backlog", [x.code for x in r.signals])

    def test_codex_backlog(self):
        r = self.assess(snapshot(agent("fe", app="codex", state="unknown", waiting=(2, ["api"], 11))))
        self.assertIn((10, "codex-backlog", ("fe",)), codes(r))
        self.assertTrue(next(x for x in r.signals if x.code == "codex-backlog").text.endswith("（来源：Codex 桌面版）"))
        r = self.assess(snapshot(agent("fe", app="codex", state="unknown", waiting=(2, ["api"], 9))))
        self.assertNotIn("codex-backlog", [x.code for x in r.signals])
        r = self.assess(snapshot(agent("fe", app="codex", state="running", waiting=(2, ["api"], 30))))
        self.assertNotIn("codex-backlog", [x.code for x in r.signals])


class ProgressSignalTest(HealthCase):
    def kinds(self, r):
        return [x.code for x in r.signals]

    def test_silent_stop_matches_stalled(self):
        maps = {"fe": line_map([module(last_tick=at(130))])}
        r = self.assess(snapshot(agent("fe", activity_ago=180)), maps=maps)
        self.assertEqual(r.lines["fe"].word, "stalled")
        self.assertIn((3, "silent-stop", ("fe",)), codes(r))

    def test_suspended_blocks(self):
        maps = {"fe": line_map([module()], bottlenecks=[{"id": "m0", "suspendedReason": "等上游修复",
                                                          "blocks": ["m1", "m2"]}])}
        r = self.assess(snapshot(agent("fe", activity_ago=1)), maps=maps)
        sig = [x for x in r.signals if x.code == "suspended-blocks"][0]
        self.assertEqual(sig.no, 6)
        self.assertIn("m0", sig.text)
        self.assertIn("挡住 2 个", sig.text)

    def conclude(self, ref, verdict, minutes_ago):
        msg = protocol.parse(f"【审查结论】\n审查编号：{ref}\n节点：Spec\n送审方：前端\n结论：{verdict}\n")
        reviews.record_conclusion(self.g, message=msg, sender="owner", at=at(minutes_ago))

    def register_reviewer(self):
        reviews.register(self.g, session="fe", reviewer="owner", nodes=("spec",), approval_item=None,
                         approval_note="接入时用户确认", at=at(1000))

    def test_rework_fallback(self):
        self.register_reviewer()
        for i in range(2):
            self.conclude("R-1", "有须修改项", 100 - i)
        self.assertNotIn("rework", self.kinds(self.assess()))
        self.conclude("R-1", "有须修改项", 90)
        self.assertIn((7, "rework", ("fe",)), codes(self.assess()))

    def test_rework_against_history(self):
        self.register_reviewer()
        for ref in ("H-1", "H-2", "H-3"):
            self.conclude(ref, "有须修改项", 500)
            self.conclude(ref, "通过", 400)          # median of closed = 2 -> threshold 4
        for i in range(3):
            self.conclude("R-9", "有须修改项", 100 - i)
        self.assertNotIn("rework", self.kinds(self.assess()))
        self.conclude("R-9", "有须修改项", 90)
        self.assertIn("rework", self.kinds(self.assess()))

    def test_slow_with_history(self):
        # 3 ticks over 40 minutes -> average 20 minutes -> threshold max(60, 30) = 60 minutes
        mod = module(last_tick=at(70), first_tick=at(110), ticks=3)
        r = self.assess(snapshot(agent("fe", activity_ago=1)), maps={"fe": line_map([mod])})
        self.assertIn((8, "slow-progress", ("fe",)), codes(r))
        mod = module(last_tick=at(50), first_tick=at(90), ticks=3)
        r = self.assess(snapshot(agent("fe", activity_ago=1)), maps={"fe": line_map([mod])})
        self.assertNotIn("slow-progress", self.kinds(r))

    def test_slow_fallback(self):
        for ago, expected in ((119, False), (120, True)):
            with self.subTest(ago=ago):
                mod = module(last_tick=at(ago), first_tick=at(ago), ticks=1)
                r = self.assess(snapshot(agent("fe", activity_ago=1)), maps={"fe": line_map([mod])})
                self.assertEqual("slow-progress" in self.kinds(r), expected)

    def test_snapshot_change_beats_old_tick(self):
        prev = self.assess(maps={"fe": line_map([module(done=1)])}).snapshot
        prev["sessions"]["fe"]["m1"]["changedAt"] = at(500)
        mod = module(done=2, last_tick=at(600), first_tick=at(900), ticks=3)
        r = self.assess(snapshot(agent("fe", activity_ago=1)), maps={"fe": line_map([mod])}, previous=prev)
        self.assertNotIn("slow-progress", self.kinds(r))

    def test_shallow_history_ignores_ticks(self):
        mod = module(last_tick=at(600), first_tick=at(900), ticks=3)
        r = self.assess(snapshot(agent("fe", activity_ago=1)), maps={"fe": line_map([mod], history="shallow")})
        self.assertNotIn("slow-progress", self.kinds(r))   # no snapshot either: nothing to judge by
        prev = self.assess(maps={"fe": line_map([module(done=1)])}).snapshot
        prev["sessions"]["fe"]["m1"]["changedAt"] = at(130)
        r = self.assess(snapshot(agent("fe", activity_ago=1)),
                        maps={"fe": line_map([module(done=1, last_tick=at(1), first_tick=at(900), ticks=9)],
                                             history="shallow")}, previous=prev)
        self.assertIn("slow-progress", self.kinds(r))      # 130 minutes since the snapshot change, fallback 120

    def test_orphan_wait(self):
        old = self.wait(waiter="fe", target="API", sent_ago=60)
        self.wait(waiter="fe", target="前端负责人", sent_ago=30)
        self.wait(waiter="api", target="前端", sent_ago=10)
        r = self.assess()
        orphans = [x for x in r.signals if x.code == "orphan-wait"]
        self.assertEqual([(x.no, x.sessions) for x in orphans], [(9, ("fe",))])
        self.assertIn(f"#{old}", orphans[0].text)


if __name__ == "__main__":
    unittest.main()


def with_activity(a, activity):
    a["presence"]["activity"] = activity
    return a


class PresenceActivityTest(HealthCase):
    """relay-presence-and-doubt Task 2."""

    def test_busy_counts_idle_does_not(self):
        r = self.assess(snapshot(with_activity(agent("owner", activity_ago=120), "busy")))
        self.assertEqual(r.lines["owner"].word, "working")
        r = self.assess(snapshot(with_activity(agent("owner", activity_ago=1), "idle")))
        self.assertNotEqual(r.lines["owner"].word, "working")

    def test_idle_backlog_is_not_called_busy(self):
        idle = with_activity(agent("owner", activity_ago=1, since_ago=30, waiting=(2, ["fe"], 20)), "idle")
        r = self.assess(snapshot(idle))
        self.assertNotIn("busy-backlog", [x.code for x in r.signals])
        sig = next(x for x in r.signals if x.code == "idle-backlog")
        self.assertEqual((sig.no, sig.text), (5, "前端负责人 空闲，有 2 条消息没读"))
        busy = with_activity(agent("owner", activity_ago=1, since_ago=30, waiting=(2, ["fe"], 20)), "busy")
        self.assertIn("busy-backlog", [x.code for x in self.assess(snapshot(busy)).signals])

    def test_no_relay_no_all_waiting(self):
        self.wait()
        self.assertNotIn("all-waiting", [x.code for x in self.assess(None).signals])
        r = self.assess(snapshot(agent("fe", activity_ago=120), agent("api", activity_ago=120),
                                 agent("owner", activity_ago=120)))
        self.assertIn("all-waiting", [x.code for x in r.signals])


class HonestLineTest(HealthCase):
    """relay-presence-and-doubt Task 2: skip possibly stale tickets, show short names."""

    def test_short_name_for_relay_target(self):
        self.wait(target="api")
        r = self.assess(snapshot(agent("fe", activity_ago=1)))
        self.assertEqual(r.lines["fe"].text, "阻塞：等 API")

    def test_stale_ticket_skipped(self):
        self.wait(target="API")
        self.ask_user(sender="fe")                   # fe moved on: a later message to the hub
        with self.g.transaction() as tx:
            tx.write_state("hub", {"received": {"9": {"at": at(1), "kind": "wait-user", "returned": False,
                                                      "sender": "fe"}}})
        r = self.assess(snapshot(agent("fe", activity_ago=1)))
        self.assertTrue(r.lines["fe"].text.startswith("阻塞：等你决定 #"), r.lines["fe"].text)


class DeliveryDoubtTest(HealthCase):
    """relay-presence-and-doubt Task 3."""

    def test_signal_11(self):
        a = agent("fe", app="codex", activity_ago=1, waiting=(2, ["hub"], 10))
        a["waiting"]["doubtfulIds"] = [8, 9]
        sig = next(x for x in self.assess(snapshot(a)).signals if x.code == "delivery-doubt")
        self.assertEqual((sig.no, sig.sessions), (11, ("fe",)))
        self.assertEqual(sig.text, "前端 有 2 条消息送达存疑（#8、#9）（来源：agent-relay）")
        self.assertNotIn("delivery-doubt",
                         [x.code for x in self.assess(snapshot(agent("fe", app="codex", activity_ago=1))).signals])


from decision_inbox import crew  # noqa: E402

CREW = crew.CrewRead("ok", (crew.Module("a", "shop-a", "build", None),
                            crew.Module("b", "shop-b", "wait-merge", None),
                            crew.Module("c", "shop-c", "build", "等接口"),
                            crew.Module("d", "shop-d", "merged", None)))


class CrewLineTest(HealthCase):
    """crew-line-status Task 2: a coordinator's line counts its module sessions."""

    def setUp(self):
        super().setUp()
        with self.g.transaction() as tx:
            tx.add_session({"relayName": "coord", "shortName": "门店", "role": "dev", "line": ["门店"],
                            "host": "claude-desktop", "repo": "/tmp/coord", "crewCoordinator": True})

    def quiet(self, *extra):
        return [agent(n, activity_ago=60) for n in ("fe", "api", "owner", "coord")] + list(extra)

    def run_(self, agents, read=CREW, maps=None):
        return health.assess(self.g, now=NOW, relay=snapshot(*agents) if agents is not None else None,
                             maps=maps or {}, crews={"coord": read})

    def test_busy_module_beats_blocked_and_lists_all_tickets(self):
        one, two = self.wait("coord", "API"), self.wait("coord", "API")
        r = self.run_(self.quiet(with_activity(agent("shop-a", activity_ago=1), "busy"),
                                 with_activity(agent("shop-b", activity_ago=1), "idle"),
                                 with_activity(agent("shop-c", activity_ago=1), "busy")))
        self.assertEqual((r.lines["coord"].word, r.lines["coord"].text),
                         ("working", f"干活中（模块 a 在忙·构建、b 停着·等合并、c 挂起：等接口；还在等 API #{one}、#{two}）"))
        self.assertNotIn("all-waiting", [x.code for x in r.signals])

    def test_all_modules_quiet_is_blocked_and_all_waiting(self):
        self.wait("coord", "API")
        r = self.run_(self.quiet(with_activity(agent("shop-a", activity_ago=1), "idle"),
                                 agent("shop-b", state="stopped"),
                                 with_activity(agent("shop-c", activity_ago=1), "busy")))
        self.assertEqual(r.lines["coord"].text,
                         "阻塞：等 API（模块 a 停着·构建、b 停着·等合并、c 挂起：等接口）")
        self.assertIn("all-waiting", [x.code for x in r.signals])

    def test_unknown_output(self):
        self.wait("coord", "API")
        r = self.run_(self.quiet(), read=crew.CrewRead("unknown", (), "不在 git 仓库里"))
        self.assertEqual(r.lines["coord"].text, "阻塞：等 API（模块状态未知：不在 git 仓库里）")
        self.assertNotIn("all-waiting", [x.code for x in r.signals])

    def test_missing_agent_and_old_relay(self):
        r = self.run_(self.quiet())
        self.assertIn("a 无记录·构建", r.lines["coord"].text)
        old = self.run_(self.quiet(agent("shop-a", activity_ago=3)))
        self.assertEqual(old.lines["coord"].word, "working")

    def test_without_relay_only_stages(self):
        r = self.run_(None)
        self.assertEqual(r.lines["coord"].text, f"{health.NO_RELAY}（模块 a 构建、b 等合并、c 挂起：等接口）")

    def test_long_suspend_reason_is_cut(self):
        read = crew.CrewRead("ok", (crew.Module("c", "shop-c", "build", "一" * 25),))
        self.assertIn("c 挂起：" + "一" * 20 + "…）", self.run_(self.quiet(), read=read).lines["coord"].text)

    def test_coordinator_line_is_never_stalled(self):
        maps = {"coord": line_map([module(last_tick=at(130), first_tick=at(500), ticks=3)]),
                "fe": line_map([module(last_tick=at(130), first_tick=at(500), ticks=3)])}
        agents = [agent(n, activity_ago=180) for n in ("fe", "api", "owner", "coord")]
        r = self.run_(agents, maps=maps)
        self.assertNotEqual(r.lines["coord"].word, "stalled")
        self.assertEqual(r.lines["fe"].word, "stalled")
        self.assertEqual([x.sessions for x in r.signals if x.no == 3], [("fe",)])

    def test_no_crews_argument_changes_nothing(self):
        self.wait("coord", "API")
        r = health.assess(self.g, now=NOW, relay=snapshot(*self.quiet()), maps={})
        self.assertEqual(r.lines["coord"].text, "阻塞：等 API")


class LeftEntryTest(HealthCase):
    """rehearsal2-fixes Task 1: a session that left is not a line any more."""

    def leave(self, name):
        with self.g.transaction() as tx:
            doc = tx.read_state("onboarding")
            doc.setdefault("left", {})[name] = at(60)
            tx.write_state("onboarding", doc)

    def test_left_session_has_no_line_or_signal(self):
        self.leave("api")
        r = self.assess(snapshot(agent("api", activity_ago=1, waiting=(3, ["fe"], 30), state="stopped")))
        self.assertNotIn("api", r.lines)
        self.assertFalse([s for s in r.signals if "api" in s.sessions])
        self.assertIn("fe", r.lines)

    def test_wait_on_left_session_still_names_it(self):
        self.leave("api")
        self.wait(target="API")
        r = self.assess(snapshot(agent("fe", activity_ago=1)))
        self.assertEqual(r.lines["fe"].text, "阻塞：等 API")


class StoppedTest(HealthCase):
    """rehearsal2-fixes Task 2: a Claude session the app put away is not 掉线 while it can be woken."""

    def word(self, r, name):
        return r.lines[name].word, r.lines[name].text

    def claude(self, name, state="stopped", wake=False, **kw):
        a = agent(name, state=state, **kw)
        if wake:
            a["wake"] = {"app": "claude", "sessionId": name}
        return a

    def set_desktop(self, name):
        with self.g.transaction() as tx:
            entry = dict(store.find_session(self.g, relay_name=name), desktopSession=f"local_{name}")
            tx.replace_session(entry)

    def test_stopped_with_desktop_session_is_not_offline(self):
        self.set_desktop("owner")
        r = self.assess(snapshot(self.claude("owner", activity_ago=3)))
        self.assertEqual(self.word(r, "owner"), ("idle", "3 分钟无活动"))

    def test_stopped_with_wake_binding_is_not_offline(self):
        r = self.assess(snapshot(self.claude("owner", wake=True, activity_ago=3)))
        self.assertNotEqual(r.lines["owner"].word, "offline")

    def test_stopped_unwakeable_is_offline(self):
        r = self.assess(snapshot(self.claude("owner", activity_ago=3)))
        self.assertEqual(self.word(r, "owner"), ("offline", "掉线"))

    def test_unreachable_is_offline(self):
        self.set_desktop("owner")
        r = self.assess(snapshot(self.claude("owner", state="unreachable", wake=True)))
        self.assertEqual(self.word(r, "owner"), ("offline", "掉线"))

    def test_codex_stopped_stays_offline(self):
        a = agent("fe", app="codex", state="stopped")
        a["wake"] = {"app": "codex", "sessionId": "fe"}
        r = self.assess(snapshot(a))
        self.assertEqual(self.word(r, "fe"), ("offline", "掉线"))

    def test_stopped_wakeable_still_blocked(self):
        self.set_desktop("owner")
        self.wait(waiter="owner", target="API")
        r = self.assess(snapshot(self.claude("owner", activity_ago=1)))
        self.assertEqual(r.lines["owner"].word, "blocked")

    def test_backlog_text_for_wakeable_session(self):
        self.set_desktop("owner")
        r = self.assess(snapshot(self.claude("owner", waiting=(2, ["fe"], 30))))
        s = next(x for x in r.signals if x.code == "offline-backlog")
        self.assertEqual(s.text, "前端负责人 停着，有 2 条消息等它")

    def test_module_word(self):
        now = health._instant(NOW)
        self.assertEqual(health._module_word(snapshot(self.claude("m", wake=True)).agents["m"], now), "停着")
        self.assertEqual(health._module_word(snapshot(self.claude("m")).agents["m"], now), "停着")
        self.assertEqual(health._module_word(snapshot(self.claude("m", state="unreachable")).agents["m"], now), "掉线")
