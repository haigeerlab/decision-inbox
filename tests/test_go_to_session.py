"""go-to-session (R21 DI-7, DI-8): a host confirmation the hub cannot approve, shown on top, never answered."""

from pathlib import Path

from helpers import TempHomeTestCase

from decision_inbox import hub, items, store
from test_hub import inbox, message as msg

NOW = "2026-10-19T12:00:00+08:00"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "session-protocol" / "v2.2" / "wait-user"
CLAUDE = (FIXTURES / "go-to-session.txt").read_text(encoding="utf-8")
CODEX = (FIXTURES / "go-to-session-codex.txt").read_text(encoding="utf-8")
ORDINARY = """【等待用户】
结束：无
来自：前端
要你决定：要不要换成分页接口
要点：列表一次拉全量太慢
接口已经支持分页
选项与我的建议：
推荐 A：换成分页
  选了会怎样：首屏变快
B：先不换
  选了会怎样：保持现状
是否完全停住：否
"""


def minutes(n):
    from datetime import datetime, timedelta
    return (datetime.fromisoformat(NOW) + timedelta(minutes=n)).isoformat()


class GoToSessionCase(TempHomeTestCase):
    def setUp(self):
        super().setUp()
        self.g, _ = store.init_group("demo")
        with self.g.transaction() as tx:
            tx.add_session({"relayName": "di-hub", "shortName": "决策收件箱", "role": "hub", "line": [],
                            "host": "claude-desktop", "desktopSession": "local_00000000-0000-0000-0000-000000000001"})
            tx.add_session({"relayName": "fe", "shortName": "前端", "role": "dev", "line": ["前端"],
                            "host": "claude-desktop", "repo": "/tmp/fe",
                            "desktopSession": "local_00000000-0000-0000-0000-0000000000fe"})
            tx.add_session({"relayName": "be", "shortName": "后端", "role": "dev", "line": ["后端"],
                            "host": "codex-desktop", "repo": "/tmp/be"})

    def receive(self, text, sender="fe", relay_id=1, at=NOW):
        r = items.receive(self.g, text, sender=sender, relay_id=relay_id, received_at=at)
        self.assertTrue(r.accepted, r)
        return r.item


class ReceiveAndReplyTest(GoToSessionCase):
    def test_record_keeps_kind_and_fields(self):
        it = items.get(self.g, self.receive(CLAUDE))
        self.assertEqual(it["waitKind"], "go-to-session")
        self.assertEqual(it["goToSession"]["blockedAction"], "Bash: git push origin alpha")
        self.assertIsNone(items.get(self.g, self.receive(ORDINARY, sender="be", relay_id=2))["waitKind"])

    def test_ordinary_and_go_to_session_do_not_supersede_each_other(self):
        first = self.receive(ORDINARY, relay_id=1)
        second = self.receive(CLAUDE, relay_id=2)
        self.assertEqual({items.get(self.g, n)["status"] for n in (first, second)}, {"pending"})
        third = self.receive(CLAUDE, relay_id=3)
        self.assertEqual(items.get(self.g, second)["status"], "superseded")
        self.assertEqual(items.get(self.g, third)["status"], "pending")

    def test_answering_it_sends_nothing(self):
        no = self.receive(CLAUDE)
        r = hub.reply(self.g, f"{no} A", NOW)
        self.assertEqual(list(r.sends), [])
        self.assertIn(f"#{no} 是去会话操作，不需要回复", r.show)
        self.assertEqual(items.get(self.g, no)["status"], "pending")

    def test_mixed_reply_forwards_only_the_ordinary_item(self):
        gts = self.receive(CLAUDE, relay_id=1)
        plain = self.receive(ORDINARY, sender="be", relay_id=2)
        r = hub.reply(self.g, f"{gts} A；{plain} B", NOW)
        self.assertEqual([s["to"] for s in r.sends], ["be"])
        self.assertIn(f"#{gts} 是去会话操作", r.show)
        self.assertEqual(items.get(self.g, gts)["status"], "pending")

    def test_resumed_from_its_sender_closes_it(self):
        no = self.receive(CLAUDE)
        resumed = f"【已恢复】\n结束：#{no}\n"
        hub.receive(self.g, inbox(msg(50, "be", resumed)), minutes(5))
        self.assertEqual(items.get(self.g, no)["status"], "pending")
        hub.receive(self.g, inbox(msg(51, "fe", resumed)), minutes(6))
        self.assertEqual(items.get(self.g, no)["status"], "closed")


class MainViewTest(GoToSessionCase):
    def view(self, at=NOW, relay=None):
        return hub.main_view(self.g, at, relay=relay)

    def test_claude_item_on_top_with_link_and_no_options(self):
        no = self.receive(CLAUDE)
        text = self.view()
        top = text.split("\n\n")[0]
        for words in (f"#{no} · 前端 · 去会话操作", "claude://claude.ai/epitaxy/local_f9d5b932-946c-407b-a5c2-87845cb29425",
                      "被拦的操作：Bash: git push origin alpha", "点：允许（Yes）",
                      "为什么这里批不了：宿主弹窗只能在那个会话里点，决策收件箱代点不了",
                      "你在 #21 已同意，只差宿主这一下", "点完不用回复，对方会发【已恢复】自动结项"):
            self.assertIn(words, top)
        self.assertNotIn("推荐 A", text)
        self.assertNotIn("我去点", text)
        self.assertNotIn(f"━━ {no} ·", text)  # not an ordinary card

    def test_full_link_shown_as_is(self):
        self.receive(CLAUDE.replace("链接：local_f9d5b932-946c-407b-a5c2-87845cb29425",
                                    "链接：claude://claude.ai/epitaxy/local_abc"))
        self.assertIn("claude://claude.ai/epitaxy/local_abc", self.view())

    def test_codex_item_says_open_in_codex(self):
        self.receive(CODEX, sender="be")
        top = self.view().split("\n\n")[0]
        self.assertIn("在 Codex 应用里打开 rh2-beta（/Users/me/live-saas/.worktrees/beta） 对应的任务", top)
        self.assertIn("宿主原文：Allow network access for: npm install", top)
        self.assertNotIn("claude://", top)

    def test_reminder_after_thirty_minutes(self):
        self.receive(CLAUDE)
        self.assertNotIn("再提醒一次", self.view(minutes(29)))
        self.assertIn("已等 40 分钟，再提醒一次", self.view(minutes(40)))

    def test_closed_item_leaves_the_top(self):
        no = self.receive(CLAUDE)
        hub.receive(self.g, inbox(msg(51, "fe", f"【已恢复】\n结束：#{no}\n")), minutes(1))
        self.assertNotIn("去会话操作", self.view(minutes(2)))

    def test_fallback_card_only_without_an_open_item(self):
        from test_health import snapshot, agent
        waiting = snapshot(agent("fe", state="waiting-approval"))
        self.assertIn("去原会话确认 · 前端", self.view(relay=waiting))
        self.receive(CLAUDE)
        self.assertNotIn("去原会话确认", self.view(relay=waiting))

    def test_not_in_the_answer_everything_block(self):
        self.receive(CLAUDE, relay_id=1)
        self.receive(CODEX, sender="be", relay_id=2)
        self.assertNotIn("一次答完", self.view())
