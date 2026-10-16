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


if __name__ == "__main__":
    unittest.main()
