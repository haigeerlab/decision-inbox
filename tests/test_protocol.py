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


class MultilineTest(unittest.TestCase):
    def test_complete_scopes(self):
        msg = protocol.parse(fixture("wait-user-multiline.txt"))
        self.assertTrue(msg.ok, msg.problems)
        self.assertEqual(msg.lines_in_scope, ("前端", "API"))
        self.assertEqual(msg.scopes["前端"], "只改类型定义和展示映射，不改接口调用")
        self.assertEqual(msg.scopes["API"], "改响应字段名并补兼容期旧字段，\n兼容期两周")

    def test_scope_missing(self):
        text = fixture("wait-user-multiline.txt").replace(
            "- API：改响应字段名并补兼容期旧字段，\n  兼容期两周\n", "")
        self.assertIn("scope-missing:API", codes(protocol.parse(text).problems))

    def test_scope_unknown(self):
        text = fixture("wait-user-multiline.txt").replace(
            "选项与我的建议：", "- 后台：顺便改报表\n选项与我的建议：")
        self.assertIn("scope-unknown:后台", codes(protocol.parse(text).problems))

    def test_scope_section_missing(self):
        base = fixture("wait-user-multiline.txt")
        text = base[:base.index("各线范围")] + base[base.index("选项与我的建议"):]
        msg = protocol.parse(text)
        self.assertIn("missing-field:各线范围", codes(msg.problems))

    def test_single_line_message_has_no_scope(self):
        msg = protocol.parse(fixture("wait-user.txt"))
        self.assertEqual((msg.lines_in_scope, msg.scopes), ((), {}))


class ReviewLineTest(unittest.TestCase):
    def parse_with(self, line):
        text = fixture("wait-user.txt").replace("要点：", (line + "\n要点：") if line else "要点：")
        return protocol.parse(text)

    def test_five_forms(self):
        cases = {
            "架构审查：通过": ("passed", None, None),
            "架构审查：通过（R-3）": ("passed", None, "R-3"),
            "架构审查：通过，附建议2条（命名、日志）": ("passed-with-advice", 2, None),
            "架构审查：通过，附建议1条（日志）(#41)": ("passed-with-advice", 1, "#41"),
            "架构审查：进行中，请勿先批": ("in-progress", None, None),
            "架构审查：不适用（不属于审查节点）": ("not-applicable", None, None),
            "架构审查：用户豁免": ("waived", None, None),
            "架构审查:通过,附建议3条": ("passed-with-advice", 3, None),
        }
        for line, (status, advice, ref) in cases.items():
            with self.subTest(line=line):
                msg = self.parse_with(line)
                self.assertEqual((msg.review.status, msg.review.advice_count, msg.review.ref),
                                 (status, advice, ref))
                self.assertTrue(msg.ok, msg.problems)

    def test_unrecognized_and_absent(self):
        msg = self.parse_with("架构审查：已看过，问题不大")
        self.assertEqual(msg.review.status, "unrecognized")
        self.assertEqual(msg.review.raw, "已看过，问题不大")
        self.assertTrue(msg.ok)
        msg = self.parse_with("架构审查：—")
        self.assertEqual(msg.review.status, "unrecognized")
        msg = self.parse_with(None)
        self.assertEqual(msg.review.status, "absent")
        self.assertIsNone(msg.review.raw)
        self.assertTrue(msg.ok)


ORIGINAL = "12 B\n  补充：先做 A 的接口，#3 那项也一起！\n最后一行：「就这样」。"


class UserReplyTest(unittest.TestCase):
    def test_round_trip(self):
        for original in (ORIGINAL, "12 A", "按推荐来"):
            with self.subTest(original=original):
                text = protocol.format_user_reply(item=12, original=original, answered_at="2026-10-16 14:05",
                                                  option_text="B：先接支付宝")
                msg = protocol.parse(text)
                self.assertEqual(msg.kind, "user-reply")
                self.assertTrue(msg.ok, msg.problems)
                self.assertEqual(msg.item, 12)
                self.assertEqual(msg.fields["用户原话"], original)
                self.assertEqual(msg.fields["选项原文"], "B：先接支付宝")
                self.assertIn("选项 B 原文：", text)
                self.assertEqual(msg.fields["答复时间"], "2026-10-16 14:05")

    def test_without_option_text(self):
        text = protocol.format_user_reply(item=7, original="自己写的一句话", answered_at="t")
        self.assertNotIn("原文", text)
        self.assertTrue(protocol.parse(text).ok)

    def test_required_fields(self):
        text = protocol.format_user_reply(item=7, original="x", answered_at="t")
        for drop, code in (("答复时间：t\n", "missing-field:答复时间"), ("事项：#7\n", "missing-field:事项")):
            with self.subTest(code=code):
                self.assertIn(code, codes(protocol.parse(text.replace(drop, "")).problems))

    def test_multiline_replies(self):
        original_item = fixture("wait-user-multiline.txt")
        out = protocol.format_multiline_replies(item=30, sender="总协调", original=ORIGINAL,
                                                answered_at="2026-10-16 14:10", wait_user_text=original_item)
        self.assertEqual(sorted(out), ["API", "前端"])
        source = protocol.parse(original_item)
        for line, text in out.items():
            with self.subTest(line=line):
                msg = protocol.parse(text)
                self.assertEqual(msg.kind, "user-reply")
                self.assertTrue(msg.ok, msg.problems)
                self.assertEqual(msg.item, 30)
                self.assertIn("多线事项，发起方：总协调", msg.fields["事项"])
                self.assertEqual(msg.fields["用户原话"], ORIGINAL)
                self.assertEqual(msg.fields["适用于你的范围"], source.scopes[line])
                self.assertEqual(msg.fields["原事项全文"], original_item.rstrip("\n"))

    def test_multiline_reply_requires_scope_and_original(self):
        text = protocol.format_multiline_replies(item=30, sender="总协调", original="30 A", answered_at="t",
                                                 wait_user_text=fixture("wait-user-multiline.txt"))["前端"]
        cut = text[:text.index("原事项全文")]
        self.assertIn("missing-field:原事项全文", codes(protocol.parse(cut).problems))

    def test_multiline_needs_valid_source(self):
        with self.assertRaises(ValueError):
            protocol.format_multiline_replies(item=12, sender="前端", original="x", answered_at="t",
                                              wait_user_text=fixture("wait-user.txt"))


class ReviewConclusionTest(unittest.TestCase):
    def test_parse(self):
        msg = protocol.parse(fixture("review-conclusion.txt"))
        self.assertEqual(msg.kind, "review-conclusion")
        self.assertTrue(msg.ok, msg.problems)
        c = msg.conclusion
        self.assertEqual((c.ref, c.node, c.submitter, c.verdict, c.advice_count),
                         ("R-3", "spec", "前端", "changes-required", None))

    def test_module_field(self):
        base = fixture("review-conclusion.txt")
        self.assertIsNone(protocol.parse(base).conclusion.module)
        msg = protocol.parse(base.replace("节点：Spec\n", "节点：Spec\n模块： pay-page \n"))
        self.assertTrue(msg.ok, msg.problems)
        self.assertEqual(msg.conclusion.module, "pay-page")
        self.assertIsNone(protocol.parse(base.replace("节点：Spec\n", "节点：Spec\n模块：\n")).conclusion.module)

    def test_nodes_and_verdicts(self):
        base = fixture("review-conclusion.txt")
        for written, node in (("Spec", "spec"), ("Plan", "plan"), ("接口提案", "interface"), ("最终验收", "final")):
            with self.subTest(node=written):
                msg = protocol.parse(base.replace("节点：Spec", f"节点：{written}"))
                self.assertEqual(msg.conclusion.node, node)
        for written, verdict, advice in (("通过", "passed", None), ("通过，附建议2条", "passed-with-advice", 2),
                                         ("通过,附建议1条（命名）", "passed-with-advice", 1),
                                         ("有须修改项", "changes-required", None)):
            with self.subTest(verdict=written):
                msg = protocol.parse(base.replace("结论：有须修改项", f"结论：{written}"))
                self.assertTrue(msg.ok, msg.problems)
                self.assertEqual((msg.conclusion.verdict, msg.conclusion.advice_count), (verdict, advice))

    def test_problems(self):
        base = fixture("review-conclusion.txt")
        for line in ("审查编号：R-3\n", "节点：Spec\n", "送审方：前端\n", "结论：有须修改项\n"):
            name = line.split("：")[0]
            with self.subTest(drop=name):
                msg = protocol.parse(base.replace(line, ""))
                self.assertIn(f"missing-field:{name}", codes(msg.problems))
                self.assertIsNone(msg.conclusion)
        self.assertIn("bad-node", codes(protocol.parse(base.replace("节点：Spec", "节点：需求")).problems))
        self.assertIn("bad-verdict", codes(protocol.parse(base.replace("结论：有须修改项", "结论：差不多")).problems))

    def test_other_kinds_have_no_conclusion(self):
        self.assertIsNone(protocol.parse(fixture("wait-user.txt")).conclusion)


class CodeTableTest(unittest.TestCase):
    @staticmethod
    def family(code):
        return code.split(":")[0] + ":" if ":" in code else code

    def test_table_matches_spec(self):
        spec = (Path(__file__).resolve().parent.parent / "spec" / "message-protocol.md").read_text(encoding="utf-8")
        for code in protocol.PROBLEM_CODES + protocol.HINT_CODES:
            with self.subTest(code=code):
                self.assertIn(code.rstrip(":"), spec)

    def test_emitted_codes_are_in_table(self):
        texts = [p.read_text(encoding="utf-8") for p in FIX.glob("*.txt")]
        texts += ["", "【等待用户】【取代】\n", "【已恢复】\n", "【撤回】\n", "【用户答复】\n", "【等待其他会话】\n",
                  fixture("wait-user.txt").replace("是否完全停住：是", "是否完全停住：大概"),
                  fixture("wait-user-multiline.txt").replace("- 前端：", "- 后台："),
                  fixture("review-conclusion.txt").replace("节点：Spec", "节点：需求").replace("结论：有须修改项", "结论：?"),
                  "【审查结论】\n"]
        for text in texts:
            msg = protocol.parse(text)
            for issue in msg.problems:
                self.assertIn(self.family(issue.code), protocol.PROBLEM_CODES, issue.code)
            for issue in msg.hints:
                self.assertIn(self.family(issue.code), protocol.HINT_CODES, issue.code)


if __name__ == "__main__":
    unittest.main()
