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


WAIT_USER = """【等待用户】
结束：无
来自：前端
要你决定：支付页先接哪种支付方式
{review}要点：负责人说审查过一遍了，问题不大。
选项与我的建议：
推荐 A：先接微信支付
B：先接支付宝
是否完全停住：是
"""


def wait_user(review_line=None):
    return protocol.parse(WAIT_USER.format(review=(review_line + "\n") if review_line else ""))


class LabelTest(ReviewsCase):
    def label(self, review_line, at=T2, session="fe-codex"):
        return reviews.display_label(self.g, session=session, message=wait_user(review_line), received_at=at)

    def test_five_forms_verbatim(self):
        self.register()
        cases = {
            "架构审查：通过": "已审：通过",
            "架构审查：通过，附建议2条（命名、日志）": "已审：通过，附建议2条",
            "架构审查：进行中，请勿先批": "审查中，请勿先批",
            "架构审查：不适用（不属于审查节点）": "不需审：不属于审查节点",
            "架构审查：用户豁免": "用户豁免",
        }
        for line, text in cases.items():
            with self.subTest(line=line):
                label = self.label(line)
                self.assertEqual(label.text, text)
                self.assertFalse(label.warn)
                self.assertEqual(label.highlight, text == "审查中，请勿先批")

    def test_ref_is_kept(self):
        self.register()
        self.assertEqual(self.label("架构审查：通过（R-3）").ref, "R-3")

    def test_missing_or_unrecognized(self):
        self.register()
        for line in (None, "架构审查：已看过", "架构审查：—"):
            with self.subTest(line=line):
                label = self.label(line)
                self.assertEqual(label.text, "⚠ 未标审查")
                self.assertTrue(label.warn)
                self.assertIn("负责人说审查过一遍了，问题不大。", label.mentions)
        self.assertIn("已看过", self.label("架构审查：已看过").mentions)

    def test_unregistered_session_ignores_line(self):
        for line in (None, "架构审查：通过", "架构审查：进行中，请勿先批"):
            with self.subTest(line=line):
                label = self.label(line)
                self.assertEqual(label.text, "不需审：本会话无审查者")
                self.assertFalse(label.warn or label.highlight)

    def test_registration_time_decides(self):
        self.register(at=T1)
        self.assertEqual(self.label("架构审查：通过", at=T0).text, "不需审：本会话无审查者")
        self.assertEqual(self.label(None, at=T2).text, "⚠ 未标审查")
        reviews.unregister(self.g, session="fe-codex", approval_item=15, approval_note="用户原话：15 A", at=T3)
        self.assertEqual(self.label(None, at=T2).text, "⚠ 未标审查")
        self.assertEqual(self.label(None, at="2026-10-16T14:00:00+08:00").text, "不需审：本会话无审查者")


def conclusion(verdict="有须修改项", ref="R-3", node="Spec", submitter="前端", module=None):
    extra = f"模块：{module}\n" if module else ""
    return protocol.parse(f"【审查结论】\n审查编号：{ref}\n节点：{node}\n{extra}送审方：{submitter}\n结论：{verdict}\n")


class RoundsTest(ReviewsCase):
    def setUp(self):
        super().setUp()
        self.register(nodes=("spec", "plan"))

    def record(self, msg, sender="fe-owner", at=T2):
        return reviews.record_conclusion(self.g, message=msg, sender=sender, at=at)

    def test_three_rounds_then_pass(self):
        for verdict in ("有须修改项", "有须修改项", "通过"):
            result = self.record(conclusion(verdict))
            self.assertTrue(result.recorded)
            self.assertEqual(result.problems, ())
        stats = reviews.round_stats(self.g)
        self.assertEqual(stats.closed, (("R-3", "fe-codex", "spec", 3),))
        self.assertEqual(stats.open, ())

    def test_open_review(self):
        self.record(conclusion("有须修改项", ref="R-4", node="Plan"))
        self.assertEqual(reviews.round_stats(self.g).open, (("R-4", "fe-codex", "plan", 1),))

    def test_rejected_conclusions_do_not_count(self):
        cases = {
            "not-registered-reviewer": dict(msg=conclusion(), sender="coord"),
            "node-not-registered": dict(msg=conclusion(node="最终验收")),
            "bad-conclusion": dict(msg=conclusion(verdict="差不多")),
        }
        for code, kw in cases.items():
            with self.subTest(code):
                result = self.record(**kw)
                self.assertFalse(result.recorded)
                self.assertIn(code, {i.code for i in result.problems})
        self.assertIn("bad-conclusion", {i.code for i in self.record(conclusion(submitter="后台")).problems})
        self.assertIn("bad-conclusion", {i.code for i in self.record(protocol.parse("【已恢复】\n结束：#1\n")).problems})
        stats = reviews.round_stats(self.g)
        self.assertEqual((stats.closed, stats.open), ((), ()))

    def test_before_registration_is_not_registered(self):
        result = self.record(conclusion(), at=T0)
        self.assertIn("not-registered-reviewer", {i.code for i in result.problems})

    def test_reopen_after_pass(self):
        self.record(conclusion("通过"))
        result = self.record(conclusion("有须修改项"), at=T3)
        self.assertTrue(result.recorded)
        self.assertIn("reopened", {i.code for i in result.hints})
        stats = reviews.round_stats(self.g)
        self.assertEqual((stats.closed, stats.open), ((), (("R-3", "fe-codex", "spec", 2),)))

    def test_module_reviews(self):
        self.record(conclusion("有须修改项", ref="R-3", module="pay"))
        self.record(conclusion("有须修改项", ref="R-3"), at=T3)          # later round without 模块 keeps pay
        self.record(conclusion("通过，附建议2条", ref="R-4", node="Plan", module="pay"))
        self.record(conclusion("通过", ref="R-5", module="cart"))
        self.record(conclusion("通过", ref="R-1", module="cart"))
        self.record(conclusion("有须修改项", ref="R-7"))
        cells, unmarked = reviews.module_reviews(self.g, session="fe-codex")
        self.assertEqual(unmarked, ("R-7",))
        self.assertEqual(cells["pay"], (
            reviews.ModuleReview("R-3", "spec", "changes-required", None, 2, False),
            reviews.ModuleReview("R-4", "plan", "passed-with-advice", 2, 1, True),
        ))
        self.assertEqual([c.ref for c in cells["cart"]], ["R-1", "R-5"])
        self.assertEqual(reviews.module_reviews(self.g, session="api-codex"), ({}, ()))

    def test_module_moves_with_latest_marked_round(self):
        self.record(conclusion(ref="R-3", module="pay"))
        self.record(conclusion(ref="R-3", module="cart"), at=T3)
        cells, _ = reviews.module_reviews(self.g, session="fe-codex")
        self.assertEqual(list(cells), ["cart"])

    def test_old_record_without_module(self):
        self.record(conclusion(ref="R-3"))
        with self.g.transaction() as tx:
            doc = tx.read_state("reviews")
            doc["reviews"]["R-3"].pop("module", None)
            tx.write_state("reviews", doc)
        self.assertEqual(reviews.module_reviews(self.g, session="fe-codex"), ({}, ("R-3",)))

    def test_snapshot_and_log_consistent(self):
        self.record(conclusion("有须修改项"))
        self.record(conclusion("通过，附建议1条"))
        report = store.check(self.g)
        self.assertEqual(report["problems"], [])
        types = [e["type"] for e in store.read_events(self.g)]
        self.assertEqual(types.count("reviews.conclusion"), 2)


if __name__ == "__main__":
    unittest.main()
