import os
import time
from pathlib import Path

from helpers import TempHomeTestCase

from decision_inbox import hub, install, items, relay, reviews, store

PROTO = Path(__file__).resolve().parent / "fixtures" / "protocol"
WAIT_USER = (PROTO / "wait-user.txt").read_text(encoding="utf-8")
MULTI = (PROTO / "wait-user-multiline.txt").read_text(encoding="utf-8")
NOW = "2026-10-16T05:30:00Z"
SENT = "2026-10-16T05:00:00.000Z"


def message(mid, sender, body, created=SENT, truncated=False):
    return relay.InboxMessage(id=mid, sender=sender, body=body, created_at=created, reply_to=None,
                              expects_reply=False, truncated=truncated, next_offset=20 if truncated else None)


def inbox(*messages, more=False):
    return relay.Inbox(agent="di-hub", messages=tuple(messages), has_more=more)


def wait_session(target="前端", what="订单接口的 Mock 数据", end="无"):
    return f"【等待其他会话】\n结束：{end}\n在等谁：{target}\n等什么：{what}\n"


def conclusion(verdict="通过", submitter="前端"):
    return f"【审查结论】\n审查编号：R-1\n节点：Spec\n送审方：{submitter}\n结论：{verdict}\n"


class HubCase(TempHomeTestCase):
    def setUp(self):
        super().setUp()
        self._tz = os.environ.get("TZ")
        os.environ["TZ"] = "Asia/Shanghai"
        time.tzset()
        self.g, _ = store.init_group("demo")
        people = [
            ("di-hub", "收件枢纽", "hub", [], "claude-desktop"),
            ("fe-codex", "前端", "dev", ["前端"], "codex-desktop"),
            ("api-codex", "API", "dev", ["API"], "codex-desktop"),
            ("fe-owner", "前端负责人", "owner", ["前端"], "claude-desktop"),
            ("coord", "总协调", "coordinator", [], "codex-desktop"),
        ]
        with self.g.transaction() as tx:
            for name, short, role, line, host in people:
                entry = {"relayName": name, "shortName": short, "role": role, "line": line, "host": host}
                if role == "dev":
                    entry["repo"] = f"/tmp/{name}"
                tx.add_session(entry)
        reviews.register(self.g, "fe-codex", "fe-owner", ("spec",), None, "用户 2026-10-16 批准", at=SENT)

    def tearDown(self):
        if self._tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = self._tz
        time.tzset()
        super().tearDown()

    def receive(self, *messages, more=False):
        return hub.receive(self.g, inbox(*messages, more=more), now=NOW)

    def tickets(self):
        return store.read_state(self.g, "tickets").get("tickets", {})


class ReceiveDispatchTest(HubCase):
    def test_one_of_each_kind(self):
        r = self.receive(
            message(1001, "fe-codex", WAIT_USER),
            message(1002, "api-codex", "【等待用户】\n结束：无\n来自：API\n"),
            message(1003, "api-codex", wait_session()),
            message(1004, "api-codex", "【已恢复】\n结束：#2\n"),
            message(1005, "fe-owner", conclusion()),
            message(1006, "fe-codex", "随便说一句\n第二行"),
            message(1007, "bridge", "Message #990 to api-codex failed.\nmore"),
        )
        self.assertEqual(r.ack, [1001, 1002, 1003, 1004, 1005, 1006, 1007])
        self.assertEqual([it["no"] for it in items.pending(self.g)], [1])
        self.assertEqual(items.get(self.g, 1)["receivedAt"], SENT)
        ticket = self.tickets()["2"]
        self.assertEqual((ticket["waiter"], ticket["sentAt"], ticket["status"]), ("api-codex", SENT, "closed"))
        self.assertEqual(ticket["close"]["reason"], 1)
        review = store.read_state(self.g, "reviews")["reviews"]["R-1"]
        self.assertEqual(len(review["rounds"]), 1)
        self.assertEqual(len(r.sends), 1)
        send = r.sends[0]
        self.assertEqual((send["id"], send["to"], send["replyTo"], send["kind"]), ("out:1", "api-codex", 1002, "return"))
        body = Path(send["bodyFile"]).read_text(encoding="utf-8")
        self.assertTrue(body.startswith("退回：你的【等待用户】没有收进待答表"))
        self.assertIn("前端 称：随便说一句（说「1006 原文」看全文）", r.notes)
        self.assertIn("agent-relay 通知：Message #990 to api-codex failed.", r.notes)

    def test_user_reply_from_a_session_is_not_handled(self):
        r = self.receive(message(1010, "fe-codex", "【用户答复】\n事项：#1\n用户原话：1 A\n答复时间：现在\n"))
        self.assertEqual(r.notes, ["前端 发来一条【用户答复】，收件枢纽不处理"])
        self.assertEqual((r.sends, r.ack), ([], [1010]))

    def test_unregistered_reviewer_conclusion_is_returned(self):
        r = self.receive(message(1011, "api-codex", conclusion()))
        self.assertEqual(r.sends[0]["to"], "api-codex")
        body = Path(r.sends[0]["bodyFile"]).read_text(encoding="utf-8")
        self.assertTrue(body.startswith("退回：你的【审查结论】没有处理"))
        self.assertIn("不是 前端 登记的审查者", body)

    def test_wait_session_missing_field_is_returned_without_ticket(self):
        r = self.receive(message(1012, "api-codex", "【等待其他会话】\n结束：无\n在等谁：前端\n"))
        self.assertEqual(self.tickets(), {})
        body = Path(r.sends[0]["bodyFile"]).read_text(encoding="utf-8")
        self.assertTrue(body.startswith("退回：你的【等待其他会话】没有处理"))
        self.assertIn("等什么", body)
        self.assertEqual(r.sends[0]["replyTo"], 1012)

    def test_end_line_of_wait_user_closes_old_ticket(self):
        self.receive(message(1013, "fe-codex", wait_session(target="API")))
        r = self.receive(message(1014, "fe-codex", WAIT_USER.replace("结束：无", "结束：#1")))
        self.assertEqual([it["no"] for it in items.pending(self.g)], [2])
        self.assertEqual(self.tickets()["1"]["close"]["reason"], 2)
        self.assertEqual(r.sends, [])

    def test_resumed_ends_answered_item(self):
        self.receive(message(1015, "fe-codex", WAIT_USER))
        items.answer(self.g, items.interpret_reply(self.g, "1 A").answers, answered_at=NOW)
        self.receive(message(1016, "fe-codex", "【已恢复】\n结束：#1\n"))
        self.assertEqual(items.get(self.g, 1)["status"], "closed")

    def test_same_hint_told_once(self):
        r = self.receive(message(1018, "fe-codex", WAIT_USER))
        self.assertEqual(r.notes, ["前端：选项 C 没写「选了会怎样」"])

    def test_hints_are_told_to_the_user(self):
        r = self.receive(message(1017, "api-codex", wait_session(target="后台")))
        self.assertEqual(len(r.notes), 1)
        self.assertTrue(r.notes[0].startswith("API："))
        self.assertIn("后台 不在会话名册里", r.notes[0])


class ReceiveOnceTest(HubCase):
    def batch(self):
        return (message(1101, "fe-codex", WAIT_USER), message(1102, "api-codex", "【等待用户】\n结束：无\n"),
                message(1103, "api-codex", wait_session()))

    def test_same_batch_twice(self):
        first = self.receive(*self.batch())
        counter = (self.g.path / "counter.json").read_text(encoding="utf-8")
        second = self.receive(*self.batch())
        self.assertEqual(len(first.sends), 1)
        self.assertEqual(second.sends, [])
        self.assertEqual(second.notes, [])
        self.assertEqual(second.ack, [1101, 1102, 1103])
        self.assertEqual((self.g.path / "counter.json").read_text(encoding="utf-8"), counter)
        self.assertEqual(len(items.pending(self.g)), 1)

    def test_truncated_body_is_left_unread(self):
        r = self.receive(message(1104, "fe-codex", WAIT_USER[:20], truncated=True), message(1105, "api-codex", wait_session()))
        self.assertEqual(r.ack, [1105])
        self.assertEqual(r.unread, [1104])
        self.assertEqual(items.pending(self.g), [])
        self.assertTrue(any("1104" in n and "maxChars" in n for n in r.notes))
        again = self.receive(message(1104, "fe-codex", WAIT_USER))
        self.assertEqual(again.ack, [1104])
        self.assertEqual(len(items.pending(self.g)), 1)

    def test_more_pages(self):
        r = self.receive(message(1106, "api-codex", wait_session()), more=True)
        self.assertTrue(r.more)
        self.assertTrue(any("再读一页" in n for n in r.notes))

    def test_missing_created_at_uses_now(self):
        self.receive(message(1107, "fe-codex", WAIT_USER, created=None))
        self.assertEqual(items.get(self.g, 1)["receivedAt"], NOW)

    def test_hub_domain_written_with_event(self):
        self.receive(message(1108, "api-codex", wait_session()))
        state = store.read_state(self.g, "hub")
        self.assertEqual(state["received"]["1108"]["kind"], "wait-session")
        types = [e["type"] for e in store.read_events(self.g)]
        self.assertIn("hub.received", types)
        self.assertEqual(store.check(self.g)["problems"], [])


class SentTest(HubCase):
    def answered(self):
        """Item #1 answered 「1 A」 and a ticket waiting on that answer (#2)."""
        self.receive(message(1201, "fe-codex", WAIT_USER))
        self.receive(message(1202, "fe-codex", wait_session(target="用户", what="#1 的答复")))
        outs = items.answer(self.g, items.interpret_reply(self.g, "1 A").answers, answered_at=NOW)
        return hub._queue_answers(self.g, outs, now=NOW)

    def test_answer_queued_with_reply_to(self):
        sends = self.answered()
        self.assertEqual([(s["id"], s["to"], s["replyTo"], s["kind"]) for s in sends],
                         [("out:1", "fe-codex", 1201, "answer")])
        self.assertIn("用户原话：1 A", Path(sends[0]["bodyFile"]).read_text(encoding="utf-8"))

    def test_sent_records_relay_id_closes_ticket_and_keeps_body(self):
        sends = self.answered()
        closed = hub.sent(self.g, done={"out:1": 3950}, failed=[], at=NOW)
        self.assertEqual(closed, (2,))
        self.assertEqual(items.get(self.g, 1)["sent"][0]["relayId"], 3950)
        self.assertEqual(self.tickets()["2"]["close"], {"reason": 3, "basis": "已转发 #3950", "at": NOW})
        self.assertTrue(Path(sends[0]["bodyFile"]).exists())
        self.assertEqual(hub.outgoing(self.g), [])

    def test_failed_and_unrecorded_stay(self):
        self.answered()
        self.receive(message(1203, "api-codex", "【等待用户】\n结束：无\n"))
        hub.sent(self.g, done={}, failed=["out:1"], at=NOW)
        left = hub.outgoing(self.g)
        self.assertEqual([s["id"] for s in left], ["out:1", "out:2"])
        self.assertTrue(all(Path(s["bodyFile"]).exists() for s in left))
        self.assertEqual(self.tickets()["2"]["status"], "open")
        state = store.read_state(self.g, "hub")["outgoing"]
        self.assertTrue(state["out:1"]["failed"])
        hub.sent(self.g, done={"out:1": 3951}, failed=[], at=NOW)
        self.assertEqual([s["id"] for s in hub.outgoing(self.g)], ["out:2"])

    def test_unknown_or_already_sent_id_rejected(self):
        self.answered()
        with self.assertRaises(hub.UnknownOutgoing):
            hub.sent(self.g, done={"out:9": 1}, failed=[], at=NOW)
        hub.sent(self.g, done={"out:1": 3950}, failed=[], at=NOW)
        with self.assertRaises(hub.UnknownOutgoing):
            hub.sent(self.g, done={}, failed=["out:1"], at=NOW)

    def test_return_send_does_not_touch_items(self):
        r = self.receive(message(1204, "api-codex", "【等待用户】\n结束：无\n"))
        hub.sent(self.g, done={"out:1": 3960}, failed=[], at=NOW)
        self.assertEqual(store.read_state(self.g, "hub")["outgoing"]["out:1"]["relayId"], 3960)
        self.assertTrue(Path(r.sends[0]["bodyFile"]).exists())


class ReplyTest(HubCase):
    def setUp(self):
        super().setUp()
        self.receive(message(1301, "fe-codex", WAIT_USER))                                    # item #1
        self.receive(message(1302, "api-codex", wait_session(target="前端")))                 # ticket #2

    def reply(self, text):
        return hub.reply(self.g, text, now=NOW)

    def bodies(self, r):
        return [Path(s["bodyFile"]).read_text(encoding="utf-8") for s in r.sends]

    def test_letter_answer(self):
        r = self.reply("1 B")
        self.assertEqual([(s["to"], s["replyTo"], s["kind"]) for s in r.sends], [("fe-codex", 1301, "answer")])
        self.assertIn("用户原话：1 B", self.bodies(r)[0])
        self.assertEqual(items.get(self.g, 1)["status"], "forwarded")
        self.assertIn("已转达：#1 → 前端", r.show)
        self.assertNotIn("没发出去", r.show)
        self.assertIn("等你决定 0 项", r.show)

    def test_multiline_answer_goes_to_each_line(self):
        self.receive(message(1303, "coord", MULTI))                                          # item #3
        r = self.reply("3 A")
        self.assertEqual([(s["to"], s["replyTo"]) for s in r.sends],
                         [("coord", 1303), ("fe-codex", None), ("api-codex", None)])
        self.assertIn("适用于你的范围：只改类型定义和展示映射", self.bodies(r)[1])

    def test_unmatched_reply_asks_and_sends_nothing(self):
        r = self.reply("1 D")
        self.assertEqual(r.sends, [])
        self.assertEqual(r.show, "#1 没有选项 D，请确认。")
        self.assertEqual(items.get(self.g, 1)["status"], "pending")

    def test_original_words_kept_exactly(self):
        words = "1 A，但「支付页」先别上线；\n上线前再问我 \"一次\""
        r = self.reply(words)
        self.assertIn(f"用户原话：{words}", self.bodies(r)[0])

    def test_views(self):
        self.assertTrue(self.reply("1 详情").show.startswith("#1 详情 · 前端"))
        self.assertTrue(self.reply("#1 详情").show.startswith("#1 详情"))
        self.assertTrue(self.reply("看等待").show.startswith("#2 API 等 前端"))
        self.assertEqual(self.reply("看已关闭").show, "2026-10-16 没有关闭的等待单")
        self.assertEqual(self.reply("看已关闭 2026-10-15").show, "2026-10-15 没有关闭的等待单")
        self.assertEqual(self.reply("看失效").show, "没有失效的事项")

    def test_original_of_unknown_message(self):
        self.receive(message(1304, "fe-codex", "随便说一句\n第二行"))
        self.assertEqual(self.reply("1304 原文").show, "前端 发来的 #1304 原文：\n随便说一句\n第二行")
        self.assertEqual(self.reply("1301 原文").show, "没有记下 #1301 这条消息的原文（只记认不出类型的消息）")

    def test_close_ticket(self):
        r = self.reply("关掉 #2 已经不需要")
        self.assertTrue(r.show.startswith("已关掉 #2（已经不需要）"))
        self.assertEqual(self.tickets()["2"]["close"]["basis"], "已经不需要")
        self.assertEqual(r.sends, [])

    def test_close_several_without_reason(self):
        self.receive(message(1305, "api-codex", wait_session(target="收件枢纽", what="别的")))   # ticket #3
        r = self.reply("关掉 #2、#3")
        self.assertTrue(r.show.startswith("已关掉 #2、#3（用户关闭）"))

    def test_close_item_or_closed_ticket_is_a_question(self):
        r = self.reply("关掉 #1")
        self.assertEqual(r.show, "#1 是事项，不是等待单；要放弃事项请让提出方发【撤回】")
        self.reply("关掉 #2")
        self.assertEqual(self.reply("关掉 #2、#9").show, "#2 不是开着的等待单，请确认编号")
        self.assertEqual(self.tickets()["2"]["status"], "closed")

    def test_close_checks_all_before_closing_any(self):
        self.reply("关掉 #2、#1")
        self.assertEqual(self.tickets()["2"]["status"], "open")

    def test_resend(self):
        self.assertEqual(self.reply("重发").show, "没有没发出去的消息")
        self.reply("1 A")
        hub.sent(self.g, done={}, failed=["out:1"], at=NOW)
        r = self.reply("重发")
        self.assertEqual([s["id"] for s in r.sends], ["out:1"])
        self.assertEqual(r.show, "重新列出 1 条没发出去的消息")

    def test_main_view_warns_unsent_and_unreadable_relay(self):
        self.reply("1 A")
        text = hub.main_view(self.g, now=NOW, relay=None)
        lines = text.split("\n")
        self.assertEqual(lines[0], "⚠ 有 1 条消息没发出去，说「重发」再试")
        self.assertEqual(lines[1], "⚠ 读不到 agent-relay，各线状态不全")


class ConventionTest(HubCase):
    def test_block(self):
        text = hub.convention("demo", cli="python3 -m decision_inbox", workdir="/abs/io")
        lines = text.strip().split("\n")
        self.assertEqual(lines[0], "<!-- BEGIN decision-inbox hub -->")
        self.assertEqual(lines[-1], "<!-- END decision-inbox hub -->")
        for needle in ("协作组「demo」",
                       "bridge_inbox", "python3 -m decision_inbox inbox receive demo --inbox /abs/io/inbox.json",
                       "bodyFile", "replyTo", "inbox sent demo", "bridge_ack",
                       "python3 -m decision_inbox view demo --agents /abs/io/agents.json --outbox /abs/io/outbox.json",
                       "bridge_agents", "/abs/io/said.txt", "includeAcknowledged: true",
                       "python3 -m decision_inbox inbox reply demo --text-file /abs/io/said.txt --agents /abs/io/agents.json",
                       "X 称", "原会话", "不替用户决定", "不改写选项", "不补后果", "不改任何项目的文件",
                       "以后", "先向用户确认收件人", "一字不改", "maxChars"):
            self.assertIn(needle, text)

    def test_no_other_markers_inside(self):
        text = hub.convention("demo")
        self.assertEqual(text.count("<!-- BEGIN"), 1)
        self.assertEqual(text.count("<!-- END"), 1)
        self.assertIn(f"{install.cli()} inbox receive demo", text)


class CommandLineTest(HubCase):
    def setUp(self):
        super().setUp()
        self._plugins = os.environ.get("DECISION_INBOX_PLUGINS_FILE")
        os.environ["DECISION_INBOX_PLUGINS_FILE"] = str(self.home / "no-plugins.json")  # never start spec-guard

    def tearDown(self):
        if self._plugins is None:
            os.environ.pop("DECISION_INBOX_PLUGINS_FILE", None)
        else:
            os.environ["DECISION_INBOX_PLUGINS_FILE"] = self._plugins
        super().tearDown()

    def run_cli(self, *argv):
        import contextlib
        import io
        from decision_inbox.__main__ import main
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def write(self, name, text):
        path = self.home / name
        path.write_text(text, encoding="utf-8")
        return str(path)

    def inbox_file(self, *messages):
        import json
        return self.write("inbox.json", json.dumps({"agent": "di-hub", "hasMore": False, "messages": [
            {"id": mid, "fromAgent": sender, "toAgent": "di-hub", "body": body, "createdAt": SENT,
             "replyTo": None, "expectsReply": True} for mid, sender, body in messages]}, ensure_ascii=False))

    def test_receive_reply_sent_view(self):
        import json
        f = self.inbox_file((1401, "fe-codex", WAIT_USER), (1402, "api-codex", wait_session(target="用户", what="#1 的答复")))
        code, out, _ = self.run_cli("inbox", "receive", "demo", "--inbox", f)
        self.assertEqual(code, 0)
        got = json.loads(out)
        self.assertEqual((got["ack"], got["sends"], got["unread"], got["more"]), ([1401, 1402], [], [], False))
        said = self.write("said.txt", "1 A\n")
        code, out, _ = self.run_cli("inbox", "reply", "demo", "--text-file", said)
        self.assertEqual(code, 0)
        got = json.loads(out)
        self.assertEqual([s["id"] for s in got["sends"]], ["out:1"])
        self.assertIn("已转达：#1 → 前端", got["show"])
        code, out, _ = self.run_cli("inbox", "sent", "demo", "--done", "out:1=3950")
        self.assertEqual((code, json.loads(out)), (0, {"closedTickets": []}))
        outbox = self.write("outbox.json", json.dumps({"agent": "di-hub", "entries": [
            {"id": 3950, "toAgent": "fe-codex", "createdAt": NOW, "deliveryState": "accepted",
             "acknowledgedAt": "2026-10-16T05:40:00Z"}]}))
        agents = self.write("agents.json", json.dumps({"agents": []}))
        code, out, _ = self.run_cli("view", "demo", "--agents", agents, "--outbox", outbox)
        self.assertEqual(code, 0)
        self.assertNotIn("读不到 agent-relay", out)
        self.assertIn("等你决定 0 项", out)
        self.assertEqual(items.get(self.g, 1)["status"], "acknowledged")

    def test_view_without_relay_and_unsent(self):
        self.run_cli("inbox", "receive", "demo", "--inbox", self.inbox_file((1403, "api-codex", "【等待用户】\n结束：无\n")))
        code, out, _ = self.run_cli("view", "demo", "--agents", self.write("agents.json", "not json"))
        self.assertEqual(code, 0)
        self.assertEqual(out.split("\n")[:2], ["⚠ 有 1 条消息没发出去，说「重发」再试", "⚠ 读不到 agent-relay，各线状态不全"])
        code, out, _ = self.run_cli("view", "demo")
        self.assertEqual(code, 0)
        self.assertIn("读不到 agent-relay", out)

    def test_expanded_views(self):
        self.run_cli("inbox", "receive", "demo", "--inbox", self.inbox_file((1404, "fe-codex", WAIT_USER)))
        self.assertTrue(self.run_cli("view", "demo", "detail", "1")[1].startswith("#1 详情"))
        self.assertEqual(self.run_cli("view", "demo", "waits")[1].strip(), "没有开着的等待单")
        self.assertEqual(self.run_cli("view", "demo", "closed", "2026-10-15")[1].strip(), "2026-10-15 没有关闭的等待单")
        self.assertEqual(self.run_cli("view", "demo", "invalidated")[1].strip(), "没有失效的事项")
        self.assertEqual(self.run_cli("view", "demo", "bogus")[0], 2)

    def test_convention_creates_io_folder(self):
        code, out, _ = self.run_cli("inbox", "convention", "demo")
        self.assertEqual(code, 0)
        self.assertIn(f"{self.g.path / 'io'}/inbox.json", out)
        self.assertTrue((self.g.path / "io").is_dir())

    def test_errors(self):
        self.assertEqual(self.run_cli("inbox", "receive", "demo", "--inbox", self.write("bad.json", "[]"))[0], 3)
        self.assertEqual(self.run_cli("inbox", "receive", "demo", "--inbox", str(self.home / "missing.json"))[0], 3)
        self.assertEqual(self.run_cli("inbox", "sent", "demo", "--done", "out:9=1")[0], 2)
        self.assertEqual(self.run_cli("inbox", "sent", "demo", "--done", "out:1")[0], 2)
        self.assertEqual(self.run_cli("inbox", "receive", "nope", "--inbox", "x")[0], 2)
        self.assertEqual(self.run_cli("inbox", "bogus")[0], 2)
        self.assertEqual(self.run_cli("view", "nope")[0], 2)
        self.assertEqual(self.run_cli("store", "show", "demo")[0], 0)
