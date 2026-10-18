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

    def test_returned_message_does_not_close(self):
        no = self.receive(wait_session()).opened
        bad_wait_user = SINGLE.replace("结束：无", f"结束：#{no}").replace("要你决定：支付页先接哪种支付方式\n", "")
        r = self.receive(bad_wait_user, relay_id=306)
        self.assertEqual(r.closed, ())
        self.assertIn("missing-field:要你决定", {p.code for p in r.problems})
        bad_wait_session = f"【等待其他会话】\n结束：#{no}\n在等谁：API\n"
        self.assertEqual(self.receive(bad_wait_session, relay_id=307).closed, ())
        self.assertEqual(self.ticket(no)["status"], "open")

    def test_end_line_with_item_number_is_ignored(self):
        item = items.receive(self.g, SINGLE, sender="fe-codex", relay_id=1, received_at=SENT).item
        r = self.receive(f"【已恢复】\n结束：#{item}\n")
        self.assertEqual((r.closed, r.hints), ((), ()))

    def test_end_line_with_own_relay_id(self):
        """e2e-round1-fixes F10: dev-a only knows its own message id #4544, never the ticket number."""
        no = self.receive(wait_session(), relay_id=4544).opened
        other = self.receive(f"【已恢复】\n结束：#4544\n", sender="api-codex", relay_id=4545)
        self.assertEqual(other.closed, ())
        self.assertIn("end-unknown", {h.code for h in other.hints})
        r = self.receive(SINGLE.replace("结束：无", "结束：#4544"), relay_id=4610)
        self.assertEqual(r.closed, (no,))
        self.assertEqual(self.ticket(no)["close"]["basis"], "新消息 #4610")
        self.assertNotIn("end-unknown", {h.code for h in r.hints})

    def test_end_line_matching_nothing_is_reported(self):
        r = self.receive(f"【已恢复】\n结束：#9999\n")
        self.assertEqual(r.closed, ())
        hint = next(h for h in r.hints if h.code == "end-unknown")
        self.assertEqual(hint.text, "#9999 既不是收件枢纽编号，也不是你发过的消息，没有关闭任何东西")

    def test_end_line_with_own_item_relay_id_is_not_unknown(self):
        items.receive(self.g, SINGLE, sender="fe-codex", relay_id=4540, received_at=SENT)
        r = self.receive(f"【已恢复】\n结束：#4540\n")
        self.assertEqual((r.closed, r.hints), ((), ()))

    def test_end_line_naming_an_item_outside_resumed_is_flagged(self):
        """relay-checkpoint-authority F13: 结束 in a new wait does not end an item; say so."""
        item = items.receive(self.g, SINGLE, sender="fe-codex", relay_id=4707, received_at=SENT).item
        for written in (item, 4707):
            r = self.receive(SINGLE.replace("结束：无", f"结束：#{written}"), relay_id=4752 + written)
            hint = next(h for h in r.hints if h.code == "end-is-item")
            self.assertEqual(hint.text, f"#{written} 是待决事项，不是等待记录；结束待决事项要发【已恢复】")
        r = self.receive(wait_session(end=f"#{item}"), relay_id=4800)
        self.assertIn("end-is-item", {h.code for h in r.hints})

    def test_unknown_target(self):
        r = self.receive(wait_session(target="后台老王"))
        self.assertIsNotNone(r.opened)
        self.assertIn("unknown-target", {h.code for h in r.hints})
        self.assertIsNone(self.ticket(r.opened)["targetRelay"])

    def test_target_by_relay_name(self):
        """e2e-round1-fixes F5: dev-a wrote the hub's agent-relay name, not its short name."""
        entry = store.roster(self.g)[0]
        r = self.receive(wait_session(target=entry["relayName"]))
        self.assertNotIn("unknown-target", {h.code for h in r.hints})
        self.assertEqual(self.ticket(r.opened)["targetRelay"], entry["relayName"])

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


def snapshot(state="stopped", count=3, oldest="2026-10-16T04:30:00.000Z"):
    agent = {"name": "api-codex", "host": {"app": "codex", "sessionId": "t", "verified": False},
             "unread": count, "lastActivity": oldest, "presence": {"state": state}, "wake": None}
    if count:
        agent["waiting"] = {"count": count, "from": ["fe-codex"], "ids": [1], "oldestAt": oldest}
    import json
    return relay.parse_agents(json.dumps({"count": 1, "agents": [agent]}))


class MarksTest(TicketsCase):
    def view(self, now, relay_snapshot=None):
        views = tickets.open_tickets(self.g, now=now, relay=relay_snapshot)
        self.assertEqual(len(views), 1)
        return views[0]

    def test_age_marks_use_sent_time(self):
        self.receive(wait_session(), sent_at=SENT)
        self.assertEqual(self.view("2026-10-16T05:14:59Z").marks, ())
        v = self.view("2026-10-16T13:15:00+08:00")
        self.assertEqual((v.minutes, v.marks), (15, ("waited",)))
        self.assertIn("⚠ 已等 15 分钟", v.notes)
        v = self.view("2026-10-16T06:00:00Z")
        self.assertEqual(v.marks, ("waited", "maybe-stuck"))
        self.assertTrue(any("前端 在等 API" in n for n in v.notes))

    def test_offline_is_immediate(self):
        self.receive(wait_session(), sent_at=SENT)
        v = self.view("2026-10-16T05:01:00Z", snapshot())
        self.assertEqual(v.marks, ("offline",))
        note = [n for n in v.notes if "离线" in n][0]
        self.assertIn("3 条", note)
        self.assertIn("12:30", note)
        self.assertEqual(self.view("2026-10-16T05:01:00Z").marks, ())
        self.assertEqual(self.view("2026-10-16T05:01:00Z", snapshot(state="running")).marks, ())
        self.assertEqual(self.view("2026-10-16T05:01:00Z", snapshot(state="unreachable")).marks, ("offline",))

    def test_unknown_target_never_offline(self):
        self.receive(wait_session(target="后台老王"), sent_at=SENT)
        self.assertEqual(self.view("2026-10-16T05:01:00Z", snapshot()).marks, ())

    def test_closed_tickets_are_not_listed(self):
        no = self.receive(wait_session()).opened
        tickets.close_by_user(self.g, ticket=no, reason=None, at=SENT)
        self.assertEqual(tickets.open_tickets(self.g, now=SENT), [])


class ClosedTodayTest(TicketsCase):
    def test_closed_on_local_day_and_counts(self):
        a = self.receive(wait_session(), relay_id=1).opened
        b = self.receive(wait_session(what="二"), relay_id=2).opened
        c = self.receive(wait_session(what="三"), relay_id=3).opened
        self.receive(wait_session(what="四"), relay_id=4)
        # 2026-10-15T16:30Z is already 2026-10-16 00:30 in Asia/Shanghai
        tickets.close_by_user(self.g, ticket=a, reason=None, at="2026-10-15T16:30:00Z")
        tickets.close_by_user(self.g, ticket=b, reason="不等了", at="2026-10-16T08:00:00+08:00")
        tickets.close_by_user(self.g, ticket=c, reason=None, at="2026-10-15T15:59:00Z")  # 10-15 23:59 local
        today = tickets.closed_on(self.g, day="2026-10-16")
        self.assertEqual(sorted(t["no"] for t in today), [a, b])
        self.assertEqual([t["close"]["basis"] for t in today if t["no"] == b], ["不等了"])
        self.assertEqual(tickets.counts(self.g, day="2026-10-16"), {"open": 1, "closed_today": 2})
        self.assertEqual(len(store.read_state(self.g, "tickets")["tickets"]), 4)

    def test_consistency(self):
        no = self.receive(wait_session()).opened
        self.receive(f"【已恢复】\n结束：#{no}\n", relay_id=9)
        self.assertEqual(store.check(self.g)["problems"], [])
        self.assertEqual([e["type"] for e in store.read_events(self.g, ref=no)], ["tickets.opened", "tickets.closed"])


if __name__ == "__main__":
    unittest.main()
