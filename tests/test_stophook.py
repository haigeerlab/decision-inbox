import os
import tempfile
import unittest
from pathlib import Path

from helpers import TempHomeTestCase
from test_health import NOW, WAIT_USER, at

from decision_inbox import items, stophook, store, tickets


class HookCase(TempHomeTestCase):
    def setUp(self):
        super().setUp()
        self.repos = Path(tempfile.mkdtemp(prefix="di-repos-"))
        for name in ("fe", "api", "shared"):
            (self.repos / name / "src").mkdir(parents=True)
        self.g, _ = store.init_group("demo")
        people = [("hub", "收件枢纽", "hub", [], "claude-desktop", None),
                  ("fe-codex", "前端", "dev", ["前端"], "codex-desktop", self.repos / "fe"),
                  ("api-codex", "API", "dev", ["API"], "codex-desktop", self.repos / "api"),
                  ("bg-codex", "后台", "dev", ["后台"], "codex-desktop", self.repos / "shared"),
                  ("ui-codex", "UI", "dev", ["UI"], "codex-desktop", self.repos / "shared"),
                  ("fe-owner", "前端负责人", "owner", ["前端"], "claude-desktop", None)]
        with self.g.transaction() as tx:
            for name, short, role, line, host, repo in people:
                entry = {"relayName": name, "shortName": short, "role": role, "line": line, "host": host}
                if repo:
                    entry["repo"] = str(repo)
                tx.add_session(entry)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.repos, ignore_errors=True)
        super().tearDown()

    def wait(self, waiter, target, minutes_ago, what="订单接口"):
        text = f"【等待其他会话】\n结束：无\n在等谁：{target}\n等什么：{what}\n"
        return tickets.receive(self.g, text, sender=waiter, relay_id=1, sent_at=at(minutes_ago)).opened

    def payload(self, cwd=None, active=False):
        return {"cwd": str(cwd or self.repos / "api"), "stop_hook_active": active, "hook_event_name": "Stop",
                "last_assistant_message": "做完了。"}

    def decide(self, **kw):
        session = kw.pop("session", None)
        return stophook.decide(self.g, payload=self.payload(**kw), session=session, now=NOW)


class DecideTest(HookCase):
    def test_blocks_with_reason(self):
        later = self.wait("bg-codex", "API", 5, what="字段说明")
        first = self.wait("fe-codex", "API", 40, what="订单接口的 Mock 数据，\n  交付后我才能接着做")
        self.assertLess(later, first)
        d = self.decide()
        self.assertTrue(d.block)
        self.assertEqual(d.reason, "\n".join([
            "【decision-inbox】收工前请先处理：有会话在等你。",
            f"- #{later} 后台 在等你：字段说明（已等 5 分钟）",
            f"- #{first} 前端 在等你：订单接口的 Mock 数据，交付后我才能接着做（已等 40 分钟）",
            "已经交付：发消息告诉对方，请它发【已恢复】，结束行写这张单的编号。",
            "还没做完：继续做；做不下去就抛【等待其他会话】或【等待用户】，说明卡在哪。",
        ]))

    def test_second_call_passes(self):
        self.wait("fe-codex", "API", 40)
        d = self.decide(active=True)
        self.assertFalse(d.block)
        self.assertIsNone(d.reason)

    def test_reported_block_passes(self):
        self.wait("fe-codex", "API", 40)
        own = self.wait("api-codex", "后台", 10)
        self.assertFalse(self.decide().block)
        tickets.close_by_user(self.g, own, None, at=at(1))
        self.assertTrue(self.decide().block)
        items.receive(self.g, WAIT_USER, sender="api-codex", relay_id=3, received_at=at(2))
        self.assertFalse(self.decide().block)

    def test_not_fully_stopped_item_does_not_count_as_reported(self):
        self.wait("fe-codex", "API", 40)
        items.receive(self.g, WAIT_USER.replace("是否完全停住：是", "是否完全停住：否"), sender="api-codex",
                      relay_id=3, received_at=at(2))
        self.assertTrue(self.decide().block)

    def test_nobody_waiting_or_waiting_on_user(self):
        self.assertFalse(self.decide().block)
        self.wait("api-codex", "用户", 10)
        self.wait("fe-codex", "后台", 10)
        d = self.decide(cwd=self.repos / "fe")
        self.assertFalse(d.block)

    def test_identity(self):
        self.wait("fe-codex", "API", 40)
        self.assertTrue(self.decide(cwd=self.repos / "api" / "src").block)       # below repo
        self.assertTrue(self.decide(cwd="/nowhere", session="api-codex").block)  # --session wins
        lost = self.decide(cwd="/nowhere")
        self.assertFalse(lost.block)
        self.assertIn("认不出", lost.note)
        both = self.decide(cwd=self.repos / "shared")
        self.assertFalse(both.block)
        self.assertIn("后台", both.note)
        self.assertIn("UI", both.note)
        unknown = self.decide(session="ghost")
        self.assertFalse(unknown.block)
        self.assertIn("ghost", unknown.note)

    def test_symlinked_cwd(self):
        self.wait("fe-codex", "API", 40)
        link = self.repos / "api-link"
        os.symlink(self.repos / "api", link)
        self.assertTrue(self.decide(cwd=link).block)


class CommandLineTest(HookCase):
    def run_hook(self, stdin, *extra, group="demo"):
        import subprocess
        import sys
        from helpers import REPO
        env = dict(os.environ, PYTHONPATH=str(REPO))
        done = subprocess.run([sys.executable, "-m", "decision_inbox", "hook", "stop", "--group", group, *extra],
                              input=stdin, capture_output=True, text=True, env=env, timeout=30)
        return done.returncode, done.stdout, done.stderr

    def digest(self):
        import hashlib
        return {str(p.relative_to(self.g.path)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(self.g.path.rglob("*")) if p.is_file()}

    def test_block_and_pass(self):
        import json
        self.wait("fe-codex", "API", 40)
        before = self.digest()
        code, out, err = self.run_hook(json.dumps(self.payload()))
        self.assertEqual(code, 0)
        doc = json.loads(out)
        self.assertEqual(doc["decision"], "block")
        self.assertTrue(doc["reason"].startswith("【decision-inbox】收工前请先处理：有会话在等你。"))
        code, out, err = self.run_hook(json.dumps(self.payload(active=True)))
        self.assertEqual((code, out), (0, ""))
        self.assertIn("本轮已经拦过一次", err)
        code, out, _ = self.run_hook(json.dumps(self.payload(cwd="/nowhere")), "--session", "api-codex")
        self.assertEqual(json.loads(out)["decision"], "block")
        self.assertEqual(self.digest(), before)

    def test_errors_pass(self):
        import json
        cases = [("not json", ("demo",)), (json.dumps(self.payload()), ("nope",)),
                 (json.dumps([1, 2]), ("demo",)), ("", ("demo",))]
        for stdin, (group,) in cases:
            with self.subTest(stdin=stdin[:10], group=group):
                code, out, err = self.run_hook(stdin, group=group)
                self.assertEqual((code, out), (0, ""))
                self.assertEqual(len(err.strip().splitlines()), 1, err)
        self.wait("fe-codex", "API", 40)
        (self.g.path / "state" / "tickets.json").write_text("{broken", encoding="utf-8")
        code, out, err = self.run_hook(json.dumps(self.payload()))
        self.assertEqual((code, out), (0, ""))
        self.assertTrue(err.strip())

    def test_bad_arguments_still_pass(self):
        import subprocess
        import sys
        from helpers import REPO
        env = dict(os.environ, PYTHONPATH=str(REPO))
        done = subprocess.run([sys.executable, "-m", "decision_inbox", "hook", "stop"], input="{}",
                              capture_output=True, text=True, env=env, timeout=30)
        self.assertEqual((done.returncode, done.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()


class AnsweredNotResumedTest(HookCase):
    """answer-handoff-gaps 已定事项 1：已答未恢复也拦一次（宿主差异 H17）。"""

    def answered(self, reply="1 A", sender="api-codex", minutes_ago=3):
        no = items.receive(self.g, WAIT_USER, sender=sender, relay_id=7, received_at=at(30)).item
        items.answer(self.g, items.interpret_reply(self.g, reply.replace("1", str(no), 1)).answers,
                     answered_at=at(minutes_ago))
        return no

    def test_h17_scenario_blocks_once(self):
        no = self.answered()
        d = self.decide()
        self.assertTrue(d.block)
        self.assertEqual(d.reason, "\n".join([
            "【decision-inbox】收工前请先处理：用户已答复你抛的事项，你还没发【已恢复】。",
            f"- #{no} 用户已答复：「{no} A」（3 分钟前）",
            "做完了：发【已恢复】，结束行写这个编号。",
            "做不下去：抛【等待其他会话】或【等待用户】，说明卡在哪。",
        ]))
        self.assertFalse(self.decide(active=True).block)

    def test_resumed_item_passes(self):
        from decision_inbox import protocol
        no = self.answered()
        items.on_resumed(self.g, protocol.parse(f"【已恢复】\n结束：#{no}\n"), sender="api-codex", at=at(1))
        self.assertFalse(self.decide().block)

    def test_picked_and_acknowledged_still_block(self):
        no = self.answered()
        relay_id = 4001
        items.record_sent(self.g, no, to="api-codex", relay_id=relay_id, at=at(2))
        items.update_delivery(self.g, {relay_id: ("accepted", "2026-10-16T03:59:00Z")}, at=at(1))
        self.assertEqual(items.get(self.g, no)["status"], "acknowledged")
        self.assertTrue(self.decide().block)

    def test_own_ticket_still_passes(self):
        self.answered()
        self.wait("api-codex", "后台", 10)
        self.assertFalse(self.decide().block)

    def test_other_sessions_item_does_not_block(self):
        self.answered(sender="fe-codex")
        self.assertFalse(self.decide().block)

    def test_long_original_clipped(self):
        no = self.answered(reply="1 A，" + "字" * 60)
        line = self.decide().reason.split("\n")[1]
        self.assertIn("…」", line)
        self.assertEqual(len(line.split("「")[1].split("」")[0]), 41)

    def test_combined_with_someone_waiting(self):
        t = self.wait("fe-codex", "API", 40, what="字段说明")
        no = self.answered()
        self.assertEqual(self.decide().reason, "\n".join([
            "【decision-inbox】收工前请先处理：有会话在等你。",
            f"- #{t} 前端 在等你：字段说明（已等 40 分钟）",
            "已经交付：发消息告诉对方，请它发【已恢复】，结束行写这张单的编号。",
            "还没做完：继续做；做不下去就抛【等待其他会话】或【等待用户】，说明卡在哪。",
            "另外，用户已答复你抛的事项，你还没发【已恢复】：",
            f"- #{no} 用户已答复：「{no} A」（3 分钟前）",
            "做完了：发【已恢复】，结束行写这个编号。",
            "做不下去：抛【等待其他会话】或【等待用户】，说明卡在哪。",
        ]))
