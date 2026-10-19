"""loop-detection (R21 DI-5, DI-6): which module each question belongs to, and the module's facts."""

from datetime import datetime, timedelta
from types import SimpleNamespace as NS

from helpers import TempHomeTestCase

from decision_inbox import crew, loops, store

T0 = "2026-10-19T08:00:00+08:00"


def at(hours: float) -> str:
    return (datetime.fromisoformat(T0) + timedelta(hours=hours)).isoformat()


def fact(module_id, gates=3, done=2, total=5, last_tick=None):
    return NS(id=module_id, gates_total=gates, gates_done=None if gates is None else 0, progress_done=done,
              progress_total=total, last_tick_at=last_tick, status="in_progress")


def line_map(active="m1", stage="BUILDING", title="演示项目", modules=None):
    return NS(status="ok", map=NS(active_module=active, stage=stage, title=title,
                                  modules=tuple(modules if modules is not None else [fact(active)])))


def crew_read(*modules):
    return NS(status="ok", modules=tuple(modules))


def crew_module(module="alpha", started=T0, answers=(), waits=(), ask_refs=(), last_commit=None, stage="build"):
    return crew.Module(module, f"rh-{module}", stage, None, started_at=started, last_commit_at=last_commit,
                       ask_refs=tuple(ask_refs), waits=tuple(waits), answers=answers)


class LoopsCase(TempHomeTestCase):
    def setUp(self):
        super().setUp()
        self.g, _ = store.init_group("demo")
        self.no = 0
        with self.g.transaction() as tx:
            tx.add_session({"relayName": "fe", "shortName": "前端", "role": "dev", "line": ["前端"],
                            "host": "claude-desktop", "repo": "/tmp/fe"})
            tx.add_session({"relayName": "co", "shortName": "协调", "role": "dev", "line": ["协调"],
                            "host": "claude-desktop", "repo": "/tmp/co", "crewCoordinator": True})
            tx.add_session({"relayName": "own", "shortName": "审查", "role": "owner", "line": ["前端"],
                            "host": "claude-desktop"})

    def item(self, sender="fe", received=T0, answered=None, decide="要不要换分页", status=None, closed=None,
             module=..., approval=None, kind=None, multi=False):
        self.no += 1
        it = {"sender": sender, "receivedAt": received, "decide": decide, "multi": multi, "project": "",
              "approvalModule": approval, "approvalNode": "spec" if approval else None, "waitKind": kind,
              "answers": [{"letter": "A", "original": "A", "at": answered}] if answered else [],
              "status": status or ("forwarded" if answered else "pending"), "statusAt": {"pending": received}}
        if closed:
            it["statusAt"][it["status"]] = closed
        if module is not ...:
            it["module"] = module
        with self.g.transaction() as tx:
            doc = tx.read_state("items") or {}
            doc.setdefault("items", {})[str(self.no)] = it
            tx.write_state("items", doc)
        return self.no

    def module_of(self, no):
        return store.read_state(self.g, "items")["items"][str(no)].get("module", "untagged")

    def facts(self, maps=None, crews=None, now=None, commits=None):
        found = loops.facts(self.g, now or at(30), maps if maps is not None else {"fe": line_map()},
                            crews or {}, git=lambda repo, since: commits)
        return {f.key: f for f in found}


class TagTest(LoopsCase):
    def test_three_sources_and_misses(self):
        approval = self.item(approval="m9")
        plain = self.item()
        crew_hit = self.item(sender="co", decide="要不要再试一次\n细节")
        crew_miss = self.item(sender="co", decide="别的事")
        multi = self.item(sender="own", multi=True)
        unread = self.item(sender="fe")
        maps = {"fe": line_map("m1"), "co": line_map("alpha")}
        crews = {"co": crew_read(crew_module(waits=[crew.Wait("C31", "open", "要不要再试一次", T0)]))}
        loops.tag(self.g, maps, crews)
        self.assertEqual([self.module_of(n) for n in (approval, plain, crew_hit, crew_miss, multi, unread)],
                         ["m9", "m1", "alpha", None, None, "m1"])
        events = [e for e in store.read_events(self.g) if e["type"] == "items.module-tagged"]
        self.assertEqual(len(events), 6)

    def test_unreadable_map_tags_null_and_tags_never_change(self):
        no = self.item()
        loops.tag(self.g, {"fe": NS(status="timeout", map=None)}, {})
        self.assertIsNone(self.module_of(no))
        later = self.item()
        loops.tag(self.g, {"fe": line_map("m1")}, {})
        loops.tag(self.g, {"fe": line_map("m2")}, {})
        self.assertEqual((self.module_of(no), self.module_of(later)), (None, "m1"))


class SingleLineFactsTest(LoopsCase):
    def test_counts_baseline_and_progress(self):
        for _ in range(5):
            self.item(module="m1", answered=at(1))
        self.item(module="m1", kind="go-to-session")
        self.item(module="m1", status="superseded", closed=at(2))
        self.item(module="other")
        f = self.facts()["fe|m1"]
        self.assertEqual((f.asked, f.baseline, f.over), (5, 5, 0))
        self.item(module="m1")
        f = self.facts()["fe|m1"]
        self.assertEqual((f.asked, f.over, f.progress), (6, 1, (2, 5)))
        self.assertEqual(f.project, "演示项目")

    def test_unknown_baseline(self):
        self.item(module="m1")
        f = self.facts({"fe": line_map(modules=[fact("m1", gates=None)])})["fe|m1"]
        self.assertIsNone(f.baseline)
        self.assertEqual(f.over, 0)

    def test_segments_from_commits(self):
        self.item(module="m1", received=at(0), answered=at(1))
        self.item(module="m1", received=at(3), answered=at(4))
        self.item(module="m1", received=at(6))
        f = self.facts(commits=[at(2)], now=at(7))["fe|m1"]
        self.assertEqual([(s.moved, s.closed) for s in f.segments], [(True, True), (False, True)])
        self.assertEqual(f.still, 1)
        self.assertEqual(f.segments[1].worked_until, at(6))

    def test_git_unreadable(self):
        self.item(module="m1", answered=at(1))
        f = self.facts(commits=None)["fe|m1"]
        self.assertIsNone(f.still)
        self.assertIn("读不到", f.unread)

    def test_worked_hours_minus_waits(self):
        self.item(module="m1", received=at(0), answered=at(2))          # waits 0–2
        self.item(module="m1", received=at(1), kind="go-to-session",     # overlaps 1–3: only 2–3 is new
                  status="closed", closed=at(3))
        with self.g.transaction() as tx:
            tx.write_state("tickets", {"tickets": {"90": {"waiter": "fe", "sentAt": at(5), "status": "closed",
                                                          "close": {"at": at(6)}},
                                                   "91": {"waiter": "co", "sentAt": at(5), "status": "open",
                                                          "close": None}}})
        f = self.facts(commits=[], now=at(10))["fe|m1"]
        self.assertAlmostEqual(f.worked_hours, 10 - 3 - 1)

    def test_last_progress_and_done_line(self):
        self.item(module="m1", received=at(0))
        f = self.facts({"fe": line_map(modules=[fact("m1", last_tick=at(5))])}, commits=[at(3)])["fe|m1"]
        self.assertEqual(f.last_progress, at(5))
        self.assertEqual(self.facts({"fe": line_map(stage="DONE")}), {})


class CrewFactsTest(LoopsCase):
    def crews(self, **kw):
        return {"co": crew_read(crew_module(**kw))}

    def test_segments_from_answers(self):
        self.item(sender="co", module="alpha", received=at(0), answered=at(1))
        answers = (crew.Answer("C1", at(1), 0, 0), crew.Answer("C2", at(4), 0, 1))
        f = self.facts({"co": line_map("x", modules=[fact("alpha")])},
                       self.crews(answers=answers, ask_refs=[("C1", at(0)), ("C2", at(3))]), now=at(5))["co|alpha"]
        self.assertEqual([(s.moved, s.closed) for s in f.segments], [(False, True), (True, False)])
        self.assertEqual((f.still, f.asked, f.progress), (1, 1, (2, 5)))

    def test_null_and_before_050(self):
        f = self.facts({}, self.crews(answers=(crew.Answer("C1", at(1), None, 0),)))["co|alpha"]
        self.assertIsNone(f.still)
        self.assertIn("读不到", f.unread)
        f = self.facts({}, self.crews(answers=None))["co|alpha"]
        self.assertIn("0.5.0", f.unread)
        self.assertIsNone(f.baseline)  # no map for the coordinator: unknown

    def test_merged_and_suspended_are_not_in_progress(self):
        self.assertEqual(self.facts({}, self.crews(stage="merged")), {})

    def test_worked_hours_from_started_at(self):
        self.item(sender="co", module="alpha", received=at(1), answered=at(3))
        f = self.facts({}, self.crews(started=at(0), answers=()), now=at(10))["co|alpha"]
        self.assertAlmostEqual(f.worked_hours, 8)


class ReadCommitsTest(TempHomeTestCase):
    def test_real_repo_and_missing(self):
        import subprocess
        repo = self.home / "r"
        repo.mkdir()
        run = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)  # noqa: E731
        run("init", "-q")
        run("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "x")
        got = loops.read_commits(str(repo), "2000-01-01T00:00:00+00:00")
        self.assertEqual(len(got), 1)
        self.assertIsNone(loops.read_commits(str(self.home / "nope"), T0))
