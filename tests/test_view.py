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

    def test_truncate(self):
        self.assertEqual(view.truncate("一" * 30, 30), "一" * 30)
        self.assertEqual(view.truncate("一" * 31, 30), "一" * 30 + "…")

    def test_copy_line(self):
        self.assertEqual(view.copy_line(12, "A", "先接微信支付"), "12 A 先接微信支付")
        self.assertEqual(view.copy_line(12, "A", "A 先接微信支付"), "12 A 先接微信支付")
        self.assertEqual(view.copy_line(12, "A", "A：先接微信支付"), "12 A：先接微信支付")
        self.assertEqual(view.copy_line(12, "A", "A:先接"), "12 A:先接")
        self.assertEqual(view.copy_line(12, "A", "Apple 支付"), "12 A Apple 支付")
        self.assertEqual(view.copy_line(12, "A", None), "12 A")


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


if __name__ == "__main__":
    unittest.main()
