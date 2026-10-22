"""decision-cards Task 4: the template's seven classes, one copy block per card, 「一次答完」 over approvals."""

import re
from types import SimpleNamespace as NS

from test_approval import T1, T2, ApprovalCase

from decision_inbox import cards, health, items, protocol, store, view

NOW = "2026-10-19T12:00:00+08:00"

FINAL_BRIEF = """验收标准与证据：
- 前提断言：测试 preconditions hold ✔
- 1 word_counts("one two") 深相等：测试 counts each word ✔
- 2 word_counts("Hello") 深相等：测试 merges case ✔
- 3 停用词：测试 skips every stopword ✔
- 单测：node --test → pass 8 fail 0
- 完整检查：sh scripts/slow-check.sh → node --test pass 27 fail 0
C134 delta 的最终验收（审查：main 通过）：
- 位置：分支 delta，提交 71dc7c6
- Task 1：pnpm add -D -E is-plain-obj@4.1.0，锁文件只多了 3 行
- Task 2：先写测试跑出失败，再写实现
- 停用词文件没有改
- 新增依赖：is-plain-obj@4.1.0
- Spec 在构建中没有补改；Plan 没有改
- todo：Task 1、Task 2 已勾选
验收标准与证据：
- 1 word_counts("one two") 深相等：测试 counts each word ✔
"""

REVIEW = "回复：#8653\n【审查结论】\n审查编号：R-38\n节点：Spec\n模块：alpha\n送审方：门店\n结论：通过\n来自：main 审查\n" \
         "要点：目标、范围和能力图对得上，验收标准都能测。另外一句。\n"


def code_blocks(text):
    return re.findall(r"```\n(.*?)\n```", text, re.S)


class CardCase(ApprovalCase):
    def setUp(self):
        super().setUp()
        with self.g.transaction() as tx:  # a second line, so two items do not supersede each other
            tx.add_session({"relayName": "coord2", "shortName": "后台", "role": "dev", "line": ["后台"],
                            "host": "claude-desktop", "repo": "/tmp/c2"})

    def wait_user(self, decide="接下来怎么办", brief="出事了", options=None, rec="B", extra="", sender="coord", at=T1):
        options = options or "推荐 B：换方案\n  选了会怎样：不再弹窗\nA：挂起\n  选了会怎样：这条线停住\nC：照旧\n  选了会怎样：每次都弹\n"
        text = (f"【等待用户】\n结束：无\n来自：门店\n项目：crew-rehearsal\n要你决定：{decide}\n要点：{brief}\n{extra}"
                f"选项与我的建议：\n{options}你该回：{rec}\n是否完全停住：否\n")
        r = items.receive(self.g, text, sender=sender, relay_id=next(self.relay_ids), received_at=at)
        self.assertTrue(r.accepted, r.problems)
        return r.item

    def set(self, no, **fields):
        with self.g.transaction() as tx:
            doc = tx.read_state("items")
            doc["items"][str(no)].update(fields)
            tx.write_state("items", doc)

    def main(self, loop_facts=None):
        return view.render(self.g, now=NOW, assessment=health.assess(self.g, now=NOW, relay=None),
                           loop_facts=loop_facts)

    def card(self, no):
        return view.render_look(self.g, no, NOW)


class KindTest(CardCase):
    def test_classes(self):
        for node, k in (("Spec", "spec"), ("Plan", "plan"), ("最终验收", "final"), ("接口提案", "interface")):
            with self.subTest(node=node):
                self.assertEqual(cards.kind({"approvalNode": node}), k)
        self.assertEqual(cards.kind({"approvalNode": None}), "stuck")
        self.assertEqual(cards.kind({"waitKind": "go-to-session"}), "go-to-session")


class ApprovalCardTest(CardCase):
    def test_frame_order_and_one_copy_block(self):
        no = self.ask()
        text = self.card(no)
        lines = [x for x in text.split("\n") if x.strip()]
        self.assertTrue(lines[0].startswith(f"**#{no} · alpha 的 Spec，批不批** · 等了 "), lines[0])
        self.assertEqual(lines[1], "crew-rehearsal · 门店 · 模块 alpha · Spec（第 1 次交审）")
        order = [next(i for i, x in enumerate(lines) if x.startswith(p))
                 for p in ("**内容要点**", "**结论**", "**A 批准**", "**B 先不批**", "**推荐 A**", "```")]
        self.assertEqual(order, sorted(order))
        self.assertEqual(code_blocks(text), [f"{no} A"])
        self.assertIn(f"答复写法：回 {no} B", text)
        self.assertNotIn("交审原文", text)
        self.assertNotIn("【交审】", text)

    def test_main_view_has_no_originals_and_every_card_a_copy_block(self):
        a = self.ask()
        b = self.wait_user(sender="coord2", at=T2)
        out = self.main()
        self.assertNotIn("━━ 开发会话的交审原文", out)
        self.assertNotIn("【交审】", out)
        self.assertIn(f"{a} A", code_blocks(out))
        self.assertIn(f"{b} B", code_blocks(out))

    def test_round_and_last_answer(self):
        first = self.ask(at=T1)
        items.answer(self.g, [items.Answer(first, "B", f"{first} B：先改范围")], answered_at=T1)
        second = self.ask(at=T2)
        self.assertIn("Spec（第 2 次交审；上次你答：", self.card(second))

    def test_conclusion_from_review_original(self):
        no = self.ask()
        ref = self.original("review.txt", REVIEW)
        path, fp = ref.split(" ")
        self.set(no, originals={"submission": [], "conclusion": [{"path": path, "fingerprint": fp, "module": None}]})
        self.assertIn("**结论**：main 审查通过（R-38）。目标、范围和能力图对得上，验收标准都能测", self.card(no))
        open(path, "w", encoding="utf-8").write("改过了")
        self.set(no, review={"text": "已审：通过", "ref": None, "highlight": False, "warn": False, "mentions": []})
        self.assertIn("**结论**：已审：通过", self.card(no))
        self.set(no, review={})
        self.assertIn("**结论**：未审查", self.card(no))

    def test_final_card_points_are_condensed(self):
        no = self.ask(node="最终验收")
        self.set(no, brief=FINAL_BRIEF)
        text = self.card(no)
        self.assertEqual(text.count("**验收结果**"), 1)
        self.assertIn("**验收结果**：验收标准 3 条，标了通过的 3 条；完整检查：sh scripts/slow-check.sh", text)
        self.assertIn(f"其余见：回「看 {no} 全文」", text)
        self.assertLessEqual(len([x for x in text.split("\n") if x.strip()]), cards.max_lines("spec-plan"))
        self.assertEqual(cards.max_lines("spec-plan"), cards.MAX_LINES + 4)
        self.assertNotIn("锁文件只多了", text.split("**结论**")[1])

    def test_final_card_has_no_loop_head(self):
        """decision-cards I-10: the loop counts are not an approval's head."""
        no = self.ask(node="最终验收")
        self.set(no, module="alpha")
        it = items.get(self.g, no)
        f = NS(line="coord", module="alpha", project="crew-rehearsal", items=(it,), asked=4, baseline=3, over=1,
               still=0, unread=None, worked_hours=2.4, progress=(0, 4), hit=None, ready=(), key="coord|alpha",
               baseline_parts=None, last_progress=None)
        head = self.main(loop_facts=[f]).split(f"**#{no}")[1].split("\n")[0]
        self.assertNotIn("进度", head)
        self.assertNotIn("你答了", head)

    def test_decisions_join_the_copy_block(self):
        no = self.ask()
        self.set(no, decisions=[{"id": "D1", "question": "停用词格式", "options": [["A", "小写"], ["B", "随意"]],
                                 "lean": "A", "leanReason": None}])
        text = self.card(no)
        self.assertEqual(code_blocks(text), [f"{no} A；D1 A"])
        self.assertIn("**推荐 A；D1 选 A**", text)
        self.assertIn("**D1** 停用词格式 A. 小写　B. 随意（审查倾向 A）", text)


class StuckAndGoToTest(CardCase):
    def test_stuck_frame(self):
        no = self.wait_user(brief="24 小时内弹了 4 次\n因为没放行")
        text = self.card(no)
        lines = [x for x in text.split("\n") if x.strip()]
        self.assertTrue(lines[0].startswith(f"**#{no} · 接下来怎么办** · 等了"))
        self.assertEqual(lines[1:3], ["crew-rehearsal · 门店", "**出了什么事**："])
        self.assertEqual([x[:5] for x in lines if x.startswith("**") and x[2] in "ABC"],
                         ["**A 挂", "**B 换", "**C 照"])
        self.assertEqual(code_blocks(text), [f"{no} B"])

    def test_go_to_session_has_no_code_block(self):
        text = ("【等待用户】\n结束：无\n来自：门店\n项目：crew-rehearsal\n要你决定：去 epsilon 会话点权限弹窗\n"
                "要点：它在合并 main，被弹窗拦住了。\n类型：去会话操作\n会话：epsilon 模块会话\n链接：local_abc\n"
                "被拦的操作：git merge main\n点哪个按钮：合并、装依赖点允许；推送、删除点拒绝\n"
                "为什么批不了：宿主弹窗只能你亲手点\n选项与我的建议：\n推荐 A：我去点\n  选了会怎样：继续合并\n"
                "是否完全停住：否\n")
        r = items.receive(self.g, text, sender="coord", relay_id=901, received_at=T1)
        self.assertTrue(r.accepted, r.problems)
        no = r.item
        from decision_inbox import hub
        out = hub.main_view(self.g, NOW)
        self.assertIn(f"**#{no} · 去 epsilon 模块会话 点一下弹窗**", out)
        self.assertIn("点完不用回复，会自动结项。", out)
        self.assertEqual(code_blocks(out), [])


class CombinedTest(CardCase):
    def test_includes_approvals_and_round_trips(self):
        a = self.ask()
        b = self.wait_user(sender="coord2", at=T2, rec="B 换方案：先给我看预览，再写")
        out = self.main()
        block = out.split("一次答完（全按推荐）：")[1]
        [joined] = code_blocks(block)
        parsed = items.interpret_reply(self.g, joined)
        self.assertIsNone(parsed.question)
        self.assertEqual(sorted((x.item, x.letter) for x in parsed.answers), [(a, "A"), (b, "B")])

    def test_single_line_when_no_separators(self):
        a = self.ask()
        b = self.wait_user(sender="coord2", at=T2)
        [joined] = code_blocks(self.main().split("一次答完（全按推荐）：")[1])
        self.assertEqual(joined, f"{a} A，{b} B")



class FullTextTest(CardCase):
    """decision-cards Task 5 (DI-3): 「看 N 全文」 shows the originals, never as a code block."""

    def full(self, no):
        from decision_inbox import hub
        return hub.reply(self.g, f"看 {no} 全文", now=NOW).show

    def test_originals_without_code_blocks(self):
        no = self.ask()
        text = self.full(no)
        self.assertIn("━━ 开发会话的交审原文", text)
        self.assertNotIn("```", text)
        self.assertIn("│ 【交审】\n│ 结束：无\n│ 模块：alpha", text)
        self.assertIn("# alpha", text)  # Markdown shown as it is

    def test_markdown_fences_are_not_code_blocks(self):
        self.commit_file("spec/alpha.md", "# alpha\n\n```js\nlet x = 1\n```\n")
        no = self.ask()
        text = self.full(no)
        self.assertNotIn("\n```", text)
        self.assertIn("│ ```js\nlet x = 1\n│ ```", text)

    def test_long_file_is_cut(self):
        self.commit_file("spec/alpha.md", "".join(f"第 {i} 行\n" for i in range(1, 351)))
        no = self.ask()
        text = self.full(no)
        self.assertIn("第 300 行", text)
        self.assertNotIn("第 301 行", text)
        self.assertIn(f"还有 50 行，见 {self.repo}/spec/alpha.md ＠ {self.commit}", text)

    def test_answered_item_still_viewable(self):
        no = self.ask()
        items.answer(self.g, [items.Answer(no, "A", f"{no} A")], answered_at=T2)
        self.assertIn("━━ 开发会话的交审原文", self.full(no))
        self.assertIn("不存在", self.full(999))

    def commit_file(self, rel, text):
        import subprocess
        (self.repo / rel).write_text(text, encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qam", "y"], check=True)
        self.commit = subprocess.run(["git", "-C", str(self.repo), "rev-parse", "--short=7", "HEAD"], check=True,
                                     capture_output=True, text=True).stdout.strip()


V23 = __import__("pathlib").Path(__file__).resolve().parent / "fixtures" / "session-protocol" / f"v{protocol.CONTRACT_VERSION}" / "wait-user"


class V23CardTest(CardCase):
    """decision-cards Task 9: cards from session-protocol v2.3 「类型」 and content points."""

    def receive(self, name, sender="coord"):
        r = items.receive(self.g, (V23 / name).read_text(encoding="utf-8"), sender=sender,
                          relay_id=next(self.relay_ids), received_at=T1)
        self.assertTrue(r.accepted, r.problems)
        return r.item

    def labels(self, text):
        return [line.split("**")[1] for line in text.split("\n") if line.startswith("**") and "**：" in line]

    def test_final_card_follows_the_template(self):
        no = self.receive("card-final.txt")
        text = self.card(no)
        lines = [x for x in text.split("\n") if x.strip()]
        self.assertTrue(lines[0].startswith(f"**#{no} · delta 的最终验收，批不批** · 等了"), lines[0])
        self.assertEqual(lines[1], "crew-rehearsal · 门店 · 模块 未知 · 最终验收（第 1 次交审）")
        self.assertEqual(self.labels(text)[:7], ["做了什么", "验收结果", "改了哪些文件", "Spec 中途改过吗", "批了会怎样",
                                                "结论", "注意"])
        self.assertIn(f"**改了哪些文件**：5 个文件，+85 −2（共 6 行，见「看 {no} 全文」）", text)
        self.assertIn("**批了会怎样**：合并进本地 main，模块完成；合了撤不回，推送仍要你另外同意", text)
        self.assertIn("**注意**：无", text)
        self.assertIn("**推荐 A**：审查通过，没超出你批的范围", text)
        self.assertEqual(code_blocks(text), [f"{no} A"])
        self.assertNotIn("内容要点**：\n- ", text)  # points replace the picked brief lines

    def test_spec_plan_is_one_card_with_nine_points(self):
        no = self.receive("card-spec-plan.txt")
        text = self.card(no)
        self.assertIn("Spec 与 Plan（第 1 次交审）", text)
        self.assertEqual(self.labels(text)[:10], ["目标", "做／不做", "要你确认的假设", "验收标准", "附带的小决定",
                                                 "分几步", "会改哪些文件", "风险", "中途会停下来问你的地方", "批了会怎样"])
        self.assertIn(f"**验收标准**：共 2 条；例：AC1 过期令牌自动刷新一次（其余见「看 {no} 全文」）", text)
        self.assertLessEqual(len([x for x in text.split("\n") if x.strip()]), cards.max_lines("spec-plan"))
        self.assertEqual(cards.max_lines("spec-plan"), cards.MAX_LINES + 4)

    def test_spec_card_and_kind_from_type(self):
        no = self.receive("card-spec.txt")
        self.assertEqual(cards.kind(items.get(self.g, no)), "spec")
        self.assertIn("**目标**：", self.card(no))

    def test_unknown_type_is_returned(self):
        r = items.receive(self.g, (V23 / "card-kind-unknown.txt").read_text(encoding="utf-8"), sender="coord",
                          relay_id=990, received_at=T1)
        self.assertFalse(r.accepted)

    def test_full_text_lists_every_point(self):
        no = self.receive("card-final.txt")
        from decision_inbox import hub
        full = hub.reply(self.g, f"看 {no} 全文", now=NOW).show
        self.assertIn("| package.json | 加 is-plain-obj 4.1.0（你在 #44 批过） |", full)
        self.assertNotIn("```", full)


class NoteSourceTest(CardCase):
    """decision-cards D1 B (final acceptance): writing hints are the proposer's, never a card's 注意."""

    def test_writing_hint_not_shown_as_note(self):
        no = self.ask()
        self.set(no, writingNotes=["「你该回」只写了选项字母，没写完整回复原文"])
        self.assertNotIn("**注意**", self.card(no))
        self.set(no, note="无")
        self.assertIn("**注意**：无", self.card(no))


class V26CardTest(V23CardTest):
    """protocol-contract-v2-6 (session-protocol v2.6): Spec/Plan point names after upstream agent-skills."""

    def test_spec_card_with_upstream_names(self):
        text = self.card(self.receive("card-spec-upstream.txt"))
        self.assertEqual(self.labels(text)[:5], ["目标", "边界", "要你确认的假设", "验收标准", "未决问题"])

    def test_plan_card_with_upstream_names(self):
        text = self.card(self.receive("card-plan-upstream.txt"))
        self.assertEqual(self.labels(text)[:6], ["架构决定", "分几步", "会改哪些文件", "风险", "中途会停下来问你的地方",
                                                "未决问题"])

    def test_old_and_new_names_both_shown(self):
        body = (V23 / "card-spec-upstream.txt").read_text(encoding="utf-8").replace("边界：", "做／不做：旧写法\n边界：", 1)
        r = items.receive(self.g, body, sender="coord", relay_id=next(self.relay_ids), received_at=T1)
        labels = self.labels(self.card(r.item))
        self.assertIn("做／不做", labels)
        self.assertIn("边界", labels)
