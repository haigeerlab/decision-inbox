import json
import unittest

from helpers import TempHomeTestCase

from decision_inbox import protocol, reviews, store

T0 = "2026-10-16T10:00:00+08:00"
T1 = "2026-10-16T11:00:00+08:00"
T2 = "2026-10-16T12:00:00+08:00"
T3 = "2026-10-16T13:00:00+08:00"


class ReviewsCase(TempHomeTestCase):
    def setUp(self):
        super().setUp()
        self.g, _ = store.init_group("demo")
        with self.g.transaction() as tx:
            tx.add_session({"relayName": "hub", "shortName": "收件枢纽", "role": "hub", "line": [],
                            "host": "claude-desktop"})
            tx.add_session({"relayName": "fe-codex", "shortName": "前端", "role": "dev", "line": ["前端"],
                            "host": "codex-desktop", "repo": "/tmp/fe"})
            tx.add_session({"relayName": "fe-owner", "shortName": "前端负责人", "role": "owner", "line": ["前端"],
                            "host": "claude-desktop"})
            tx.add_session({"relayName": "coord", "shortName": "总协调", "role": "coordinator", "line": [],
                            "host": "codex-desktop"})

    def register(self, at=T1, nodes=("spec", "plan", "interface", "final"), **kw):
        args = dict(session="fe-codex", reviewer="fe-owner", nodes=nodes, approval_item=12,
                    approval_note="用户原话：12 A", at=at)
        args.update(kw)
        reviews.register(self.g, **args)


class RegistrationTest(ReviewsCase):
    def test_effective_time_and_event(self):
        self.register()
        self.assertIsNone(reviews.registration_at(self.g, "fe-codex", at=T0))
        reg = reviews.registration_at(self.g, "fe-codex", at=T2)
        self.assertEqual((reg.reviewer, reg.nodes), ("fe-owner", ("spec", "plan", "interface", "final")))
        events = store.read_events(self.g, ref=12)
        self.assertEqual(events[-1]["type"], "reviews.registered")
        self.assertEqual(events[-1]["data"]["approvalNote"], "用户原话：12 A")

    def test_time_zones_compare_as_instants(self):
        self.register(at="2026-10-16T03:00:00Z")  # == 11:00 +08:00
        self.assertIsNone(reviews.registration_at(self.g, "fe-codex", at="2026-10-16T10:59:59+08:00"))
        self.assertIsNotNone(reviews.registration_at(self.g, "fe-codex", at="2026-10-16T11:00:00+08:00"))

    def test_change_keeps_history(self):
        self.register()
        self.register(at=T2, nodes=("spec",), approval_item=13)
        self.assertEqual(reviews.registration_at(self.g, "fe-codex", at=T1).nodes,
                         ("spec", "plan", "interface", "final"))
        self.assertEqual(reviews.registration_at(self.g, "fe-codex", at=T3).nodes, ("spec",))

    def test_unregister(self):
        self.register()
        reviews.unregister(self.g, session="fe-codex", approval_item=15, approval_note="用户原话：15 A", at=T2)
        self.assertIsNotNone(reviews.registration_at(self.g, "fe-codex", at=T1))
        self.assertIsNone(reviews.registration_at(self.g, "fe-codex", at=T3))
        with self.assertRaises(reviews.InvalidRegistration):
            reviews.unregister(self.g, session="fe-codex", approval_item=16, approval_note="x", at=T3)

    def test_invalid_registrations_change_nothing(self):
        before = (self.g.path / "events.jsonl").read_bytes()
        cases = {
            "reviewer not owner": dict(reviewer="coord"),
            "reviewer unknown": dict(reviewer="nobody"),
            "submitter is hub": dict(session="hub"),
            "fifth node": dict(nodes=("spec", "risk")),
            "no nodes": dict(nodes=()),
            "empty approval": dict(approval_note="  "),
        }
        for label, kw in cases.items():
            with self.subTest(label):
                with self.assertRaises(reviews.InvalidRegistration):
                    self.register(**kw)
        self.assertEqual((self.g.path / "events.jsonl").read_bytes(), before)
        self.assertFalse((self.g.path / "state" / "reviews.json").exists())

    def test_coordinator_can_be_submitter(self):
        self.register(session="coord")
        self.assertIsNotNone(reviews.registration_at(self.g, "coord", at=T2))


if __name__ == "__main__":
    unittest.main()
