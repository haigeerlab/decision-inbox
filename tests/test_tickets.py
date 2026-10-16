import os
import time
import unittest
from pathlib import Path

from helpers import TempHomeTestCase

from decision_inbox import items, relay, store, tickets

PROTO = Path(__file__).resolve().parent / "fixtures" / "protocol"
RELAY = Path(__file__).resolve().parent / "fixtures" / "relay"
SINGLE = (PROTO / "wait-user.txt").read_text(encoding="utf-8")

# 2026-10-16 13:00 in Asia/Shanghai
SENT = "2026-10-16T05:00:00Z"


def wait_session(target="API", what="订单接口的 Mock 数据", end="无"):
    return f"【等待其他会话】\n结束：{end}\n在等谁：{target}\n等什么：{what}\n"


class TicketsCase(TempHomeTestCase):
    def setUp(self):
        super().setUp()
        self._tz = os.environ.get("TZ")
        os.environ["TZ"] = "Asia/Shanghai"
        time.tzset()
        self.g, _ = store.init_group("demo")
        people = [
            ("hub", "收件枢纽", "hub", [], "claude-desktop", None),
            ("fe-codex", "前端", "dev", ["前端"], "codex-desktop", "/tmp/fe"),
            ("api-codex", "API", "dev", ["API"], "codex-desktop", "/tmp/api"),
        ]
        with self.g.transaction() as tx:
            for relay_name, short, role, line, host, repo in people:
                entry = {"relayName": relay_name, "shortName": short, "role": role, "line": line, "host": host}
                if repo:
                    entry["repo"] = repo
                tx.add_session(entry)

    def tearDown(self):
        if self._tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = self._tz
        time.tzset()
        super().tearDown()

    def receive(self, text, sender="fe-codex", relay_id=300, sent_at=SENT):
        return tickets.receive(self.g, text, sender=sender, relay_id=relay_id, sent_at=sent_at)

    def ticket(self, no):
        return store.read_state(self.g, "tickets")["tickets"][str(no)]


class OpenAndCloseTest(TicketsCase):
    def test_open(self):
        r = self.receive(wait_session())
        self.assertTrue(r.handled)
        t = self.ticket(r.opened)
        self.assertEqual((t["waiter"], t["target"], t["targetRelay"], t["what"], t["sentAt"], t["relayId"],
                          t["status"]), ("fe-codex", "API", "api-codex", "订单接口的 Mock 数据", SENT, 300, "open"))
        self.assertEqual(store.read_events(self.g, ref=r.opened)[-1]["type"], "tickets.opened")

    def test_invalid_not_opened(self):
        r = self.receive("【等待其他会话】\n结束：无\n在等谁：API\n")
        self.assertIsNone(r.opened)
        self.assertIn("missing-field:等什么", {p.code for p in r.problems})
        self.assertEqual(store.read_state(self.g, "tickets").get("tickets", {}), {})

    def test_reason_1_resumed(self):
        no = self.receive(wait_session()).opened
        other = self.receive(f"【已恢复】\n结束：#{no}\n", sender="api-codex", relay_id=301)
        self.assertEqual(other.closed, ())
        self.assertIn("not-own-ticket", {h.code for h in other.hints})
        r = self.receive(f"【已恢复】\n结束：#{no}\n", relay_id=302)
        self.assertEqual(r.closed, (no,))
        close = self.ticket(no)["close"]
        self.assertEqual((close["reason"], close["basis"]), (1, "【已恢复】#302"))

    def test_reason_2_superseded(self):
        no = self.receive(wait_session()).opened
        kept = self.receive(wait_session(what="另一件事"), relay_id=303)
        self.assertEqual(self.ticket(no)["status"], "open")
        r = self.receive(wait_session(what="Mock 改成真接口", end=f"#{no}"), relay_id=304)
        self.assertEqual(r.closed, (no,))
        self.assertIsNotNone(r.opened)
        self.assertEqual((self.ticket(no)["close"]["reason"], self.ticket(no)["close"]["basis"]), (2, "新消息 #304"))
        r = self.receive(SINGLE.replace("结束：无", f"结束：#{kept.opened}"), relay_id=305)
        self.assertTrue(r.handled)
        self.assertIsNone(r.opened)
        self.assertEqual(r.closed, (kept.opened,))

    def test_end_line_with_item_number_is_ignored(self):
        item = items.receive(self.g, SINGLE, sender="fe-codex", relay_id=1, received_at=SENT).item
        r = self.receive(f"【已恢复】\n结束：#{item}\n")
        self.assertEqual((r.closed, r.hints), ((), ()))

    def test_unknown_target(self):
        r = self.receive(wait_session(target="后台老王"))
        self.assertIsNotNone(r.opened)
        self.assertIn("unknown-target", {h.code for h in r.hints})
        self.assertIsNone(self.ticket(r.opened)["targetRelay"])

    def test_other_kinds_not_handled(self):
        self.assertFalse(self.receive("【撤回】\n事项：#3\n").handled)


class ReasonThreeFourTest(TicketsCase):
    def test_reason_3_after_answer_is_sent(self):
        item = items.receive(self.g, SINGLE, sender="fe-codex", relay_id=1, received_at=SENT).item
        no = self.receive(wait_session(target="用户", what=f"#{item} 的答复")).opened
        other = self.receive(wait_session(target="API", what=f"#{item} 的答复"), relay_id=301).opened
        self.assertEqual(tickets.close_answered(self.g, at="2026-10-16T05:10:00Z"), ())
        items.answer(self.g, items.interpret_reply(self.g, f"{item} A").answers, answered_at="2026-10-16T05:20:00Z")
        self.assertEqual(tickets.close_answered(self.g, at="2026-10-16T05:21:00Z"), ())  # not sent yet
        items.record_sent(self.g, item=item, to="fe-codex", relay_id=2950, at="2026-10-16T05:22:00Z")
        self.assertEqual(tickets.close_answered(self.g, at="2026-10-16T05:23:00Z"), (no,))
        close = self.ticket(no)["close"]
        self.assertEqual((close["reason"], close["basis"]), (3, "已转发 #2950"))
        self.assertEqual(self.ticket(other)["status"], "open")

    def test_reason_3_needs_own_item(self):
        item = items.receive(self.g, SINGLE, sender="api-codex", relay_id=1, received_at=SENT).item
        no = self.receive(wait_session(target="收件枢纽", what=f"#{item} 的答复")).opened
        items.answer(self.g, items.interpret_reply(self.g, f"{item} A").answers, answered_at=SENT)
        items.record_sent(self.g, item=item, to="api-codex", relay_id=2951, at=SENT)
        self.assertEqual(tickets.close_answered(self.g, at=SENT), ())
        self.assertEqual(self.ticket(no)["status"], "open")

    def test_reason_4_user(self):
        a = self.receive(wait_session()).opened
        b = self.receive(wait_session(what="别的"), relay_id=301).opened
        tickets.close_by_user(self.g, ticket=a, reason=None, at=SENT)
        tickets.close_by_user(self.g, ticket=b, reason="需求已取消", at=SENT)
        self.assertEqual((self.ticket(a)["close"]["reason"], self.ticket(a)["close"]["basis"]), (4, "用户关闭"))
        self.assertEqual(self.ticket(b)["close"]["basis"], "需求已取消")
        for bad in (a, 999):
            with self.subTest(ticket=bad):
                with self.assertRaises(ValueError):
                    tickets.close_by_user(self.g, ticket=bad, reason=None, at=SENT)


if __name__ == "__main__":
    unittest.main()
