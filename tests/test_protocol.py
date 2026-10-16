import unittest
from pathlib import Path

from decision_inbox import protocol

FIX = Path(__file__).resolve().parent / "fixtures" / "protocol"


def fixture(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def codes(issues):
    return {i.code for i in issues}


class SkeletonTest(unittest.TestCase):
    def test_wait_session(self):
        msg = protocol.parse(fixture("wait-session.txt"))
        self.assertEqual(msg.kind, "wait-session")
        self.assertTrue(msg.ok, msg.problems)
        self.assertEqual(msg.reply_to, 40)
        self.assertEqual(msg.ends.ids, (31,))
        self.assertEqual(msg.fields["在等谁"], "API")
        self.assertEqual(msg.fields["等什么"], "订单接口的 Mock 数据，\n  交付后我才能接着做支付页")

    def test_header_order_does_not_matter(self):
        lines = fixture("wait-session.txt").split("\n")
        for head in ([1, 0, 2], [2, 1, 0], [0, 2, 1]):
            with self.subTest(head=head):
                text = "\n".join([lines[i] for i in head] + lines[3:])
                msg = protocol.parse(text)
                self.assertEqual((msg.kind, msg.reply_to, msg.ends.ids), ("wait-session", 40, (31,)))
                self.assertTrue(msg.ok)

    def test_end_line_after_fields_is_not_header(self):
        text = "【等待其他会话】\n在等谁：API\n等什么：Mock\n结束：#31\n"
        msg = protocol.parse(text)
        self.assertIn("missing-end", codes(msg.problems))

    def test_wait_session_required(self):
        base = fixture("wait-session.txt")
        cases = {"在等谁：API\n": "missing-field:在等谁", "结束：#31\n": "missing-end"}
        for drop, code in cases.items():
            with self.subTest(code=code):
                msg = protocol.parse(base.replace(drop, ""))
                self.assertIn(code, codes(msg.problems))
                self.assertFalse(msg.ok)

    def test_half_width_colon(self):
        msg = protocol.parse(fixture("wait-session.txt").replace("：", ":"))
        self.assertTrue(msg.ok, msg.problems)
        self.assertEqual(msg.fields["在等谁"], "API")

    def test_resumed(self):
        msg = protocol.parse(fixture("resumed.txt"))
        self.assertEqual(msg.kind, "resumed")
        self.assertTrue(msg.ok)
        self.assertEqual(msg.ends.ids, (12, 15))

    def test_resumed_unnumbered_and_missing(self):
        msg = protocol.parse("【已恢复】\n结束：无编号（对方没给编号）\n")
        self.assertTrue(msg.ok)
        self.assertEqual(msg.ends.unnumbered_reason, "对方没给编号")
        self.assertIn("missing-end", codes(protocol.parse("【已恢复】\n接着干活。\n").problems))
        self.assertIn("missing-end", codes(protocol.parse("【已恢复】\n结束：无\n").problems))

    def test_withdraw(self):
        msg = protocol.parse("【撤回】\n事项：#8\n原因：需求取消\n")
        self.assertEqual(msg.kind, "withdraw")
        self.assertTrue(msg.ok)
        self.assertEqual(msg.item, 8)
        self.assertIn("missing-field:事项", codes(protocol.parse("【撤回】\n原因：x\n").problems))

    def test_markers(self):
        msg = protocol.parse("【等待用户】【取代 #8】\n结束：无\n")
        self.assertEqual(msg.kind, "wait-user")
        self.assertEqual(msg.markers, (("supersede", 8),))
        msg = protocol.parse("【等待用户】\n【与 #9 并行】\n结束：无\n")
        self.assertEqual(msg.markers, (("parallel", 9),))
        self.assertIn("missing-field:取代编号", codes(protocol.parse("【等待用户】【取代】\n结束：无\n").problems))

    def test_unknown_kind(self):
        for text in ("随便说两句", "", "【进度】一切正常"):
            with self.subTest(text=text):
                msg = protocol.parse(text)
                self.assertEqual(msg.kind, "unknown")
                self.assertIn("unknown-kind", codes(msg.problems))


class WaitUserTest(unittest.TestCase):
    def test_complete_message(self):
        msg = protocol.parse(fixture("wait-user.txt"))
        self.assertEqual(msg.kind, "wait-user")
        self.assertTrue(msg.ok, msg.problems)
        self.assertTrue(msg.ends.none)
        self.assertEqual(msg.fields["来自"], "前端")
        self.assertEqual(msg.fields["要你决定"], "支付页先接哪种支付方式")
        self.assertIn("来自：这一行是要点正文的一部分", msg.fields["要点"])
        self.assertEqual([o.letter for o in msg.options], ["A", "B", "C"])
        self.assertEqual(msg.options[0].text, "先接微信支付")
        self.assertEqual(msg.options[0].consequence, "本周能上线支付页，支付宝下周补")
        self.assertEqual(msg.options[1].text, "先接支付宝")
        self.assertIsNone(msg.options[2].consequence)
        self.assertEqual(msg.recommended, "A")
        self.assertEqual(msg.suggested_reply, "12 A 先接微信支付")
        self.assertIs(msg.fully_stopped, True)
        self.assertEqual(codes(msg.hints), {"no-consequence:C"})

    def test_required_fields(self):
        base = fixture("wait-user.txt").replace("来自：这一行是要点正文的一部分，不是新字段\n", "")
        cases = {
            "来自：前端\n": "missing-field:来自",
            "要你决定：支付页先接哪种支付方式\n": "missing-field:要你决定",
            "是否完全停住：是\n": "missing-field:是否完全停住",
            "结束：无\n": "missing-end",
        }
        for drop, code in cases.items():
            with self.subTest(code=code):
                msg = protocol.parse(base.replace(drop, ""))
                self.assertIn(code, codes(msg.problems))
                self.assertFalse(msg.ok)
        start = base.index("选项与我的建议")
        no_options = base[:start] + base[base.index("你该回"):]
        self.assertIn("missing-options", codes(protocol.parse(no_options).problems))
        bad = protocol.parse(base.replace("是否完全停住：是", "是否完全停住：大概"))
        self.assertIn("bad-stop-flag", codes(bad.problems))
        self.assertIsNone(bad.fully_stopped)
        self.assertIs(protocol.parse(base.replace("是否完全停住：是", "是否完全停住：否")).fully_stopped, False)

    def test_missing_consequence_and_recommendation_are_hints(self):
        text = fixture("wait-user.txt").replace("推荐 A：", "A：").replace(
            "  选了会怎样：要多等三天 API 补签名接口\n", "")
        msg = protocol.parse(text)
        self.assertTrue(msg.ok, msg.problems)
        self.assertIsNone(msg.recommended)
        self.assertEqual(codes(msg.hints), {"no-consequence:B", "no-consequence:C", "no-recommendation"})

    def test_option_letter_styles(self):
        for sep in ("：", ":", ".", "、", ")"):
            with self.subTest(sep=sep):
                text = "【等待用户】\n结束：无\n来自：前端\n要你决定：x\n选项与我的建议：\nA" + sep + \
                       "方案一\nB" + sep + "方案二\n推荐：B\n是否完全停住：否\n"
                msg = protocol.parse(text)
                self.assertTrue(msg.ok, msg.problems)
                self.assertEqual([(o.letter, o.text) for o in msg.options], [("A", "方案一"), ("B", "方案二")])
                self.assertEqual(msg.recommended, "B")


if __name__ == "__main__":
    unittest.main()
