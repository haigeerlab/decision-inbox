import unittest
from pathlib import Path

from helpers import TempHomeTestCase
from test_health import NOW, WAIT_USER, agent, at, line_map, module, snapshot

from decision_inbox import health, items, query, specguard, store, tickets
from decision_inbox.view import ago


def hhmm(value: str) -> str:
    from datetime import datetime
    return datetime.fromisoformat(value).astimezone().strftime("%H:%M")


class QueryCase(TempHomeTestCase):
    def setUp(self):
        super().setUp()
        self.g, _ = store.init_group("demo")
        people = [
            ("hub", "收件枢纽", "hub", [], "claude-desktop", None),
            ("fe", "前端", "dev", ["前端"], "codex-desktop", "/tmp/fe"),
            ("api", "API", "dev", ["API"], "codex-desktop", "/tmp/api"),
            ("bg", "后台", "dev", ["后台"], "codex-desktop", "/tmp/bg"),
            ("owner", "前端负责人", "owner", ["前端"], "claude-desktop", None),
        ]
        with self.g.transaction() as tx:
            for name, short, role, line, host, repo in people:
                entry = {"relayName": name, "shortName": short, "role": role, "line": line, "host": host}
                if repo:
                    entry["repo"] = repo
                tx.add_session(entry)
        self.ids = iter(range(4000, 4100))

    def wait(self, waiter, target, sent_ago=5, what="接口"):
        text = f"【等待其他会话】\n结束：无\n在等谁：{target}\n等什么：{what}\n"
        return tickets.receive(self.g, text, sender=waiter, relay_id=next(self.ids), sent_at=at(sent_ago)).opened

    def ask(self, sender="fe", stopped=True, ago_minutes=5, text=None):
        text = text or WAIT_USER.replace("你该回：12 A", "你该回：A")
        if not stopped:
            text = text.replace("是否完全停住：是", "是否完全停住：否")
        return items.receive(self.g, text, sender=sender, relay_id=next(self.ids), received_at=at(ago_minutes)).item

    def assess(self, agents=(), maps=None, previous=None):
        relay = snapshot(*agents)
        return health.assess(self.g, now=NOW, relay=relay, maps=maps or {}, previous=previous), relay


class LinesTest(QueryCase):
    def test_full_row(self):
        maps = {"fe": line_map([module("pay", done=6, total=11, last_tick=at(40))], active="pay")}
        self.wait("fe", "API", 20)
        a, relay = self.assess([agent("fe", activity_ago=3), agent("api", activity_ago=200)], maps)
        rows = query.render_lines(self.g, now=NOW, assessment=a, relay=relay, maps=maps).split("\n")
        self.assertEqual(rows[0], f"前端 · 阻塞：等 API · 当前模块 pay（6/11）· 最后产出 {hhmm(at(40))}（40 分钟前）"
                                  f"· 未读 0 · 在等：API")
        self.assertEqual(len(rows), 3)
        self.assertTrue(rows[1].startswith("API · 3 小时无活动 · 当前模块：未读取 · 最后产出：无记录 · 未读 0 · 在等：—"))
        self.assertTrue(rows[2].startswith("后台 · "))
        self.assertIn("未读 未知", rows[2])

    def test_snapshot_change_is_newer_output(self):
        maps = {"fe": line_map([module("pay", done=7, total=11, last_tick=at(90))])}
        previous = {"version": 1, "at": at(30), "sessions": {"fe": {"pay": {"done": 6, "changedAt": at(200)}}}}
        a, relay = self.assess([agent("fe")], maps, previous)
        row = query.render_lines(self.g, now=NOW, assessment=a, relay=relay, maps=maps).split("\n")[0]
        self.assertIn(f"最后产出 {hhmm(NOW)}（0 分钟前）", row)

    def test_shallow_history_ignores_tick_time(self):
        maps = {"fe": line_map([module("pay", last_tick=at(40))], history="shallow")}
        a, relay = self.assess([agent("fe")], maps)
        row = query.render_lines(self.g, now=NOW, assessment=a, relay=relay, maps=maps).split("\n")[0]
        self.assertIn("最后产出：无记录", row)

    def test_spec_guard_reasons_and_done(self):
        maps = {"fe": specguard.ReadResult("no-map", "无能力图", 3),
                "api": specguard.ReadResult("not-installed", "本机没有安装 spec-guard"),
                "bg": line_map([module("jobs", status="done", step=None, done=3, total=3)], stage="DONE", active=None)}
        a, relay = self.assess([], maps)
        rows = query.render_lines(self.g, now=NOW, assessment=a, relay=relay, maps=maps).split("\n")
        self.assertIn("· 无能力图 · 最后产出", rows[0])
        self.assertIn("· 本机没有安装 spec-guard · 最后产出", rows[1])
        self.assertIn("· 全部模块已完成 · 最后产出", rows[2])

    def test_waiting_on_user_and_several(self):
        no = self.ask("fe")
        self.wait("api", "前端", 10)
        self.wait("api", "后台", 5)
        self.wait("bg", "用户", 5)
        a, relay = self.assess()
        rows = query.render_lines(self.g, now=NOW, assessment=a, relay=relay, maps={}).split("\n")
        self.assertTrue(rows[0].endswith(f"在等：你（#{no}）"))
        self.assertTrue(rows[1].endswith("在等：前端、后台"))
        self.assertTrue(rows[2].endswith("在等：你"))


def flow_head(text: str) -> list[str]:
    return text.split("\n\n")[0].split("\n")


class FlowSourceTest(QueryCase):
    def flow(self, agents=(), maps=None):
        a, relay = self.assess(agents, maps)
        return flow_head(query.render_flow(self.g, now=NOW, assessment=a, relay=relay, wakes={}))

    def test_cycle(self):
        self.wait("fe", "API", 30)
        self.wait("api", "前端", 20)
        third = self.wait("bg", "前端", 5)
        head = self.flow()
        self.assertEqual(head[0], f"停在哪：前端 ⇄ API（{hhmm(at(30))} 起）")
        self.assertEqual(head[1:4], ["为什么：互等成环", "你要做：你来定谁先做（谁来做：用户）", f"被它挡住：后台（#{third}）"])

    def test_most_blocked_with_indirect(self):
        direct = self.wait("api", "前端", 10)
        indirect = self.wait("bg", "API", 3)
        head = self.flow([agent("fe", activity_ago=2)])
        self.assertEqual(head[0], f"停在哪：前端（{hhmm(at(10))} 起）")
        self.assertEqual(head[3], f"被它挡住：API（#{direct}）、后台（#{indirect}）")
        self.assertEqual(head[4], "其他：前端负责人 无活动记录（agent-relay 没有它的数据）")

    def test_tie_picks_earliest_waited(self):
        self.wait("api", "前端", 10)
        self.wait("bg", "前端负责人", 20)
        self.assertTrue(self.flow()[0].startswith("停在哪：前端负责人（"))

    def test_fluent(self):
        head = self.flow([agent(n, activity_ago=1) for n in ("fe", "api", "bg", "owner")])
        self.assertEqual(head, ["流畅：没有卡点"])

    def test_without_graph_uses_priority(self):
        maps = {"api": line_map([module(last_tick=at(150))])}
        head = self.flow([agent("fe", state="stopped"), agent("api", activity_ago=150),
                          agent("bg", activity_ago=1), agent("owner", activity_ago=1)], maps)
        self.assertEqual(head[:3], ["停在哪：前端", "为什么：掉线",
                                    "你要做：巡视会自动叫醒，叫不醒请打开「前端」（谁来做：插件，兜底用户）"])


class FlowCategoryTest(QueryCase):
    """Each source category with a session waiting on 前端 (requirement 7.1 table)."""

    def verdict(self, fe_agent=None, maps=None, signals_from=()):
        self.wait("api", "前端", 10)
        agents = [fe_agent] if fe_agent else []
        a, relay = self.assess(list(agents) + list(signals_from), maps)
        return flow_head(query.render_flow(self.g, now=NOW, assessment=a, relay=relay, wakes={}))[1:3]

    def test_needs_user(self):
        fe = agent("fe", state="waiting-approval")
        fe["presence"]["detail"] = "permission prompt"
        self.assertEqual(self.verdict(fe), ["为什么：等你在原会话亲自确认（permission prompt）",
                                            "你要做：打开「前端」会话，确认它弹出的请求（谁来做：用户）"])

    def test_needs_user_wins_over_item(self):
        no = self.ask("fe")
        self.assertEqual(self.verdict(agent("fe", state="waiting-input"))[0], "为什么：等你在原会话亲自确认")
        self.assertIsNotNone(no)

    def test_item(self):
        no = self.ask("fe")
        self.assertEqual(self.verdict(), [f"为什么：等你决定 #{no}：支付页先接哪种支付方式",
                                          f"你要做：回「{no} A 先接微信支付」（谁来做：用户）"])

    def test_retired(self):
        fe = agent("fe", state="unknown", activity_ago=300)
        fe["retiredAt"] = at(100)
        self.assertEqual(self.verdict(fe), ["为什么：身份失效（agent-relay 里这个身份已退役）",
                                            "你要做：叫醒后用原名重登（谁来做：插件 + agent-relay）"])

    def test_offline(self):
        self.assertEqual(self.verdict(agent("fe", state="stopped"))[0], "为什么：掉线")

    def test_delivered_not_picked(self):
        api = agent("api", activity_ago=60, waiting=(1, ["fe"], 8))
        self.assertEqual(self.verdict(agent("fe", activity_ago=60), signals_from=[api]),
                         ["为什么：交付了没人接：前端 已发消息给 API，API 还没去取",
                          "你要做：叫醒 API 去取前端的交付（谁来做：插件）"])

    def test_stalled(self):
        maps = {"fe": line_map([module(last_tick=at(150))])}
        self.assertEqual(self.verdict(agent("fe", activity_ago=150), maps),
                         ["为什么：悄悄停下：停住 2 小时，还有已批准的任务没做完",
                          "你要做：叫醒 前端，要它继续或上抛（谁来做：插件）"])

    def test_working(self):
        self.assertEqual(self.verdict(agent("fe", activity_ago=2, since_ago=25)),
                         ["为什么：正在忙长任务，已忙 25 分钟", "你要做：不打扰，等它做完这一轮（谁来做：—）"])

    def test_external(self):
        self.wait("fe", "设计组", 40, what="支付页设计稿")
        self.assertEqual(self.verdict(agent("fe", activity_ago=60)),
                         ["为什么：等别的线交付：等 设计组 的「支付页设计稿」", "你要做：交审查者跟进（谁来做：审查者）"])

    def test_idle_but_waited_on(self):
        self.assertEqual(self.verdict(agent("fe", activity_ago=200)),
                         ["为什么：被等着但没在干活（3 小时无活动）",
                          "你要做：问 前端 是否已交付，没交付就让它接着做（谁来做：用户）"])


class FlowDetailsTest(QueryCase):
    def details(self, agents=(), maps=None, wakes=None):
        a, relay = self.assess(agents, maps)
        text = query.render_flow(self.g, now=NOW, assessment=a, relay=relay, wakes=wakes or {})
        return text.split("\n\n")[1].split("\n")

    def test_quiet_has_five_rows(self):
        self.assertEqual(self.details(), ["检查明细", "- 等待链：无等待", "- 积压：无", "- 停住的线：无", "- 漏抛：无",
                                          "- 长期外部阻塞：无"])

    def test_chain_and_cycle(self):
        self.wait("fe", "API", 5)
        self.wait("api", "前端", 5)
        self.wait("bg", "前端", 5)
        self.assertEqual(self.details()[1], "- 等待链：前端 → API；API → 前端；后台 → 前端；有循环：前端 ⇄ API")

    def test_backlog_threshold_and_failed_wakes(self):
        agents = [agent("fe", waiting=(3, ["api"], 10)), agent("api", waiting=(2, ["fe"], 9))]
        wakes = {"fe": {"held": 1, "refused": 1, "unknown": 1, "expired": 1, "acknowledged": 5, "pending": 2}}
        self.assertEqual(self.details(agents, wakes=wakes)[2], "- 积压：前端 有 3 条未读，最早已等 10 分钟，叫醒没成功 4 次")

    def test_stalled_line(self):
        maps = {"fe": line_map([module(last_tick=at(150))])}
        self.assertTrue(self.details([agent("fe", activity_ago=150)], maps)[3].startswith("- 停住的线：前端 停住 2 小时："))

    def test_missed_raise(self):
        agents = [agent("fe", state="waiting-input"), agent("api", state="waiting-input"),
                  agent("bg", state="waiting-input")]
        self.ask("api")
        self.wait("bg", "前端", 5)
        self.assertEqual(self.details(agents)[4], "- 漏抛：前端 停在自己会话里等输入，但没抛【等待用户】")

    def test_long_external_block(self):
        self.wait("fe", "API", 59)
        self.wait("bg", "设计组", 60, what="设计稿")
        self.wait("api", "用户", 300)
        self.assertEqual(self.details()[5], "- 长期外部阻塞：后台 等 设计组：设计稿 · 已阻塞 1 小时 · 审查者跟进：第一版不记录")


def status(no, sender, recipient, sent_at, delivery="accepted", ack=None, replies=(), wake=None, outcome=None):
    from decision_inbox.relay import MessageStatusFact
    return MessageStatusFact(no, sender, recipient, sent_at, delivery, ack, tuple(replies),
                             wake[0] if wake else None, wake[1] if wake else None, outcome)


class ItemTest(QueryCase):
    def lifecycle(self):
        no = self.ask("fe", ago_minutes=50)
        items.answer(self.g, [items.Answer(no, "A", f"{no} A")], answered_at=at(40))
        items.record_sent(self.g, no, "fe", 7001, at=at(39))
        items.update_delivery(self.g, {7001: ("accepted", None)}, at=at(35))
        items.update_delivery(self.g, {7001: ("accepted", at(30))}, at=at(30))
        from decision_inbox import protocol
        items.on_resumed(self.g, protocol.parse(f"【已恢复】\n结束：#{no}\n"), sender="fe", at=at(20))
        return no

    def test_message_ids(self):
        no = self.lifecycle()
        received = items.get(self.g, no)["relayId"]
        items.record_sent(self.g, no, "fe", 7001, at=at(10))
        self.assertEqual(query.item_message_ids(self.g, no), (received, 7001))
        self.assertEqual(query.item_message_ids(self.g, 999), ())

    def test_timeline_without_statuses_says_not_brought(self):
        """wait-honesty-and-briefs A3: no --status this time is not the mailbox lacking the message."""
        no = self.lifecycle()
        received = items.get(self.g, no)["relayId"]
        text = query.render_item(self.g, no)
        self.assertIn(f"本次没带 #{received} 的 agent-relay 状态", text)
        self.assertNotIn("查不到", text)

    def test_timeline(self):
        no = self.lifecycle()
        received = items.get(self.g, no)["relayId"]
        statuses = {7001: status(7001, "hub", "fe", at(39), ack=at(30), replies=(7005,),
                                 wake=("acknowledged", "Recipient acknowledged the message"), outcome="replied")}
        text = query.render_item(self.g, no, statuses)
        self.assertEqual(text.split("\n"), [
            f"#{no} · 前端 · 支付页先接哪种支付方式 · 当前：已结束",
            f"{hhmm(at(50))} 前端 抛出（agent-relay #{received}；审查：不需审：本会话无审查者）",
            f"{hhmm(at(50))} agent-relay 查不到 #{received}",
            f"{hhmm(at(40))} 你答复：{no} A",
            f"{hhmm(at(39))} 转发给 前端（agent-relay #7001）",
            f"{hhmm(at(39))} agent-relay #7001：投递 accepted，唤醒 acknowledged（Recipient acknowledged the message），"
            "回复 #7005，结果 replied",
            f"{hhmm(at(35))} 对方已取走",
            f"{hhmm(at(30))} agent-relay #7001：前端 已确认",
            f"{hhmm(at(30))} 对方已确认",
            f"{hhmm(at(20))} 前端 已结项，待决事项结束",
        ])
        self.assertNotIn("先接微信支付", text)

    def test_superseded_and_withdrawn(self):
        old = self.ask("fe", ago_minutes=30)
        new = self.ask(text=WAIT_USER.replace("【等待用户】", f"【等待用户】【取代 #{old}】"), ago_minutes=20)
        self.assertIn(f"被 #{new} 取代", query.render_item(self.g, old))
        items.receive(self.g, f"【撤回】\n事项：#{new}\n原因：需求取消\n", sender="fe", relay_id=1, received_at=at(10))
        self.assertTrue(query.render_item(self.g, new).endswith(f"{hhmm(at(10))} 提出方撤回（原因：需求取消）"))

    def test_ticket_and_unknown(self):
        t = self.wait("fe", "API", 30, what="订单接口")
        tickets.close_by_user(self.g, t, "不等了", at=at(5))
        text = query.render_item(self.g, t)
        self.assertEqual(text.split("\n")[0], f"W{t} · 等待记录 · 前端 等 API · 当前：已关")
        self.assertIn(f"{hhmm(at(30))} 前端 开始等待：等 API 的「订单接口」（agent-relay #", text)
        self.assertTrue(text.endswith(f"{hhmm(at(5))} 关掉：用户关闭，依据：不等了"))
        self.assertEqual(query.render_item(self.g, 999), "999 既不是待决事项（#999）也不是等待记录（W999）")


class CommandLineTest(QueryCase):
    def setUp(self):
        super().setUp()
        import os
        self._plugins = os.environ.get("DECISION_INBOX_PLUGINS_FILE")
        os.environ["DECISION_INBOX_PLUGINS_FILE"] = str(self.home / "no-plugins.json")  # never start spec-guard

    def tearDown(self):
        import os
        if self._plugins is None:
            os.environ.pop("DECISION_INBOX_PLUGINS_FILE", None)
        else:
            os.environ["DECISION_INBOX_PLUGINS_FILE"] = self._plugins
        super().tearDown()

    def file(self, name, text):
        path = self.home / name
        path.write_text(text, encoding="utf-8")
        return str(path)

    def run_cli(self, *argv):
        import contextlib
        import io
        from decision_inbox.__main__ import main
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def digest(self):
        import hashlib
        return {str(p.relative_to(self.g.path)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(self.g.path.rglob("*")) if p.is_file()}

    def test_four_subcommands_are_read_only(self):
        import json
        no = self.ask("fe")
        items.answer(self.g, [items.Answer(no, "A", f"{no} A")], answered_at=at(3))
        items.record_sent(self.g, no, "fe", 7001, at=at(2))
        self.wait("api", "前端", 20)
        agents = self.file("agents.json", json.dumps({"count": 1, "agents": [agent("fe", activity_ago=1)]}))
        wakes = self.file("wakes.json", (Path(__file__).resolve().parent / "fixtures" / "relay" /
                                         "real-wake-jobs.json").read_text(encoding="utf-8"))
        st = json.loads((Path(__file__).resolve().parent / "fixtures" / "relay" / "message-status.json").read_text())
        st["message"]["id"] = 7001
        status_file = self.file("status.json", json.dumps(st))
        before = self.digest()
        code, out, _ = self.run_cli("query", "lines", "demo", "--agents", agents, "--relay-version", "0.6.10")
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("前端 · "))
        self.assertIn("仓库路径必须是存在的绝对路径目录", out)  # spec-guard-reader's reason is shown, not hidden
        code, out, _ = self.run_cli("query", "flow", "demo", "--agents", agents, "--wakes", wakes)
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("停在哪：前端"))
        self.assertIn("检查明细", out)
        code, out, _ = self.run_cli("query", "item-ids", "demo", str(no))
        self.assertEqual((code, out.split()[-1]), (0, "7001"))
        self.assertEqual(self.run_cli("query", "item-ids", "demo", f"#{no}")[:2], (code, out))  # glossary-rename
        code, out, _ = self.run_cli("query", "item", "demo", str(no), "--status", status_file)
        self.assertEqual(code, 0)
        self.assertIn("agent-relay #7001：投递 accepted", out)
        self.assertNotIn("正文预览", out)
        self.assertEqual(self.digest(), before)

    def test_flow_heads_with_patrol_alarm(self):
        """e2e-round1-fixes F4: /flow shows the same alarm as the main view."""
        import json
        with self.g.transaction() as tx:
            tx.write_state("onboarding", {"patrolTask": "decision-inbox-patrol-demo"})
            tx.write_state("patrol", {"lastRunAt": "2020-01-01T00:00:00Z"})
        agents = self.file("agents.json", json.dumps({"count": 0, "agents": []}))
        wakes = self.file("wakes.json", (Path(__file__).resolve().parent / "fixtures" / "relay" /
                                         "real-wake-jobs.json").read_text(encoding="utf-8"))
        code, out, _ = self.run_cli("query", "flow", "demo", "--agents", agents, "--wakes", wakes)
        self.assertEqual(code, 0)
        self.assertRegex(out.split("\n")[0], r"^⚠ 巡视 \d+ 分钟没跑：去定时任务列表看 decision-inbox-patrol-demo")

    def test_errors(self):
        agents = self.file("bad.json", "not json")
        self.assertEqual(self.run_cli("query", "lines", "nope", "--agents", agents)[0], 2)
        code, _, err = self.run_cli("query", "lines", "demo", "--agents", agents)
        self.assertEqual(code, 3)
        self.assertIn("bridge_agents", err)
        self.assertEqual(self.run_cli("query", "item", "demo", "1", "--status", agents)[0], 3)
        self.assertEqual(self.run_cli("query", "lines", "demo")[0], 2)
        self.assertEqual(self.run_cli("query", "item", "demo", "abc")[0], 2)
        self.assertEqual(self.run_cli("store", "show", "demo")[0], 0)


if __name__ == "__main__":
    unittest.main()


class DoubtTimelineTest(QueryCase):
    lifecycle = ItemTest.lifecycle

    def test_doubt_wording(self):
        from decision_inbox.relay import MessageStatusFact
        no = self.lifecycle()
        st = MessageStatusFact(7001, "hub", "fe", at(39), "accepted", None, (), "accepted", None, None, wake_doubt=True)
        text = query.render_item(self.g, no, {7001: st})
        self.assertIn("agent-relay #7001：已接受但没读到（送达存疑，来源：agent-relay）", text)
        self.assertNotIn("投递 accepted", text)
