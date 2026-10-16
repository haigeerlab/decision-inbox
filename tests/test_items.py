import unittest
from pathlib import Path

from helpers import TempHomeTestCase

from decision_inbox import items, protocol, reviews, store

PROTO = Path(__file__).resolve().parent / "fixtures" / "protocol"
T1 = "2026-10-16T11:00:00+08:00"
T2 = "2026-10-16T12:00:00+08:00"
T3 = "2026-10-16T13:00:00+08:00"


def fixture(name):
    return (PROTO / name).read_text(encoding="utf-8")


SINGLE = fixture("wait-user.txt")              # options A/B/C, recommend A, fully stopped
MULTI = fixture("wait-user-multiline.txt")     # 适用会话：前端、API


def codes(issues):
    return {i.code for i in issues}


class ItemsCase(TempHomeTestCase):
    def setUp(self):
        super().setUp()
        self.g, _ = store.init_group("demo")
        people = [
            ("hub", "收件枢纽", "hub", [], "claude-desktop", None),
            ("fe-codex", "前端", "dev", ["前端"], "codex-desktop", "/tmp/fe"),
            ("api-codex", "API", "dev", ["API"], "codex-desktop", "/tmp/api"),
            ("fe-owner", "前端负责人", "owner", ["前端"], "claude-desktop", None),
            ("coord", "总协调", "coordinator", [], "codex-desktop", None),
        ]
        with self.g.transaction() as tx:
            for relay, short, role, line, host, repo in people:
                entry = {"relayName": relay, "shortName": short, "role": role, "line": line, "host": host}
                if repo:
                    entry["repo"] = repo
                tx.add_session(entry)

    def receive(self, text, sender="fe-codex", relay_id=100, at=T1):
        return items.receive(self.g, text, sender=sender, relay_id=relay_id, received_at=at)

    def item(self, no):
        return store.read_state(self.g, "items")["items"][str(no)]


class ReceiveTest(ItemsCase):
    def test_accept(self):
        with self.g.transaction() as tx:
            tx.allocate_number()  # number 1 used elsewhere: the sequence is shared
        r = self.receive(SINGLE)
        self.assertTrue(r.handled and r.accepted)
        self.assertEqual(r.item, 2)
        self.assertIsNone(r.return_text)
        it = self.item(2)
        self.assertEqual((it["sender"], it["status"], it["relayId"]), ("fe-codex", "pending", 100))
        self.assertEqual(it["text"], SINGLE)
        self.assertEqual(it["decide"], "支付页先接哪种支付方式")
        self.assertEqual([o["letter"] for o in it["options"]], ["A", "B", "C"])
        self.assertEqual(it["review"]["text"], "不需审：本会话无审查者")
        self.assertEqual(store.read_events(self.g, ref=2)[-1]["type"], "items.received")

    def test_review_label_frozen_at_receipt(self):
        reviews.register(self.g, session="fe-codex", reviewer="fe-owner", nodes=("spec",),
                         approval_item=None, approval_note="接入时用户确认", at=T2)
        early = self.receive(SINGLE, at=T1).item
        late = self.receive(SINGLE, at=T3).item
        self.assertEqual(self.item(early)["review"]["text"], "不需审：本会话无审查者")
        self.assertEqual(self.item(late)["review"]["text"], "⚠ 未标审查")
        self.assertTrue(self.item(late)["review"]["warn"])

    def test_return_does_not_take_a_number(self):
        r = self.receive(SINGLE.replace("要你决定：支付页先接哪种支付方式\n", ""))
        self.assertTrue(r.handled)
        self.assertFalse(r.accepted)
        self.assertIsNone(r.item)
        self.assertIn("missing-field:要你决定", codes(r.problems))
        self.assertIn("退回", r.return_text)
        self.assertIn("缺少「要你决定」", r.return_text)
        self.assertEqual(store.read_events(self.g)[-1]["type"], "items.returned")
        self.assertEqual(self.receive(SINGLE).item, 1)

    def test_multiline_scope_missing_is_returned(self):
        text = MULTI.replace("- API：改响应字段名并补兼容期旧字段，\n  兼容期两周\n", "")
        r = self.receive(text, sender="coord")
        self.assertFalse(r.accepted)
        self.assertIn("scope-missing:API", codes(r.problems))

    def test_unknown_session_in_scope(self):
        text = MULTI.replace("适用会话：前端、API", "适用会话：前端、API、后台").replace(
            "选项与我的建议：", "- 后台：只读\n选项与我的建议：")
        r = self.receive(text, sender="coord")
        self.assertFalse(r.accepted)
        self.assertIn("scope-session-unknown:后台", codes(r.problems))

    def test_dev_multiline_becomes_single(self):
        r = self.receive(MULTI, sender="fe-codex")
        self.assertTrue(r.accepted)
        self.assertIn("multiline-not-allowed", codes(r.hints))
        self.assertFalse(self.item(r.item)["multi"])

    def test_owner_multiline_accepted(self):
        r = self.receive(MULTI, sender="fe-owner")
        self.assertTrue(r.accepted)
        it = self.item(r.item)
        self.assertTrue(it["multi"])
        self.assertEqual(it["lines"], ["前端", "API"])

    def test_other_kinds_not_handled(self):
        r = self.receive(fixture("wait-session.txt"))
        self.assertFalse(r.handled)
        self.assertEqual(store.read_events(self.g), [])


class ValidityAndOrderTest(ItemsCase):
    def test_supersede_own_item(self):
        old = self.receive(SINGLE).item
        r = self.receive(SINGLE.replace("【等待用户】", f"【等待用户】【取代 #{old}】"), relay_id=101, at=T2)
        self.assertTrue(r.accepted)
        self.assertEqual(self.item(old)["status"], "superseded")
        self.assertEqual(self.item(r.item)["status"], "pending")
        self.assertIn("items.superseded", [e["type"] for e in store.read_events(self.g, ref=old)])

    def test_supersede_other_senders_item(self):
        old = self.receive(SINGLE, sender="api-codex").item
        r = self.receive(SINGLE.replace("【等待用户】", f"【等待用户】【取代 #{old}】"))
        self.assertFalse(r.accepted)
        self.assertIn("not-owner", codes(r.problems))
        self.assertEqual(self.item(old)["status"], "pending")

    def test_withdraw(self):
        old = self.receive(SINGLE).item
        r = self.receive(f"【撤回】\n事项：#{old}\n原因：需求取消\n", relay_id=102)
        self.assertTrue(r.handled and r.accepted)
        self.assertEqual(r.item, old)
        self.assertEqual(self.item(old)["status"], "withdrawn")
        other = self.receive(SINGLE, sender="api-codex").item
        r = self.receive(f"【撤回】\n事项：#{other}\n")
        self.assertFalse(r.accepted)
        self.assertIn("not-owner", codes(r.problems))
        self.assertIsNotNone(r.return_text)

    def test_pending_order(self):
        not_stopped = self.receive(SINGLE.replace("是否完全停住：是", "是否完全停住：否"), at=T1).item
        stopped_late = self.receive(SINGLE, at=T3).item
        stopped_early = self.receive(SINGLE, sender="api-codex", at=T2).item
        multi = self.receive(MULTI.replace("适用会话：前端、API", "适用会话：前端、API、前端负责人").replace(
            "选项与我的建议：", "- 前端负责人：只看\n选项与我的建议："), sender="coord", at=T3).item
        order = [(p["no"], p["blocks"]) for p in items.pending(self.g)]
        self.assertEqual(order, [(multi, 3), (stopped_early, 1), (stopped_late, 1), (not_stopped, 0)])

    def test_pending_excludes_invalidated(self):
        old = self.receive(SINGLE).item
        self.receive(f"【撤回】\n事项：#{old}\n")
        self.assertEqual(items.pending(self.g), [])


class InterpretTest(ItemsCase):
    def setUp(self):
        super().setUp()
        self.a = self.receive(SINGLE).item                         # options A/B/C
        self.b = self.receive(SINGLE, sender="api-codex", at=T2).item

    def parse(self, text):
        return items.interpret_reply(self.g, text)

    def test_letter_reply(self):
        p = self.parse(f"{self.a} B")
        self.assertIsNone(p.question)
        self.assertEqual(p.answers, (items.Answer(self.a, "B", f"{self.a} B"),))

    def test_copy_block_and_free_sentence(self):
        copy = f"{self.a} A 先接微信支付"
        self.assertEqual(self.parse(copy).answers, (items.Answer(self.a, "A", copy),))
        free = f"{self.a} 按推荐来，支付宝下周再说"
        self.assertEqual(self.parse(free).answers, (items.Answer(self.a, None, free),))

    def test_several_items(self):
        for text in (f"{self.a} B\n{self.b} A", f"{self.a} B，{self.b} A", f"{self.a} B；{self.b} A"):
            with self.subTest(text=text):
                p = self.parse(text)
                self.assertIsNone(p.question)
                self.assertEqual([(x.item, x.letter) for x in p.answers], [(self.a, "B"), (self.b, "A")])

    def test_questions_instead_of_answers(self):
        withdrawn = self.receive(SINGLE, sender="fe-codex", at=T3).item
        self.receive(f"【撤回】\n事项：#{withdrawn}\n")
        for text in ("99 A", f"{withdrawn} A", f"{self.a} D", f"{self.a} A，{self.a} B", "按推荐来"):
            with self.subTest(text=text):
                p = self.parse(text)
                self.assertEqual(p.answers, ())
                self.assertTrue(p.question)

    def test_no_number_with_single_pending(self):
        self.receive(f"【撤回】\n事项：#{self.b}\n", sender="api-codex")
        p = self.parse("按推荐来")
        self.assertEqual(p.answers, (items.Answer(self.a, None, "按推荐来"),))

    def test_same_answer_twice_in_one_reply_is_one(self):
        p = self.parse(f"{self.a} B，{self.a} B")
        self.assertEqual([(x.item, x.letter) for x in p.answers], [(self.a, "B")])


class AnswerTest(ItemsCase):
    def test_single_answer_with_option_text(self):
        no = self.receive(SINGLE).item
        out = items.answer(self.g, items.interpret_reply(self.g, f"{no} B").answers, answered_at=T2)
        self.assertEqual(len(out), 1)
        self.assertEqual((out[0].to, out[0].item), ("fe-codex", no))
        parsed = protocol.parse(out[0].text)
        self.assertEqual(parsed.kind, "user-reply")
        self.assertEqual(parsed.fields["用户原话"], f"{no} B")
        self.assertEqual(parsed.fields["选项原文"], "B：先接支付宝")
        self.assertEqual(self.item(no)["status"], "forwarded")
        self.assertEqual(store.read_events(self.g, ref=no)[-1]["type"], "items.answered")

    def test_free_sentence_forwarded_verbatim(self):
        no = self.receive(SINGLE).item
        text = f"{no} 按推荐来，支付宝下周再说"
        out = items.answer(self.g, items.interpret_reply(self.g, text).answers, answered_at=T2)
        parsed = protocol.parse(out[0].text)
        self.assertEqual(parsed.fields["用户原话"], text)
        self.assertNotIn("选项原文", parsed.fields)

    def test_multiline_fan_out(self):
        no = self.receive(MULTI, sender="coord").item
        out = items.answer(self.g, items.interpret_reply(self.g, f"{no} A").answers, answered_at=T2)
        self.assertEqual(sorted(o.to for o in out), ["api-codex", "coord", "fe-codex"])
        source = protocol.parse(MULTI)
        for o in out:
            parsed = protocol.parse(o.text)
            self.assertTrue(parsed.ok, parsed.problems)
            if o.to == "fe-codex":
                self.assertEqual(parsed.fields["适用于你的范围"], source.scopes["前端"])
            if o.to == "api-codex":
                self.assertEqual(parsed.fields["适用于你的范围"], source.scopes["API"])
        self.assertEqual(sorted(self.item(no)["recipients"]), ["api-codex", "coord", "fe-codex"])

    def test_in_review_is_still_forwarded(self):
        reviews.register(self.g, session="fe-codex", reviewer="fe-owner", nodes=("spec",),
                         approval_item=None, approval_note="接入时用户确认", at=T1)
        text = SINGLE.replace("要点：", "架构审查：进行中，请勿先批\n要点：")
        no = self.receive(text, at=T2).item
        self.assertTrue(self.item(no)["review"]["highlight"])
        out = items.answer(self.g, items.interpret_reply(self.g, f"{no} B").answers, answered_at=T3)
        self.assertEqual(protocol.parse(out[0].text).fields["用户原话"], f"{no} B")

    def test_changed_answer_after_forwarding_is_a_question(self):
        no = self.receive(SINGLE).item
        items.answer(self.g, items.interpret_reply(self.g, f"{no} A").answers, answered_at=T2)
        p = items.interpret_reply(self.g, f"{no} B")
        self.assertEqual(p.answers, ())
        self.assertTrue(p.question)

    def test_answer_rejects_non_pending(self):
        no = self.receive(SINGLE).item
        answers = items.interpret_reply(self.g, f"{no} A").answers
        items.answer(self.g, answers, answered_at=T2)
        with self.assertRaises(ValueError):
            items.answer(self.g, answers, answered_at=T3)


class LifecycleTest(ItemsCase):
    def answered(self, text=SINGLE, sender="fe-codex"):
        no = self.receive(text, sender=sender).item
        out = items.answer(self.g, items.interpret_reply(self.g, f"{no} A").answers, answered_at=T2)
        for i, o in enumerate(out):
            items.record_sent(self.g, item=no, to=o.to, relay_id=500 + i, at=T2)
        return no, out

    def test_single_recipient_progress(self):
        no, _ = self.answered()
        self.assertEqual(self.item(no)["sent"][0]["relayId"], 500)
        items.update_delivery(self.g, {500: ("accepted", None)}, at=T3)
        self.assertEqual(self.item(no)["status"], "picked")
        items.update_delivery(self.g, {500: ("accepted", "2026-10-16T05:10:00Z")}, at=T3)
        self.assertEqual(self.item(no)["status"], "acknowledged")
        items.update_delivery(self.g, {500: ("queued", None)}, at=T3)
        self.assertEqual(self.item(no)["status"], "acknowledged")  # never moves back

    def test_multi_recipient_waits_for_slowest(self):
        no, out = self.answered(MULTI, sender="coord")
        self.assertEqual(len(out), 3)
        items.update_delivery(self.g, {500: ("accepted", "t"), 501: ("accepted", "t")}, at=T3)
        self.assertEqual(self.item(no)["status"], "forwarded")
        items.update_delivery(self.g, {502: ("accepted", None)}, at=T3)
        self.assertEqual(self.item(no)["status"], "picked")
        items.update_delivery(self.g, {502: ("accepted", "t")}, at=T3)
        self.assertEqual(self.item(no)["status"], "acknowledged")

    def test_resumed_closes_only_own_answered_item(self):
        no, _ = self.answered()
        waiting = self.receive(SINGLE, relay_id=200).item
        other = protocol.parse(f"【已恢复】\n结束：#{no}\n")
        items.on_resumed(self.g, other, sender="api-codex", at=T3)
        self.assertEqual(self.item(no)["status"], "forwarded")
        mine = protocol.parse(f"【已恢复】\n结束：#{no}、#{waiting}\n")
        items.on_resumed(self.g, mine, sender="fe-codex", at=T3)
        self.assertEqual(self.item(no)["status"], "closed")
        self.assertEqual(self.item(waiting)["status"], "pending")  # not answered yet: untouched

    def test_invalidated_items_do_not_move(self):
        no = self.receive(SINGLE).item
        self.receive(f"【撤回】\n事项：#{no}\n")
        items.update_delivery(self.g, {999: ("accepted", "t")}, at=T3)
        items.on_resumed(self.g, protocol.parse(f"【已恢复】\n结束：#{no}\n"), sender="fe-codex", at=T3)
        self.assertEqual(self.item(no)["status"], "withdrawn")

    def test_history_and_consistency(self):
        no, _ = self.answered()
        items.update_delivery(self.g, {500: ("accepted", "t")}, at=T3)
        items.on_resumed(self.g, protocol.parse(f"【已恢复】\n结束：#{no}\n"), sender="fe-codex", at=T3)
        types = [e["type"] for e in items.history(self.g, item=no)]
        self.assertEqual(types, ["items.received", "items.answered", "items.sent", "items.delivery", "items.closed"])
        sent = [e for e in items.history(self.g, item=no) if e["type"] == "items.sent"][0]
        self.assertEqual(sent["data"]["relayId"], 500)
        self.assertEqual(store.check(self.g)["problems"], [])


if __name__ == "__main__":
    unittest.main()
