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
        self.assertEqual(self.item(early)["review"]["mentions"], [])

    def test_review_mentions_stored(self):
        reviews.register(self.g, session="fe-codex", reviewer="fe-owner", nodes=("spec",),
                         approval_item=None, approval_note="接入时用户确认", at=T1)
        text = SINGLE.replace("要点：", "要点：架构师说审查还没做完。")
        no = self.receive(text, at=T2).item
        label = reviews.display_label(self.g, session="fe-codex", message=protocol.parse(text), received_at=T2)
        self.assertTrue(label.mentions)
        self.assertEqual(self.item(no)["review"]["mentions"], list(label.mentions))

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

    def test_supersede_by_mail_id_names_the_item(self):
        """p0-field-fixes F-P0-1: a mail id in 【取代】 is still returned, but the text says which item it is."""
        old = self.receive(SINGLE, relay_id=5538).item
        r = self.receive(SINGLE.replace("【等待用户】", "【等待用户】【取代 #5538】"), relay_id=5539, at=T2)
        self.assertFalse(r.accepted)
        self.assertEqual(codes(r.problems), {"not-owner"})
        self.assertIn(f"#5538 是邮箱号，对应待决事项 #{old}；去掉【取代】靠默认取代，或改写【取代 #{old}】", r.return_text)
        self.assertEqual(self.item(old)["status"], "pending")

    def test_other_senders_mail_id_gets_the_plain_text(self):
        self.receive(SINGLE, sender="api-codex", relay_id=5538)
        r = self.receive(SINGLE.replace("【等待用户】", "【等待用户】【取代 #5538】"), relay_id=5539, at=T2)
        self.assertIn("#5538 不存在，或不是你抛出的待决事项", r.return_text)
        self.assertNotIn("邮箱号", r.return_text)

    def test_withdraw_by_mail_id_names_the_item(self):
        """rehearsal-fixes: a mail id in 【撤回】 is still returned, but the text says which item to write."""
        old = self.receive(SINGLE, relay_id=5538).item
        r = self.receive("【撤回】\n事项：#5538\n原因：需求取消\n", relay_id=5539, at=T2)
        self.assertFalse(r.accepted)
        self.assertEqual(codes(r.problems), {"not-owner"})
        self.assertIn(f"#5538 是邮箱号，对应待决事项 #{old}；改写「事项：#{old}」重发【撤回】", r.return_text)
        self.assertNotIn("【取代", r.return_text)
        self.assertEqual(self.item(old)["status"], "pending")
        r = self.receive("【撤回】\n事项：#9999\n", relay_id=5540, at=T2)
        self.assertIn("#9999 不存在，或不是你抛出的待决事项", r.return_text)

    def test_new_item_supersedes_own_pending_by_default(self):
        """wait-honesty-and-briefs A7: no marker means the new item replaces this session's unanswered one."""
        old = self.receive(SINGLE).item
        other = self.receive(SINGLE, sender="api-codex", relay_id=101).item
        r = self.receive(SINGLE, relay_id=102, at=T2)
        self.assertTrue(r.accepted)
        self.assertEqual(self.item(old)["status"], "superseded")
        self.assertEqual(self.item(other)["status"], "pending")
        event = [e for e in store.read_events(self.g, ref=old) if e["type"] == "items.superseded"][-1]
        self.assertEqual(event["data"], {"by": r.item, "auto": True})
        hint = next(h for h in r.hints if h.code == "auto-superseded")
        self.assertEqual(hint.text, f"#{old} 已被新的待决事项自动取代；确实要两项都答，请写【与 #{old} 并行】重发")

    def test_parallel_marker_keeps_the_old_item(self):
        old = self.receive(SINGLE).item
        r = self.receive(SINGLE.replace("【等待用户】", f"【等待用户】【与 #{old} 并行】"), relay_id=101, at=T2)
        self.assertEqual(self.item(old)["status"], "pending")
        self.assertNotIn("auto-superseded", {h.code for h in r.hints})

    def test_single_and_multi_line_items_do_not_replace_each_other(self):
        multi = self.receive(MULTI, sender="coord").item
        single = self.receive(SINGLE, sender="coord", relay_id=101, at=T2).item
        self.assertEqual(self.item(multi)["status"], "pending")
        self.assertEqual(self.item(single)["status"], "pending")

    def test_answered_items_are_not_superseded(self):
        old = self.receive(SINGLE).item
        items.answer(self.g, items.interpret_reply(self.g, f"{old} A").answers, answered_at=T2)
        self.receive(SINGLE, relay_id=101, at=T2)
        self.assertEqual(self.item(old)["status"], "forwarded")

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
        stopped_late = self.receive(SINGLE.replace("【等待用户】", f"【等待用户】【与 #{not_stopped} 并行】"), at=T3).item
        stopped_early = self.receive(SINGLE, sender="api-codex", at=T2).item
        multi = self.receive(MULTI.replace("适用会话：前端、API", "适用会话：前端、API、前端负责人").replace(
            "选项与我的建议：", "- 前端负责人：只看\n选项与我的建议："), sender="coord", at=T3).item
        order = [(p["no"], p["blocks"]) for p in items.pending(self.g)]
        self.assertEqual(order, [(multi, 3), (stopped_early, 1), (stopped_late, 1), (not_stopped, 0)])

    def test_get_and_by_status(self):
        old = self.receive(SINGLE).item
        new = self.receive(SINGLE.replace("【等待用户】", f"【等待用户】【取代 #{old}】"), relay_id=101, at=T2).item
        gone = self.receive(SINGLE, sender="api-codex", relay_id=102).item
        self.receive(f"【撤回】\n事项：#{gone}\n原因：需求取消\n", sender="api-codex", relay_id=103)
        got = items.get(self.g, new)
        self.assertEqual((got["no"], got["status"], got["relayId"]), (new, "pending", 101))
        self.assertIsNone(items.get(self.g, 999))
        self.assertEqual([it["no"] for it in items.by_status(self.g, "superseded", "withdrawn")], [old, gone])
        self.assertEqual([it["no"] for it in items.by_status(self.g, "pending")], [new])
        self.assertEqual(items.by_status(self.g, "closed"), [])

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
        free = f"{self.a} 原话：按推荐来，支付宝下周再说"
        self.assertEqual(self.parse(free).answers, (items.Answer(self.a, None, free),))

    def test_several_items(self):
        for text in (f"{self.a} B\n{self.b} A", f"{self.a} B，{self.b} A", f"{self.a} B；{self.b} A"):
            with self.subTest(text=text):
                p = self.parse(text)
                self.assertIsNone(p.question)
                self.assertEqual([(x.item, x.letter) for x in p.answers], [(self.a, "B"), (self.b, "A")])

    def test_questions_instead_of_answers(self):
        withdrawn = self.receive(SINGLE.replace("【等待用户】", f"【等待用户】【与 #{self.a} 并行】"),
                                 sender="fe-codex", at=T3).item
        self.receive(f"【撤回】\n事项：#{withdrawn}\n")
        for text in ("99 A", f"{withdrawn} A", f"{self.a} D", f"{self.a} A，{self.a} B", "按推荐来"):
            with self.subTest(text=text):
                p = self.parse(text)
                self.assertEqual(p.answers, ())
                self.assertTrue(p.question)

    def test_no_number_with_single_pending(self):
        """stage-c3-fixes I-20: with one item pending, only a letter or 「原话：」 answers it without a number."""
        self.receive(f"【撤回】\n事项：#{self.b}\n", sender="api-codex")
        p = self.parse("按推荐来")
        self.assertEqual(p.answers, ())
        self.assertEqual(p.question, items.NO_ITEM_QUESTION)
        self.assertEqual(self.parse("B").answers, (items.Answer(self.a, "B", "B"),))
        self.assertEqual(self.parse("B。").answers, (items.Answer(self.a, "B", "B。"),))
        self.assertEqual(self.parse("原话：按推荐来").answers, (items.Answer(self.a, None, "原话：按推荐来"),))
        self.assertEqual(self.parse("Z").question, f"#{self.a} 没有选项 Z，请确认。")

    def test_no_number_item_without_options_takes_the_sentence(self):
        no_options = SINGLE.split("选项与我的建议：")[0] + "选项与我的建议：\n推荐 A：照做\n是否完全停住：是\n"
        self.receive(f"【撤回】\n事项：#{self.b}\n", sender="api-codex")
        self.receive(f"【撤回】\n事项：#{self.a}\n", sender="fe-codex")
        no = self.receive(no_options, sender="coord", at=T3).item
        with self.g.transaction() as tx:  # an item whose options were never recorded (old data)
            doc = tx.read_state("items")
            doc["items"][str(no)]["options"] = []
            tx.write_state("items", doc)
        self.assertEqual(self.parse("按推荐来").answers, (items.Answer(no, None, "按推荐来"),))

    def test_same_answer_twice_in_one_reply_is_one(self):
        p = self.parse(f"{self.a} B，{self.a} B")
        self.assertEqual([(x.item, x.letter) for x in p.answers], [(self.a, "B")])


class TolerantReplyTest(InterpretTest):
    """decision-cards DI-7 (I-4): trailing punctuation is tolerated; anything else unclear is asked, never guessed."""

    def test_trailing_punctuation_after_the_letter(self):
        for tail in ("」", "。", "）", ")", "”", "！", "?", "』", "\"", "。」"):
            with self.subTest(tail=tail):
                text = f"{self.a} A{tail}"
                self.assertEqual(self.parse(text).answers, (items.Answer(self.a, "A", text),))

    def test_option_text_goes_out_for_a_punctuated_letter(self):
        out = items.answer(self.g, self.parse(f"{self.a} A」").answers, answered_at=T2)
        self.assertIn("选项 A 原文：", out[0].text)
        self.assertIn(f"用户原话：{self.a} A」", out[0].text)

    def test_no_letter_is_asked_not_forwarded(self):
        p = self.parse(f"{self.a} 好的")
        self.assertEqual(p.answers, ())
        self.assertIn(f"没认出 #{self.a} 选的是哪个选项（A／B／C）", p.question)
        self.assertIn(f"「{self.a} A」", p.question)
        self.assertIn(f"「{self.a} 原话：", p.question)
        self.assertEqual(self.item(self.a)["status"], "pending")

    def test_original_words_without_an_option(self):
        text = f"{self.a} 原话：好的，先这样"
        p = self.parse(text)
        self.assertEqual(p.answers, (items.Answer(self.a, None, text),))
        out = items.answer(self.g, p.answers, answered_at=T2)
        self.assertIn(f"用户原话：{text}", out[0].text)
        self.assertNotIn("原文：", out[0].text.replace("用户原话", ""))


class PrefixTest(InterpretTest):
    """review-nearby Task 6 (R6): only an unprefixed number is an item; C15, R-3, D1 stay in the user's words."""

    def test_letter_followed_by_punctuation(self):
        for text in (f"{self.a} B，C15 退回", f"{self.a} B；C15 退回", f"{self.a} B、C16 也退回"):
            with self.subTest(text=text):
                p = self.parse(text)
                self.assertIsNone(p.question)
                self.assertEqual(p.answers, (items.Answer(self.a, "B", text),))

    def test_prefixed_pieces_join_the_item_before_them(self):
        for text in (f"{self.a} B，C15 退回，{self.b} A", f"{self.a} B\nC15 退回\n{self.b} A"):
            with self.subTest(text=text):
                p = self.parse(text)
                self.assertIsNone(p.question)
                self.assertEqual([(x.item, x.letter) for x in p.answers], [(self.a, "B"), (self.b, "A")])
                self.assertIn("C15 退回", p.answers[0].original)

    def test_prefixed_number_is_never_an_item(self):
        for text in (f"C{self.a} A", f"#C{self.a} A", f"R-{self.a} A", f"D{self.a} A", f"4c5d6e{self.a} A"):
            with self.subTest(text=text):
                self.assertEqual(self.parse(text).question, items.NO_ITEM_QUESTION)

    def test_old_forms_unchanged(self):
        self.assertEqual([(x.item, x.letter) for x in self.parse(f"{self.a} B").answers], [(self.a, "B")])
        self.assertEqual([(x.item, x.letter) for x in self.parse(f"#{self.a} B").answers], [(self.a, "B")])
        self.assertEqual([(x.item, x.letter) for x in self.parse(f"{self.a} B，{self.b} A").answers],
                         [(self.a, "B"), (self.b, "A")])
        self.receive(f"【撤回】\n事项：#{self.b}\n", sender="api-codex")
        self.assertEqual(self.parse("A").answers, (items.Answer(self.a, "A", "A"),))  # stage-c3-fixes I-20: letter now read


CONTRACT = Path(__file__).resolve().parent / "fixtures" / "session-protocol" / f"v{protocol.CONTRACT_VERSION}"
DECISIONS = (CONTRACT / "wait-user" / "decisions.txt").read_text(encoding="utf-8")  # A/B, D1 and D2 (A/B)


class DecisionReplyTest(ItemsCase):
    """review-nearby Task 7 (R2): every 「待用户决定」 must be answered; nothing half-answered goes out."""

    def setUp(self):
        super().setUp()
        self.no = self.receive(DECISIONS, sender="coord").item
        self.other = self.receive(SINGLE, at=T2).item

    def parse(self, text):
        return items.interpret_reply(self.g, text)

    def test_recorded(self):
        ds = self.item(self.no)["decisions"]
        self.assertEqual([(d["id"], d["lean"], [o[0] for o in d["options"]]) for d in ds],
                         [("D1", "B", ["A", "B"]), ("D2", "A", ["A", "B"])])

    def test_full_answers_pass(self):
        n = self.no
        for text in (f"{n} A；D1 B；D2 A", f"{n} A\nD1 B\nD2 A", f"{n} A；D1 选 B，D2：A"):
            with self.subTest(text=text):
                p = self.parse(text)
                self.assertIsNone(p.question)
                self.assertEqual(p.answers, (items.Answer(n, "A", text, (("D1", "B"), ("D2", "A"))),))

    def test_missing_or_wrong_asks_again(self):
        n = self.no
        cases = {f"{n} A": ("D1", "D2"), f"{n} A；D1 B": ("D2",), f"{n} A；D1 Z；D2 A": ("D1",),
                 f"{n} A；D1 B；D1 A；D2 A": ("D1",), f"{n} A；D1 B；D2 A；D3 A": ("D3",),
                 f"{n} D1 B；D2 A": ("主选项",)}
        for text, named in cases.items():
            with self.subTest(text=text):
                p = self.parse(text)
                self.assertEqual(p.answers, ())
                for word in named:
                    self.assertIn(word, p.question)
                self.assertIn(f"例如「{n} A；D1 B；D2 A」", p.question)

    def test_question_names_what_is_missing(self):
        q = self.parse(f"{self.no} A；D1 B").question
        self.assertIn("D2 错误日志保留多久？（A. 7 天／B. 30 天）", q)
        self.assertNotIn("D1 alpha", q)

    def test_other_items_unchanged(self):
        p = self.parse(f"{self.other} B；D1 A")
        self.assertIsNone(p.question)
        self.assertEqual(p.answers, (items.Answer(self.other, "B", f"{self.other} B；D1 A"),))

    def test_forwarded_whole_and_recorded(self):
        text = f"{self.no} A；D1 B；D2 A"
        out = items.answer(self.g, self.parse(text).answers, answered_at=T3)
        self.assertIn(f"用户原话：{text}", out[0].text)
        self.assertEqual(self.item(self.no)["answers"][0]["decisions"], [["D1", "B"], ["D2", "A"]])


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

    def test_reply_names_the_proposers_message(self):
        no = self.receive(SINGLE, relay_id=4540).item
        out = items.answer(self.g, items.interpret_reply(self.g, f"{no} A").answers, answered_at=T2)
        self.assertIn(f"事项：#{no}（你的原消息 #4540）", out[0].text)

    def test_free_sentence_forwarded_verbatim(self):
        no = self.receive(SINGLE).item
        text = f"{no} 原话：按推荐来，支付宝下周再说"
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
        items.record_sent(self.g, no, to="fe-codex", relay_id=3901, at=T2)  # stage-c3-fixes: it went out
        p = items.interpret_reply(self.g, f"{no} B")
        self.assertEqual(p.answers, ())
        self.assertTrue(p.question)

    def test_answer_rejects_non_pending(self):
        no = self.receive(SINGLE).item
        answers = items.interpret_reply(self.g, f"{no} A").answers
        items.answer(self.g, answers, answered_at=T2)
        items.record_sent(self.g, no, to="fe-codex", relay_id=3901, at=T2)  # stage-c3-fixes: it went out
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

    def test_resumed_with_own_relay_id(self):
        """e2e-round1-fixes F10: the proposer may end with its own message id."""
        no, _ = self.answered()
        relay_id = self.item(no)["relayId"]
        items.on_resumed(self.g, protocol.parse(f"【已恢复】\n结束：#{relay_id}\n"), sender="api-codex", at=T3)
        self.assertEqual(self.item(no)["status"], "forwarded")
        closed = items.on_resumed(self.g, protocol.parse(f"【已恢复】\n结束：#{relay_id}\n"), sender="fe-codex", at=T3)
        self.assertEqual((closed, self.item(no)["status"]), ((no,), "closed"))

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


class LegacyFormatTest(ItemsCase):
    """transition-compat: lines not migrated yet get the old numbering; left sessions get nothing."""

    def mark(self, relay, **fields):
        with self.g.transaction() as tx:
            entry = dict(store.find_session(self.g, relay_name=relay), **fields)
            if fields.get("legacyFormat"):
                entry.pop("repo", None)
            tx.replace_session(entry)

    def leave(self, relay):
        with self.g.transaction() as tx:
            doc = tx.read_state("onboarding")
            doc.setdefault("left", {})[relay] = T1
            tx.write_state("onboarding", doc)

    def test_single_reply_uses_old_numbering(self):
        self.mark("fe-codex", legacyFormat=True)
        no = self.receive(SINGLE, relay_id=5990).item
        out = items.answer(self.g, items.interpret_reply(self.g, f"{no} A").answers, answered_at=T2)
        first = out[0].text.splitlines()[1]
        self.assertEqual(first, f"事项：#5990（hub 编号 {no}）")
        self.assertEqual(out[0].text.splitlines()[0], "【用户答复】")
        self.assertIn(f"用户原话：{no} A", out[0].text)

    def test_formal_line_unchanged(self):
        no = self.receive(SINGLE, relay_id=5990).item
        out = items.answer(self.g, items.interpret_reply(self.g, f"{no} A").answers, answered_at=T2)
        self.assertEqual(out[0].text.splitlines()[1], f"事项：#{no}（你的原消息 #5990）")

    def test_multiline_reply_uses_old_numbering_for_legacy_lines_only(self):
        self.mark("fe-codex", legacyFormat=True)
        no = self.receive(MULTI, sender="coord", relay_id=5948).item
        out = {o.to: o.text for o in items.answer(self.g, items.interpret_reply(self.g, f"{no} A").answers,
                                                  answered_at=T2)}
        self.assertEqual(out["fe-codex"].splitlines()[1], f"事项：#5948（多线事项，发起方 coord；hub 编号 {no}）")
        self.assertIn("适用于你的范围：", out["fe-codex"])
        self.assertTrue(out["api-codex"].splitlines()[1].startswith(f"事项：#{no}（"))

    def test_left_session_gets_no_multiline_reply(self):
        no = self.receive(MULTI, sender="coord").item
        self.leave("api-codex")
        out = items.answer(self.g, items.interpret_reply(self.g, f"{no} A").answers, answered_at=T2)
        self.assertEqual(sorted(o.to for o in out), ["coord", "fe-codex"])

    def test_multiline_naming_a_left_session_is_returned(self):
        self.leave("api-codex")
        r = self.receive(MULTI, sender="coord")
        self.assertFalse(r.accepted)
        self.assertIn("scope-session-unknown:API", codes(r.problems))

    def test_legacy_supersede_and_withdraw_by_own_mail_id(self):
        self.mark("fe-codex", legacyFormat=True)
        old = self.receive(SINGLE, relay_id=5990).item
        r = self.receive(SINGLE.replace("【等待用户】", "【等待用户】【取代 #5990】"), relay_id=6000, at=T2)
        self.assertTrue(r.accepted, r.problems)
        self.assertEqual(self.item(old)["status"], "superseded")
        r = self.receive("【撤回】\n事项：#6000\n原因：需求取消\n", relay_id=6001)
        self.assertTrue(r.accepted, r.problems)
        self.assertEqual(self.item(r.item)["status"], "withdrawn")

    def test_legacy_cannot_reach_someone_elses_item(self):
        self.mark("fe-codex", legacyFormat=True)
        self.receive(SINGLE, sender="api-codex", relay_id=7000)
        r = self.receive(SINGLE.replace("【等待用户】", "【等待用户】【取代 #7000】"), relay_id=7001)
        self.assertFalse(r.accepted)
        self.assertIn("not-owner", codes(r.problems))

    def test_formal_line_still_needs_the_item_number(self):
        self.receive(SINGLE, relay_id=5990)
        r = self.receive(SINGLE.replace("【等待用户】", "【等待用户】【取代 #5990】"), relay_id=6000, at=T2)
        self.assertFalse(r.accepted)
        self.assertIn("#5990 是邮箱号", r.return_text)

    def test_legacy_hint_names_both_numbers(self):
        self.mark("fe-codex", legacyFormat=True)
        old = self.receive(SINGLE, relay_id=5990).item
        r = self.receive(SINGLE, relay_id=6000, at=T2)
        hint = next(h.text for h in r.hints if h.code == "auto-superseded")
        self.assertTrue(hint.startswith(f"#5990（hub 编号 {old}） 已被新的待决事项自动取代"), hint)
        self.assertIn("【与 #5990 并行】", hint)


class WritingNotesTest(TempHomeTestCase):
    """rehearsal2-fixes Task 4 (user chose A): loose writing is noted for the user only, outside the contract."""

    FIX = Path(__file__).resolve().parent / "fixtures" / "protocol"
    CODES = ("missing-project", "reply-letter-only", "review-empty-advice", "brief-thin-batch")

    def notes(self, text):
        return [code for code, _ in items.writing_notes(protocol.parse(text))]

    def test_rehearsal_batch_sample(self):
        text = (self.FIX.parent / "rehearsal" / "wait-user-batch-thin.txt").read_text(encoding="utf-8")
        msg = protocol.parse(text)
        self.assertEqual(([p.code for p in msg.problems], [h.code for h in msg.hints]), ([], []))  # contract unchanged
        self.assertEqual(self.notes(text), list(self.CODES))

    def test_complete_sample_has_no_notes(self):
        self.assertEqual(self.notes((self.FIX / "wait-user.txt").read_text(encoding="utf-8")), [])

    def test_review_forms(self):
        base = (self.FIX / "wait-user.txt").read_text(encoding="utf-8").replace(
            "选项与我的建议：", "架构审查：{}\n选项与我的建议：")
        self.assertNotIn("review-empty-advice", self.notes(base.format("通过，附建议1条（金额字段改成分）")))
        self.assertNotIn("review-empty-advice", self.notes(base.format("通过，附建议1条（日志）（#41）")))
        self.assertIn("review-empty-advice", self.notes(base.format("通过，附建议2条（R-3）")))
        self.assertNotIn("review-empty-advice", self.notes(base.format("通过")))

    def test_reply_letter_forms(self):
        base = (self.FIX / "wait-user.txt").read_text(encoding="utf-8")
        for reply in ("A", " B ", "12 A"):
            with self.subTest(reply=reply):
                self.assertIn("reply-letter-only", self.notes(base.replace("你该回：12 A 先接微信支付", f"你该回：{reply}")))
        self.assertNotIn("reply-letter-only", self.notes(base.replace("你该回：12 A 先接微信支付", "你该回：A 先接微信支付")))

    def test_batch_brief_rich_enough(self):
        text = (self.FIX / "wait-user.txt").read_text(encoding="utf-8").replace(
            "要你决定：支付页先接哪种支付方式", "要你决定：批准 #4、#5 吗").replace(
            "要点：Mock 已就绪，两种方式工作量差一倍。", "要点：\n- #4 做什么\n- #4 不做什么\n- #5 步骤\n- #5 风险")
        self.assertNotIn("brief-thin-batch", self.notes(text))

    def test_notes_kept_on_item_not_on_card(self):
        from decision_inbox import view
        g, _ = store.init_group("demo")
        with g.transaction() as tx:
            tx.add_session({"relayName": "coord", "shortName": "并行协调", "role": "dev", "line": ["main"],
                            "host": "claude-desktop", "repo": "/tmp/coord"})
        text = (self.FIX.parent / "rehearsal" / "wait-user-batch-thin.txt").read_text(encoding="utf-8")
        r = items.receive(g, text, sender="coord", relay_id=6546, received_at="2026-10-18T19:40:01+08:00")
        self.assertTrue(r.accepted)
        self.assertEqual(r.return_text, None)
        it = next(x for x in items.pending(g))
        self.assertTrue(any("「你该回」只写了选项字母" in n for n in it["writingNotes"]))  # kept for the 回执
        card = view._item_card(g, "2026-10-18T19:45:00+08:00", it)
        # decision-cards D1 B: writing hints are the proposer's business, not the user's card
        self.assertNotIn("写法提示", card)


class ModuleFieldTest(ItemsCase):
    """stage-c-fixes DI-10: session-protocol v2.4 「模块」 is kept on the item; without it the item has no key."""

    def with_module(self, value):
        return SINGLE.replace("选项与我的建议：\n",
                              f"模块：{value}\n选项与我的建议：\n", 1)

    def test_module_id_kept(self):
        r = self.receive(self.with_module("zeta"))
        self.assertEqual(self.item(r.item)["module"], "zeta")

    def test_line_level_kept_as_written(self):
        r = self.receive(self.with_module("无"))
        self.assertEqual(self.item(r.item)["module"], "无")

    def test_without_field_no_key(self):
        r = self.receive(SINGLE)
        self.assertNotIn("module", self.item(r.item))


D1_ONLY = DECISIONS.replace("D2：错误日志保留多久？\n  A. 7 天\n  B. 30 天\n  倾向：A\n", "").replace("；D2 A", "")
# What the hub wrote to said.txt for #69–#72 on 2026-10-20 (I-16): three items on one line, then one per line.
SAID_9430 = ("69 A；D1 A   70 A；D1 A  71 A；D1 A\n\n72 A 批准能力图及 README 文档范围\n"
             "69 A；D1 A\n70 A；D1 A\n71 A；D1 A\n")


class InlineSplitTest(ItemsCase):
    """stage-c2-fixes I-16: several items on one line are split per item; each keeps only its own words."""

    def setUp(self):
        super().setUp()
        store.set_start_number(self.g, 69)
        # different senders: a sender's new item supersedes its pending one
        for n, sender in ((69, "coord"), (70, "fe-owner"), (71, "api-codex")):
            self.assertEqual(self.receive(D1_ONLY, sender=sender, relay_id=n).item, n)
        self.assertEqual(self.receive(SINGLE, relay_id=72, at=T2).item, 72)

    def parse(self, text):
        return items.interpret_reply(self.g, text)

    def test_replay_9430(self):
        p = self.parse(SAID_9430)
        self.assertIsNone(p.question)
        got = {a.item: a.original for a in p.answers}
        self.assertEqual(got, {69: "69 A；D1 A", 70: "70 A；D1 A", 71: "71 A；D1 A",
                               72: "72 A 批准能力图及 README 文档范围"})
        out = items.answer(self.g, p.answers, answered_at=T3)
        to_69 = next(o.text for o in out if o.item == 69)
        self.assertNotIn("70 A", to_69)
        self.assertNotIn("71 A", to_69)

    def test_one_line_two_items(self):
        p = self.parse("69 A；D1 A 72 B")
        self.assertIsNone(p.question)
        self.assertEqual({a.item: (a.letter, a.original) for a in p.answers},
                         {69: ("A", "69 A；D1 A"), 72: ("B", "72 B")})

    def test_numbers_in_the_words_are_not_split(self):
        for text in ("72 A 提交 3f2a1b9", "72 A 第 70 步先做", "72 原话：验收 69、70 都要补"):
            with self.subTest(text=text):
                p = self.parse(text)
                self.assertIsNone(p.question)
                self.assertEqual([(a.item, a.original) for a in p.answers], [(72, text)])

    def test_letter_must_be_that_items_option(self):
        p = self.parse("72 A 改成 69 Z，再看")
        self.assertIsNone(p.question)
        self.assertEqual([a.item for a in p.answers], [72])

    def test_mixed_in_without_split_asks(self):
        p = self.parse("72 A，顺便69 A；D1 A")
        self.assertEqual(p.answers, ())
        q = p.question
        self.assertIsNotNone(q)
        self.assertIn("#69", q)
        self.assertIn("#72", q)
