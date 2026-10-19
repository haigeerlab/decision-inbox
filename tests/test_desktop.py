"""decision-cards Task 7 (DI-9, I-14): a session stuck on a permission prompt that nobody reported.

The bridge_sessions shape (pid, sessionId, cwd, name, status, statusUpdatedAt, hostSessionId) is what
agent-relay printed on 2026-10-19 (idle, busy). The waiting values (`status: waiting`, `waitingFor:
permission prompt`) were rh2-coord's account from stage 3; the same day a probe session stopped on a
real permission prompt and bridge_sessions printed exactly them (RAW_WAITING below).
"""

import json
from datetime import datetime, timedelta

from helpers import TempHomeTestCase

from decision_inbox import desktop, hub, items, patrol, store

NOW = "2026-10-19T21:00:00+08:00"
ROOT = "/tmp/di-desktop"
GO_TO = ("【等待用户】\n结束：无\n来自：协调\n要你决定：去 zeta 会话点弹窗\n要点：在合并 main\n类型：去会话操作\n"
         "会话：rh2-zeta\n链接：local_zeta\n被拦的操作：git merge main\n点哪个按钮：允许\n为什么批不了：宿主弹窗\n"
         "选项与我的建议：\n推荐 A：我去点\n  选了会怎样：继续\n是否完全停住：否\n")


# bridge_sessions for a session on a real permission prompt, 2026-10-19 (paths shortened, ids kept as printed)
RAW_WAITING = {"pid": 41591, "sessionId": "107c1390-f951-47a0-b432-1978b379bf70", "cwd": "/tmp/probe",
               "name": "弹窗探针：故意停在权限确认上", "messagingSocketPath": "/tmp/cc-socks/41591.sock",
               "procStart": "Mon Oct 19 15:26:21 2026", "version": "2.1.299", "peerProtocol": 1,
               "status": "waiting", "statusUpdatedAt": 1792423587257, "waitingFor": "permission prompt",
               "entrypoint": "claude-desktop", "kind": "interactive",
               "hostSessionId": "local_4e769a40-dc2f-49e5-9750-4022799241af"}


def ms(minutes_ago):
    return int((datetime.fromisoformat(NOW) - timedelta(minutes=minutes_ago)).timestamp() * 1000)


def session(name, cwd, host, status="waiting", minutes_ago=10, waiting_for="permission prompt"):
    row = {"pid": 1, "sessionId": f"uuid-{name}", "cwd": cwd, "name": name, "status": status,
           "statusUpdatedAt": ms(minutes_ago), "entrypoint": "claude-desktop", "kind": "interactive",
           "hostSessionId": host}
    if waiting_for is not None and status == "waiting":
        row["waitingFor"] = waiting_for
    return row


def bridge(*rows):
    return json.dumps({"thisSession": {"app": "claude", "sessionId": "x"}, "claude": list(rows)}, ensure_ascii=False)


class DesktopCase(TempHomeTestCase):
    def setUp(self):
        super().setUp()
        self.g, _ = store.init_group("demo")
        with self.g.transaction() as tx:
            tx.add_session({"relayName": "hub", "shortName": "收件箱", "role": "hub", "line": [],
                            "host": "claude-desktop", "desktopSession": "local_hub"})
            tx.add_session({"relayName": "coord", "shortName": "协调", "role": "dev", "line": ["crew"],
                            "host": "claude-desktop", "repo": f"{ROOT}/crew-rehearsal",
                            "desktopSession": "local_coord", "crewCoordinator": True})

    def view(self, *rows, status="ok"):
        sessions = desktop.parse_sessions(bridge(*rows)) if status == "ok" else None
        return hub.main_view(self.g, NOW, sessions=sessions, sessions_status=status)

    def zeta(self, **kw):
        return session("rh2-zeta 模块会话（zeta）", f"{ROOT}/crew-rehearsal-crew/zeta", "local_zeta", **kw)


class PromptReminderTest(DesktopCase):
    def test_stuck_module_session_gets_a_class_7_reminder(self):
        text = self.view(self.zeta())
        self.assertIn("**去 rh2-zeta 模块会话（zeta） 点一下弹窗**（收件箱发现的，提出方没报）· 等了 10 分钟", text)
        self.assertIn("claude://claude.ai/epitaxy/local_zeta", text)
        self.assertIn("点「允许」：合并 main、装依赖、跑测试", text)
        self.assertIn("点完不用回复", text)
        self.assertNotIn("```", text)

    def test_roster_session_by_link_or_repo(self):
        self.assertIn("去 协调会话", self.view(session("协调会话", "/elsewhere", "local_coord")))
        self.assertIn("去 子目录 点", self.view(session("子目录", f"{ROOT}/crew-rehearsal/pkg", "local_other")))

    def test_not_shown(self):
        cases = {
            "not ours": session("别的项目", "/Users/me/other", "local_other"),
            "too fresh": self.zeta(minutes_ago=4),
            "busy": self.zeta(status="busy"),
            "waiting for input": self.zeta(waiting_for="user input"),
            "the hub itself": session("收件箱", "/elsewhere", "local_hub"),
            "sibling but not -crew": session("x", f"{ROOT}/crew-rehearsal-other/zeta", "local_x"),
        }
        for name, row in cases.items():
            with self.subTest(name):
                self.assertNotIn("点一下弹窗**（收件箱发现的", self.view(row))

    def test_open_go_to_session_item_wins(self):
        items.receive(self.g, GO_TO, sender="coord", relay_id=1, received_at=NOW)
        text = self.view(self.zeta())
        self.assertNotIn("（收件箱发现的，提出方没报）", text)
        self.assertIn("**#1 · 去 rh2-zeta 点一下弹窗**", text)

    def test_threshold_configurable(self):
        doc = json.loads((self.g.path / "group.json").read_text(encoding="utf-8"))
        doc["stall"] = {"promptMinutes": 15}
        (self.g.path / "group.json").write_text(json.dumps(doc), encoding="utf-8")
        self.assertNotIn("（收件箱发现的", self.view(self.zeta(minutes_ago=10)))

    def test_without_sessions_says_so(self):
        self.assertIn("本次没带会话状态，看不到停在弹窗上的会话", self.view(status="absent"))
        self.assertNotIn("本次没带会话状态", hub.main_view(self.g, NOW))  # callers that never read it

    def test_raw_output_of_a_real_prompt(self):
        with self.g.transaction() as tx:
            tx.add_session({"relayName": "probe", "shortName": "探针", "role": "dev", "line": ["probe"],
                            "host": "claude-desktop", "repo": "/tmp/probe"})
        later = "2026-10-19T23:40:00+08:00"  # 13 minutes after statusUpdatedAt
        [(s, minutes, owner)] = desktop.stuck(self.g, later, desktop.parse_sessions(bridge(RAW_WAITING)))
        self.assertEqual((s.host, minutes, owner["relayName"]), ("local_4e769a40-dc2f-49e5-9750-4022799241af", 13, "probe"))

    def test_unreadable(self):
        with self.assertRaises(desktop.DesktopDataError):
            desktop.parse_sessions("{oops")
        with self.assertRaises(desktop.DesktopDataError):
            desktop.parse_sessions(json.dumps({"claude": "x"}))


class PatrolNoticeTest(DesktopCase):
    def plan(self, *rows, state=None):
        return patrol.plan(self.g, now=NOW, sessions=desktop.parse_sessions(bridge(*rows)))

    def test_notified_once_per_prompt(self):
        p = self.plan(self.zeta())
        notices = [a for a in p.actions if a.kind == "notify" and a.id.startswith("notify:prompt:")]
        self.assertEqual(len(notices), 1)
        self.assertIn("rh2-zeta 模块会话（zeta）", notices[0].text)
        patrol.record(self.g, p.to_json(), done=[notices[0].id])
        again = self.plan(self.zeta())
        self.assertFalse([a for a in again.actions if a.id.startswith("notify:prompt:")])
        later = self.plan(self.zeta(minutes_ago=6))  # a new prompt: statusUpdatedAt moved
        self.assertTrue([a for a in later.actions if a.id.startswith("notify:prompt:")])


class CommandLineTest(DesktopCase):
    def test_view_and_patrol_read_sessions_file(self):
        import io
        from contextlib import redirect_stdout
        from decision_inbox import __main__ as cli
        path = self.home / "sessions.json"
        path.write_text(bridge(self.zeta(minutes_ago=600)), encoding="utf-8")
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(cli._view(["demo", "--sessions", str(path)]), 0)
        self.assertIn("（收件箱发现的，提出方没报）", out.getvalue())
        self.assertFalse(path.exists())  # consumed like agents.json
        out = io.StringIO()
        with redirect_stdout(out):
            cli._view(["demo"])
        self.assertIn("本次没带会话状态", out.getvalue())
        self.assertIn("--sessions", patrol.prompt("demo"))
        self.assertIn("bridge_sessions", patrol.prompt("demo"))
