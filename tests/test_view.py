import unittest
from pathlib import Path

from helpers import TempHomeTestCase

from decision_inbox import items, store, tickets, view
from decision_inbox.health import Assessment, LineState, Signal

PROTO = Path(__file__).resolve().parent / "fixtures" / "protocol"
NOW = "2026-10-16T12:00:00+08:00"


def at(minutes_ago: int) -> str:
    """An instant `minutes_ago` minutes before NOW."""
    from datetime import datetime, timedelta
    return (datetime.fromisoformat(NOW) - timedelta(minutes=minutes_ago)).isoformat()


def wait_session(target: str, what: str = "订单接口") -> str:
    return f"【等待其他会话】\n结束：无\n在等谁：{target}\n等什么：{what}\n"


WORKING = LineState("working", "干活中")
IDLE = LineState("done", "已结项（空闲）")


class ViewCase(TempHomeTestCase):
    def setUp(self):
        super().setUp()
        self.g, _ = store.init_group("demo")
        people = [
            ("hub", "收件枢纽", "hub", [], "claude-desktop"),
            ("fe-codex", "前端", "dev", ["前端"], "codex-desktop"),
            ("api-codex", "API", "dev", ["API"], "codex-desktop"),
            ("bg-codex", "后台", "dev", ["后台"], "codex-desktop"),
            ("coord", "总协调", "coordinator", [], "codex-desktop"),
        ]
        with self.g.transaction() as tx:
            for relay, short, role, line, host in people:
                entry = {"relayName": relay, "shortName": short, "role": role, "line": line, "host": host}
                if role == "dev":
                    entry["repo"] = f"/tmp/{relay}"
                tx.add_session(entry)
        self.relay_ids = iter(range(500, 600))

    def assessment(self, lines=None, signals=()):
        lines = lines or {"fe-codex": WORKING, "api-codex": WORKING, "bg-codex": IDLE}
        return Assessment(lines, tuple(signals))

    def wait(self, waiter, target, minutes_ago):
        return tickets.receive(self.g, wait_session(target), sender=waiter, relay_id=next(self.relay_ids),
                               sent_at=at(minutes_ago)).opened

    def ask(self, text=None, sender="fe-codex", minutes_ago=5):
        text = text or (PROTO / "wait-user.txt").read_text(encoding="utf-8")
        return items.receive(self.g, text, sender=sender, relay_id=next(self.relay_ids),
                             received_at=at(minutes_ago)).item

    def forward(self, no, minutes_ago, letter="A"):
        items.answer(self.g, [items.Answer(no, letter, f"{no} {letter}")], answered_at=at(minutes_ago))

    def render(self, assessment=None, relay=None):
        return view.render(self.g, now=NOW, assessment=assessment or self.assessment(), relay=relay)


class PartsTest(unittest.TestCase):
    def test_ago(self):
        cases = {0: "0 分钟前", 59: "59 分钟前", 60: "1 小时前", 119: "1 小时前",
                 23 * 60 + 59: "23 小时前", 25 * 60: "1 天前", 49 * 60: "2 天前"}
        for minutes, want in cases.items():
            with self.subTest(minutes=minutes):
                self.assertEqual(view.ago(NOW, at(minutes)), want)

    def test_clip(self):
        self.assertEqual(view.clip("一" * 30, 30), "一" * 30)
        self.assertEqual(view.clip("一" * 31, 30), "一" * 30 + "…")

    def test_copy_line(self):
        self.assertEqual(view.copy_line(12, "A", "先接微信支付"), "12 A 先接微信支付")
        self.assertEqual(view.copy_line(12, "A", "A 先接微信支付"), "12 A 先接微信支付")
        self.assertEqual(view.copy_line(12, "A", "A：先接微信支付"), "12 A：先接微信支付")
        self.assertEqual(view.copy_line(12, "A", "A:先接"), "12 A:先接")
        self.assertEqual(view.copy_line(12, "A", "Apple 支付"), "12 A Apple 支付")
        self.assertEqual(view.copy_line(12, "A", None), "12 A")
        self.assertEqual(view.copy_line(12, "A", "A"), "12 A")

    def test_copy_line_drops_leading_number(self):
        self.assertEqual(view.copy_line(15, "A", "12 A 先接微信支付"), "15 A 先接微信支付")
        self.assertEqual(view.copy_line(15, "A", "12 先接微信支付"), "15 A 先接微信支付")
        self.assertEqual(view.copy_line(15, "A", "12  A"), "15 A")
        self.assertEqual(view.copy_line(15, "A", "12A 先接"), "15 A 12A 先接")


class EmptyAndHeaderTest(ViewCase):
    def test_empty_state_has_three_parts(self):
        text = self.render()
        self.assertEqual(text, "前端 干活中 · API 干活中 · 后台 已结项（空闲）\n"
                               "等你决定 0 项 · 异常 0\n"
                               "\n"
                               "等待中 0 单 · 已失效 0 项 · 今天已关 0 单")

    def test_lines_row_order_and_blocked_spacing(self):
        lines = {"bg-codex": LineState("blocked", "阻塞：等 API", target="API"),
                 "api-codex": LineState("needs-user", "等你确认"),
                 "fe-codex": LineState("blocked", "阻塞：等你决定 #12", item=12)}
        first = self.render(self.assessment(lines)).split("\n")[0]
        self.assertEqual(first, "前端 阻塞：等你决定 #12 · API 等你确认 · 后台 阻塞：等API")

    def test_needs_user_counts_as_decision(self):
        self.ask()
        lines = {"fe-codex": WORKING, "api-codex": LineState("needs-user", "等你确认"), "bg-codex": IDLE}
        self.assertIn("等你决定 2 项 · 异常 0", self.render(self.assessment(lines)))

    def test_anomaly_count_excludes_signal_1(self):
        signals = [Signal(1, "all-waiting", ("api-codex",), "全线互等"),
                   Signal(4, "offline-backlog", ("api-codex",), "API 掉线，有 2 条消息送不进去")]
        self.assertIn("等你决定 0 项 · 异常 1", self.render(self.assessment(signals=signals)))

    def test_recently_forwarded_window(self):
        recent = self.ask(minutes_ago=30)
        old = self.ask(minutes_ago=30, sender="api-codex")
        multi = self.ask((PROTO / "wait-user-multiline.txt").read_text(encoding="utf-8"), sender="coord",
                         minutes_ago=30)
        self.forward(old, 11)
        self.forward(multi, 10)
        self.forward(recent, 2)
        overview = self.render().split("\n")[1]
        self.assertEqual(overview, f"等你决定 0 项 · 异常 0 · 刚转达：{multi} → 总协调＋前端＋API、{recent} → 前端")

    def test_footer_counts(self):
        self.wait("fe-codex", "API", 20)
        closed = self.wait("api-codex", "后台", 30)
        tickets.close_by_user(self.g, closed, None, at=at(5))
        gone = self.ask()
        items.receive(self.g, f"【撤回】\n事项：#{gone}\n", sender="fe-codex", relay_id=900, received_at=at(1))
        self.assertTrue(self.render().endswith("等待中 1 单 · 已失效 1 项 · 今天已关 1 单"))


class PushLineTest(ViewCase):
    ALL = (Signal(1, "all-waiting", ("api-codex", "bg-codex", "fe-codex"), "全线互等"),)

    def test_stuck_on_most_waited_session_that_waits_for_nobody(self):
        self.wait("api-codex", "前端", 14)
        self.wait("bg-codex", "前端", 3)
        self.wait("fe-codex", "用户", 1)  # 前端 waits on the user, not on another session
        self.assertTrue(self.render(self.assessment(signals=self.ALL)).startswith("⚠ 全线停住 14 分钟：卡在 前端\n"))

    def test_waiting_target_is_skipped(self):
        self.wait("api-codex", "前端", 20)
        self.wait("bg-codex", "前端", 3)
        self.wait("fe-codex", "后台", 5)
        self.wait("coord", "API", 5)
        first = self.render(self.assessment(signals=self.ALL)).split("\n")[0]
        self.assertEqual(first, "⚠ 全线停住 20 分钟：卡在哪见 /flow")

    def test_tie_points_to_flow(self):
        self.wait("api-codex", "前端", 8)
        self.wait("coord", "后台", 6)
        first = self.render(self.assessment(signals=self.ALL)).split("\n")[0]
        self.assertEqual(first, "⚠ 全线停住 8 分钟：卡在哪见 /flow")

    def test_no_push_without_signal_1(self):
        self.wait("api-codex", "前端", 14)
        self.assertFalse(self.render().startswith("⚠"))


SINGLE = (PROTO / "wait-user.txt").read_text(encoding="utf-8").replace("你该回：12 A", "你该回：A")
MULTI = (PROTO / "wait-user-multiline.txt").read_text(encoding="utf-8")


def fact(name, since=None, detail=None):
    from decision_inbox.relay import AgentFact
    return AgentFact(name=name, host_app="codex", presence_raw="waiting-approval", presence="needs-user",
                     presence_since=since, unread=0, waiting_count=0, waiting_from=(), waiting_ids=(),
                     waiting_oldest_at=None, last_activity_at=None, wake_bound=None, retired=False,
                     presence_detail=detail)


def snapshot(*facts):
    from decision_inbox.relay import AgentsSnapshot
    return AgentsSnapshot("ok", {f.name: f for f in facts})


def card(text, no):
    """The card whose title starts with `━━ <no> ·`, up to the next blank line."""
    for block in text.split("\n\n"):
        if block.startswith(f"━━ {no} ·"):
            return block
    raise AssertionError(f"no card #{no} in:\n{text}")


class NeedsUserCardTest(ViewCase):
    LINES = {"fe-codex": LineState("needs-user", "等你确认"), "api-codex": WORKING, "bg-codex": IDLE}

    def test_card_first_with_detail_and_time(self):
        self.ask(SINGLE, sender="api-codex")
        text = self.render(self.assessment(self.LINES),
                           snapshot(fact("fe-codex", since=at(14), detail="permission prompt")))
        blocks = text.split("\n\n")
        self.assertEqual(blocks[1], "━━ 去原会话确认 · 前端 · 14 分钟前\n"
                                    "要你做：打开「前端」会话，确认它弹出的请求（permission prompt）")
        self.assertTrue(blocks[2].startswith("━━ "))
        self.assertIn("等你决定 2 项", blocks[0])

    def test_without_detail_or_relay(self):
        text = self.render(self.assessment(self.LINES), snapshot(fact("fe-codex", since=at(3))))
        self.assertIn("━━ 去原会话确认 · 前端 · 3 分钟前\n要你做：打开「前端」会话，确认它弹出的请求\n", text + "\n")
        text = self.render(self.assessment(self.LINES))
        self.assertIn("━━ 去原会话确认 · 前端\n要你做：打开「前端」会话，确认它弹出的请求\n", text + "\n")
        self.assertNotIn("```", text)


class ItemCardTest(ViewCase):
    def test_reply_with_guessed_number(self):
        raw = (PROTO / "wait-user.txt").read_text(encoding="utf-8")  # 你该回：12 A 先接微信支付
        no = self.ask(raw)
        self.assertIn(f"```\n{no} A 先接微信支付\n```", card(self.render(), no))

    def test_recommended_card(self):
        no = self.ask(SINGLE)
        self.assertEqual(card(self.render(), no), "\n".join([
            f"━━ {no} · 前端 · 支付页先接哪种支付方式 · 5 分钟前 · 挡住 1 条线",
            "要你决定：支付页先接哪种支付方式",
            "推荐 A：先接微信支付",
            "  选了会怎样：本周能上线支付页，支付宝下周补",
            "推荐回复（点代码块右上角复制，发给我）：",
            "```",
            f"{no} A 先接微信支付",
            "```",
            "B：先接支付宝",
            "  选了会怎样：要多等三天 API 补签名接口",
            f"  回 {no} B",
            "C：两种一起接",
            "  选了会怎样：提出方未说明后果",
            f"  回 {no} C",
            f"审查：不需审：本会话无审查者 · 详情：{no} 详情",
        ]))

    def test_recommended_moves_first_and_one_code_block(self):
        text = SINGLE.replace("推荐 A：先接微信支付", "A：先接微信支付").replace("B. 先接支付宝", "推荐 B：先接支付宝")
        no = self.ask(text.replace("你该回：A 先接微信支付", "你该回：B"))
        c = card(self.render(), no)
        self.assertTrue(c.split("\n")[2].startswith("推荐 B：先接支付宝"))
        self.assertEqual(c.count("```"), 2)
        self.assertIn(f"```\n{no} B\n```", c)
        self.assertIn(f"A：先接微信支付\n  选了会怎样：本周能上线支付页，支付宝下周补\n  回 {no} A", c)

    def test_no_recommendation(self):
        text = SINGLE.replace("推荐 A：", "A：").replace("你该回：A 先接微信支付\n", "")
        no = self.ask(text)
        c = card(self.render(), no)
        self.assertNotIn("```", c)
        self.assertNotIn("推荐", c)  # no 「推荐回复」 line either
        self.assertIn(f"A：先接微信支付\n  选了会怎样：本周能上线支付页，支付宝下周补\n  回 {no} A", c)

    def test_long_option_shown_whole_topic_clipped(self):
        """e2e-round1-fixes F12: a clipped option like `{"name":"d…` cannot be told apart."""
        long_option = "一" * 31
        long_topic = "二" * 21
        text = (SINGLE.replace("B. 先接支付宝", f"B. {long_option}")
                .replace("要你决定：支付页先接哪种支付方式", f"要你决定：{long_topic}")
                .replace("是否完全停住：是", "是否完全停住：否"))
        no = self.ask(text, minutes_ago=90)
        c = card(self.render(), no)
        self.assertEqual(c.split("\n")[0], f"━━ {no} · 前端 · {'二' * 20}… · 1 小时前")
        self.assertIn(f"B：{'一' * 31}\n", c)
        self.assertNotIn("挡住", c)

    def test_combined_reply_for_several_recommended(self):
        """relay-checkpoint-authority R4: one copy block answers every recommended card at once."""
        stopped = self.ask(SINGLE, minutes_ago=3)
        loose = self.ask(SINGLE.replace("是否完全停住：是", "是否完全停住：否"), sender="api-codex", minutes_ago=50)
        plain = self.ask(SINGLE.replace("推荐 A：", "A：").replace("你该回：A 先接微信支付\n", "")
                         .replace("【等待用户】", f"【等待用户】【与 #{stopped} 并行】"), minutes_ago=10)
        text = self.render()
        order = sorted((stopped, loose, plain), key=lambda no: text.index(f"━━ {no} ·"))
        recommended = [no for no in order if no != plain]
        block = (f"一次答完（全按推荐）：\n```\n{'，'.join(f'{no} A' for no in recommended)}\n```\n"
                 f"#{plain} 没有推荐，要单独回")
        self.assertIn(block, text)
        self.assertLess(text.index(f"━━ {order[-1]} ·"), text.index("一次答完"))
        self.assertLess(text.index("一次答完"), text.index("等待中 "))

    def test_no_combined_reply_for_one(self):
        self.ask(SINGLE)
        self.ask(SINGLE.replace("推荐 A：", "A：").replace("你该回：A 先接微信支付\n", ""))
        self.assertNotIn("一次答完", self.render())

    def test_multiline_source(self):
        no = self.ask(MULTI, sender="coord")
        self.assertIn(f"━━ {no} · 多线：前端＋API · 订单状态字段统一用哪套命名 · 5 分钟前 · 挡住 2 条线", self.render())

    def test_order_follows_pending(self):
        loose = self.ask(SINGLE.replace("是否完全停住：是", "是否完全停住：否"), minutes_ago=50)
        stopped = self.ask(SINGLE, sender="api-codex", minutes_ago=3)
        text = self.render()
        self.assertLess(text.index(f"━━ {stopped} ·"), text.index(f"━━ {loose} ·"))


class ReviewLineTest(ViewCase):
    def register(self):
        from decision_inbox import reviews
        with self.g.transaction() as tx:
            tx.add_session({"relayName": "fe-owner", "shortName": "前端负责人", "role": "owner",
                            "line": ["前端"], "host": "claude-desktop"})
        reviews.register(self.g, session="fe-codex", reviewer="fe-owner", nodes=("spec",),
                         approval_item=None, approval_note="接入时用户确认", at=at(60))

    def test_in_review_is_bold(self):
        self.register()
        no = self.ask(SINGLE.replace("要点：", "架构审查：进行中，请勿先批\n要点："))
        self.assertIn(f"审查：**审查中，请勿先批** · 详情：{no} 详情", card(self.render(), no))

    def test_unmarked_lists_mentions(self):
        self.register()
        no = self.ask(SINGLE.replace("要点：", "要点：架构师说审查还没做完。"))
        c = card(self.render(), no)
        self.assertTrue(c.endswith(f"审查：⚠ 未标审查 · 详情：{no} 详情\n"
                                   "  正文提到：架构师说审查还没做完。Mock 已就绪，两种方式工作量差一倍。"))

    def test_old_record_without_mentions(self):
        self.register()
        no = self.ask(SINGLE.replace("要点：", "要点：审查没做。"))
        with self.g.transaction() as tx:
            doc = tx.read_state("items")
            del doc["items"][str(no)]["review"]["mentions"]
            tx.write_state("items", doc)
        self.assertTrue(card(self.render(), no).endswith(f"审查：⚠ 未标审查 · 详情：{no} 详情"))


SPEC = Path(__file__).resolve().parent.parent / "spec" / "hub-view.md"


def spec_sample() -> str:
    """The 主视图样例 block of the spec, with its code-block placeholder made a real code block.

    e2e-round1-fixes F12 reworks hub-view (the accepted spec stays as written): the copy block
    now has a 「推荐回复」 line above it.
    """
    text = SPEC.read_text(encoding="utf-8")
    body = text.split("## 主视图样例", 1)[1].split("```text\n", 1)[1].split("\n```", 1)[0]
    return body.replace("（下面是代码块，代码块里只有一行：12 A 先接微信支付）",
                        f"{view.COPY_LABEL}\n```\n12 A 先接微信支付\n```")


class AnomalyTest(ViewCase):
    def test_each_signal_row(self):
        signals = [
            Signal(2, "delivered-not-picked", ("api-codex", "fe-codex"), "交付了没人接：前端 已发消息给 API，API 还没去取（API 在等 前端）"),
            Signal(3, "silent-stop", ("fe-codex",), "前端 停住 2 小时：当前模块 pay 还有 3 项没勾，也没在等任何人"),
            Signal(4, "offline-backlog", ("api-codex",), "API 掉线，有 2 条消息送不进去"),
            Signal(5, "busy-backlog", ("bg-codex",), "后台 已忙 25 分钟，还有 1 条消息在等它"),
            Signal(6, "suspended-blocks", ("fe-codex",), "前端 的 pay 挂起（等设计稿）→ 挡住 1 个：cart"),
            Signal(7, "rework", ("api-codex",), "API 的审查 R3（spec）已来回 4 轮，超过本组常见水平"),
            Signal(8, "slow-progress", ("bg-codex",), "后台 的 jobs 已 3 小时没有新进展，明显慢于平时"),
            Signal(9, "orphan-wait", ("fe-codex",), "前端 的等待单 #31（等 API）还开着，但它后来又开了新的等待 #35"),
            Signal(10, "codex-backlog", ("api-codex",), "API（Codex）没被加载，有 2 条消息积压，最早一条已等 12 分钟"),
        ]
        text = self.render(self.assessment(signals=[Signal(1, "all-waiting", ("fe-codex",), "全线互等")] + signals))
        section = next(b for b in text.split("\n\n") if b.startswith("异常\n"))
        self.assertEqual(section.split("\n"), [
            "异常",
            "- API：交付了没人接——前端 已发消息给 API，API 还没去取。建议：提醒 API 去取前端的交付",
            "- 前端：前端 停住 2 小时：当前模块 pay 还有 3 项没勾，也没在等任何人。建议：问 前端 是否卡住，或让它继续或上抛",
            "- API：API 掉线，有 2 条消息送不进去。建议：打开 API 让它恢复",
            "- 后台：后台 已忙 25 分钟，还有 1 条消息在等它。建议：先等它做完这一轮；要插队就去它的会话说明",
            "- 前端：前端 的 pay 挂起（等设计稿）→ 挡住 1 个：cart。建议：看挂起原因是否已经解决",
            "- API：API 的审查 R3（spec）已来回 4 轮，超过本组常见水平。建议：看一下这次审查的分歧点",
            "- 后台：后台 的 jobs 已 3 小时没有新进展，明显慢于平时。建议：问 后台 进展，或交负责人跟进",
            "- 前端：前端 的等待单 #31（等 API）还开着，但它后来又开了新的等待 #35。建议：确认旧等待是否还需要，不需要就说「关掉 #31」",
            "- API：API（Codex）没被加载，有 2 条消息积压，最早一条已等 12 分钟。建议：在 Codex 里点开 API 让它加载",
        ])
        self.assertNotIn("全线互等", text)
        self.assertIn("异常 9", text)

    def test_no_section_without_anomalies(self):
        self.assertNotIn("异常\n", self.render(self.assessment(signals=[Signal(1, "all-waiting", (), "全线互等")])))


class FullViewTest(ViewCase):
    def build(self):
        self.relay_ids = iter(range(7001, 7100))
        for _ in range(3):
            closed = self.wait("bg-codex", "API", 60)
            tickets.close_by_user(self.g, closed, None, at=at(30))
        with self.g.transaction() as tx:
            while tx.allocate_number() < 8:
                pass
        nine = self.ask(SINGLE, sender="api-codex", minutes_ago=20)
        self.forward(nine, 3)
        with self.g.transaction() as tx:
            tx.allocate_number()
        self.wait("api-codex", "前端", 14)
        text = SINGLE.replace("C、两种一起接\n", "").replace("你该回：A 先接微信支付", "你该回：先接微信支付")
        twelve = self.ask(text, minutes_ago=5)
        self.assertEqual((nine, twelve), (9, 12))
        lines = {"fe-codex": LineState("needs-user", "等你确认"),
                 "api-codex": LineState("blocked", "阻塞：等 前端", target="前端", since=at(14)),
                 "bg-codex": IDLE}
        signals = [Signal(1, "all-waiting", ("api-codex", "bg-codex", "fe-codex"), "全线互等"),
                   Signal(2, "delivered-not-picked", ("api-codex", "fe-codex"),
                          "交付了没人接：前端 已发消息给 API，API 还没去取（API 在等 前端）")]
        relay = snapshot(fact("fe-codex", since=at(14), detail="permission prompt"))
        return self.render(self.assessment(lines, signals), relay)

    def test_matches_spec_sample_exactly(self):
        self.assertMultiLineEqual(self.build(), spec_sample())

    def test_no_relay_ids_or_paths(self):
        import re
        text = self.build()
        for relay_id in range(7001, 7100):
            self.assertIsNone(re.search(rf"(?<!\d){relay_id}(?!\d)", text), relay_id)
        self.assertNotIn("/tmp", text)
        self.assertNotIn(str(store.root_dir()), text)
        self.assertIsNone(re.search(r"(?<![\w/])/[A-Za-z]", text.replace("/flow", "")))


def hhmm(value: str) -> str:
    from datetime import datetime
    return datetime.fromisoformat(value).astimezone().strftime("%H:%M")


class ExpandedViewTest(ViewCase):
    def test_detail(self):
        no = self.ask(MULTI, sender="coord", minutes_ago=30)
        self.forward(no, 2)
        sent_ids = []
        for to in ("coord", "fe-codex", "api-codex"):
            sent_ids.append(next(self.relay_ids))
            items.record_sent(self.g, no, to, sent_ids[-1], at=at(1))
        relay_id = items.get(self.g, no)["relayId"]
        self.assertEqual(view.render_detail(self.g, item=no), "\n".join([
            f"#{no} 详情 · 多线：前端＋API · 收到于 {hhmm(at(30))}",
            f"agent-relay 消息编号：{relay_id}",
            f"答复发送编号：总协调 #{sent_ids[0]}、前端 #{sent_ids[1]}、API #{sent_ids[2]}",
            "各线范围：前端：只改类型定义和展示映射，不改接口调用",
            "各线范围：API：改响应字段名并补兼容期旧字段，兼容期两周",
            "原文：",
            MULTI.rstrip("\n"),
        ]))

    def test_detail_single_and_missing(self):
        no = self.ask(SINGLE, minutes_ago=3)
        text = view.render_detail(self.g, item=no)
        self.assertTrue(text.startswith(f"#{no} 详情 · 前端 · 收到于 {hhmm(at(3))}\nagent-relay 消息编号："))
        self.assertNotIn("各线范围", text)
        self.assertNotIn("答复发送编号", text)
        self.assertTrue(text.endswith("原文：\n" + SINGLE.rstrip("\n")))
        self.assertEqual(view.render_detail(self.g, item=999), "#999 不存在")

    def test_waits(self):
        self.assertEqual(view.render_waits(self.g, now=NOW), "没有开着的等待单")
        fresh = self.wait("fe-codex", "API", 5)
        old = tickets.receive(self.g, (PROTO / "wait-session.txt").read_text(encoding="utf-8"),
                              sender="bg-codex", relay_id=1, sent_at=at(70)).opened
        lines = view.render_waits(self.g, now=NOW).split("\n")
        self.assertEqual(lines, [
            f"#{fresh} 前端 等 API：订单接口 · 已等 5 分钟",
            f"#{old} 后台 等 API：订单接口的 Mock 数据，交付后我才能接着做支付页 · ⚠ 已等 70 分钟 · "
            "可能卡住：后台 在等 API 的「订单接口的 Mock 数据，\n  交付后我才能接着做支付页」，"
            "请看一下 API 是否已完成却没通知 后台".replace("\n  ", ""),
        ])

    def test_closed(self):
        day = view._today(NOW)
        self.assertEqual(view.render_closed(self.g, day=day), f"{day} 没有关闭的等待单")
        first = self.wait("fe-codex", "API", 30)
        tickets.close_by_user(self.g, first, "不等了", at=at(20))
        second = self.wait("api-codex", "后台", 30)
        tickets.close_by_user(self.g, second, None, at=at(10))
        self.assertEqual(view.render_closed(self.g, day=day).split("\n"), [
            f"#{first} 前端 等 API：订单接口 · 用户关闭 · 依据：不等了 · {hhmm(at(20))} 关",
            f"#{second} API 等 后台：订单接口 · 用户关闭 · 依据：用户关闭 · {hhmm(at(10))} 关",
        ])

    def test_invalidated(self):
        self.assertEqual(view.render_invalidated(self.g), "没有失效的事项")
        old = self.ask(SINGLE)
        new = self.ask(SINGLE.replace("【等待用户】", f"【等待用户】【取代 #{old}】"))
        gone = self.ask(SINGLE, sender="api-codex")
        items.receive(self.g, f"【撤回】\n事项：#{gone}\n原因：需求取消\n", sender="api-codex", relay_id=1,
                      received_at=at(1))
        bare = self.ask(MULTI, sender="coord")
        items.receive(self.g, f"【撤回】\n事项：#{bare}\n", sender="coord", relay_id=2, received_at=at(1))
        self.assertEqual(view.render_invalidated(self.g).split("\n"), [
            f"#{old} 已取代（被 #{new} 取代）· 前端 · 支付页先接哪种支付方式",
            f"#{gone} 已撤回（需求取消）· API · 支付页先接哪种支付方式",
            f"#{bare} 已撤回 · 多线：前端＋API · 订单状态字段统一用哪套命名",
        ])


if __name__ == "__main__":
    unittest.main()
