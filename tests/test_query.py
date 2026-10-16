import unittest

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


if __name__ == "__main__":
    unittest.main()
