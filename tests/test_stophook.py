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
            f"- W{later}（结束行写 #{later}）后台 在等你：字段说明（已等 5 分钟）",
            f"- W{first}（结束行写 #{first}）前端 在等你：订单接口的 Mock 数据，交付后我才能接着做（已等 40 分钟）",
            "已经交付：发消息告诉对方，请它发【已恢复】，结束行写这条等待记录的编号（#数字）。",
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

    def answered(self, reply="1 A", sender="api-codex", minutes_ago=3, sent=True):
        no = items.receive(self.g, WAIT_USER, sender=sender, relay_id=7, received_at=at(30)).item
        items.answer(self.g, items.interpret_reply(self.g, reply.replace("1", str(no), 1)).answers,
                     answered_at=at(minutes_ago))
        if sent:  # decision-cards DI-6: only an answer that reached the proposer is waited on
            items.record_sent(self.g, no, to=sender, relay_id=3900 + no, at=at(minutes_ago))
        return no

    def test_unsent_answer_does_not_block(self):
        """decision-cards DI-6 (I-2): the proposer never got the answer, so 【已恢复】 is not due yet."""
        self.answered(sent=False)
        self.assertFalse(self.decide().block)

    def test_h17_scenario_blocks_once(self):
        no = self.answered()
        d = self.decide()
        self.assertTrue(d.block)
        self.assertEqual(d.reason, "\n".join([
            "【decision-inbox】收工前请先处理：用户已答复你抛的待决事项，你还没发【已恢复】（表示已结项）。",
            f"- #{no} 用户已答复：「{no} A」（3 分钟前）",
            "做完了：发【已恢复】，结束行写这个编号。",
            "做不下去：抛【等待其他会话】或【等待用户】，说明卡在哪。",
            "已经发过【已恢复】、决策收件箱还没收进：回一句「已发 #邮箱号」即可收工，不用重发。",
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
            f"- W{t}（结束行写 #{t}）前端 在等你：字段说明（已等 40 分钟）",
            "已经交付：发消息告诉对方，请它发【已恢复】，结束行写这条等待记录的编号（#数字）。",
            "还没做完：继续做；做不下去就抛【等待其他会话】或【等待用户】，说明卡在哪。",
            "另外，用户已答复你抛的待决事项，你还没发【已恢复】（表示已结项）：",
            f"- #{no} 用户已答复：「{no} A」（3 分钟前）",
            "做完了：发【已恢复】，结束行写这个编号。",
            "做不下去：抛【等待其他会话】或【等待用户】，说明卡在哪。",
            "已经发过【已恢复】、决策收件箱还没收进：回一句「已发 #邮箱号」即可收工，不用重发。",
        ]))


def progress(done, total, status="ok", module="pay", module_status="in_progress"):
    from types import SimpleNamespace
    m = SimpleNamespace(id=module, progress_done=done, progress_total=total, status=module_status)
    return lambda repo: SimpleNamespace(status=status, map=SimpleNamespace(active_module=module, modules=(m,)))


class SilentStopTest(HookCase):
    """wait-honesty-and-briefs B1: open todos and nothing reported means the session stopped silently."""

    def decide_with(self, read_map, **kw):
        return stophook.decide(self.g, payload=self.payload(**kw), now=NOW, read_map=read_map)

    def test_open_todos_and_nothing_reported_blocks_once(self):
        d = self.decide_with(progress(2, 5))
        self.assertTrue(d.block)
        self.assertEqual(d.reason.split("\n")[0],
                         "【decision-inbox】收工前请先处理：当前模块 pay 还有 3 项没勾，你既没报阻塞也没抛待决事项。")
        self.assertIn("手上没有已批准、还没做完的下一步：抛一项【等待用户】", d.reason)
        self.assertFalse(self.decide_with(progress(2, 5), active=True).block)

    def test_passes_when_done_unreadable_or_reported(self):
        self.assertFalse(self.decide_with(progress(5, 5)).block)
        self.assertFalse(self.decide_with(progress(2, 5, status="not-installed")).block)
        self.wait("api-codex", "前端", 3)
        self.assertFalse(self.decide_with(progress(2, 5)).block)

    def test_pending_item_counts_as_reported(self):
        text = (Path(__file__).resolve().parent / "fixtures" / "protocol" / "wait-user.txt").read_text(encoding="utf-8")
        items.receive(self.g, text.replace("是否完全停住：是", "是否完全停住：否"), sender="api-codex", relay_id=9,
                      received_at=at(1))
        self.assertFalse(self.decide_with(progress(2, 5)).block)

    def test_suspended_module_passes(self):
        """crew-coordinator-seam: a suspended module is waiting on something outside, not a silent stop."""
        self.assertFalse(self.decide_with(progress(2, 5, module_status="suspended")).block)


class CrewCoordinatorTest(HookCase):
    """crew-coordinator-seam: module progress belongs to module-crew, the other two duties still hold."""

    def setUp(self):
        super().setUp()
        (self.repos / "crew" / "src").mkdir(parents=True)
        with self.g.transaction() as tx:
            tx.add_session({"relayName": "crew-coord", "shortName": "前端并行", "role": "dev", "line": ["前端"],
                            "host": "claude-desktop", "repo": str(self.repos / "crew"), "crewCoordinator": True})

    def decide_with(self, read_map, **kw):
        return stophook.decide(self.g, payload=self.payload(cwd=self.repos / "crew", **kw), now=NOW,
                               read_map=read_map)

    def test_open_todos_pass_for_the_coordinator(self):
        self.assertFalse(self.decide_with(progress(2, 5)).block)

    def test_someone_waiting_still_blocks(self):
        self.wait("api-codex", "前端并行", 10)
        self.assertTrue(self.decide_with(progress(2, 5)).block)

    def test_answered_not_resumed_still_blocks(self):
        no = items.receive(self.g, WAIT_USER, sender="crew-coord", relay_id=21, received_at=at(30)).item
        items.answer(self.g, items.interpret_reply(self.g, f"{no} A").answers, answered_at=at(3))
        items.record_sent(self.g, no, to="crew-coord", relay_id=3999, at=at(3))
        self.assertTrue(self.decide_with(progress(2, 5)).block)

    def test_ordinary_dev_line_still_blocks(self):
        d = stophook.decide(self.g, payload=self.payload(cwd=self.repos / "api"), now=NOW, read_map=progress(2, 5))
        self.assertTrue(d.block)


class LeftEntriesTest(HookCase):
    """r20-fixes Task 1 (O-who-left): entries that left the group take no part in finding this session."""

    def leave(self, relay):
        with self.g.transaction() as tx:
            doc = tx.read_state("onboarding")
            doc.setdefault("left", {})[relay] = NOW
            tx.write_state("onboarding", doc)

    def test_shared_repo_finds_the_one_still_in(self):
        self.leave("ui-codex")
        self.wait("fe-codex", "后台", 10)
        d = self.decide(cwd=self.repos / "shared")
        self.assertTrue(d.block)
        self.assertIn("前端 在等你", d.reason)

    def test_left_session_named_passes(self):
        self.wait("fe-codex", "API", 10)
        self.leave("api-codex")
        d = self.decide(session="api-codex")
        self.assertFalse(d.block)
        self.assertIn("api-codex 已退出协作组", d.note)
        self.assertFalse(self.decide().block)  # by cwd: the only entry for this repo has left


class HubTurnCheckTest(unittest.TestCase):
    """decision-cards Task 6 (DI-4, D1 A): the hub's last reply must carry the cards as the command printed them."""

    VIEW = ("等你决定 2 项 · 异常 0\n\n**#47 · epsilon 的Plan，批不批** · 等了 3 分钟 · 挡住 1 条线\n"
            "crew-rehearsal · rh2-coord · 模块 epsilon · Plan（第 2 次交审）\n\n**推荐 A**\n\n```\n47 A\n```\n\n"
            "**#49 · 接下来怎么办** · 等了 5 分钟\n\n**推荐 B**\n\n```\n49 B 换方案：先给我看预览\n```\n\n"
            "等待中 0 条 · 已失效 0 项 · 今天已关 0 条")
    EMPTY = "等你决定 0 项 · 异常 0\n\n等待中 0 条 · 已失效 0 项 · 今天已关 0 条"
    CMD = "/Users/me/.decision-inbox/bin/decision-inbox view di-p0 --agents /x/agents.json"

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="di-transcript-"))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dir, ignore_errors=True)

    def transcript(self, output, final, command=None, extra_turn=False):
        import json
        rows = [{"type": "user", "message": {"role": "user", "content": "看一下"}},
                {"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": command or self.CMD}}]}},
                {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1",
                                                          "content": output}]}},
                {"type": "assistant", "message": {"content": [{"type": "text", "text": final}]}}]
        if extra_turn:
            rows += [{"type": "user", "message": {"role": "user", "content": "谢谢"}},
                     {"type": "assistant", "message": {"content": [{"type": "text", "text": "不客气"}]}}]
        path = self.dir / "t.jsonl"
        path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
        return {"transcript_path": str(path), "stop_hook_active": False, "cwd": "/somewhere"}

    def check(self, payload):
        return stophook.hub_turn_check(payload)

    def test_verbatim_passes(self):
        self.assertFalse(self.check(self.transcript(self.VIEW, self.VIEW)).block)

    def test_missing_head_blocks(self):
        final = self.VIEW.replace("**#49 · 接下来怎么办** · 等了 5 分钟", "#49 也在等你")
        d = self.check(self.transcript(self.VIEW, final))
        self.assertTrue(d.block)
        self.assertIn("**#49 · 接下来怎么办** · 等了 5 分钟", d.reason)
        self.assertIn("逐字", d.reason)

    def test_missing_or_changed_copy_block_blocks(self):
        for final in (self.VIEW.replace("```\n47 A\n```", "回 47 A"),
                      self.VIEW.replace("49 B 换方案：先给我看预览", "49 B 换方案：先给我看预览。")):
            with self.subTest(final=final[-80:]):
                d = self.check(self.transcript(self.VIEW, final))
                self.assertTrue(d.block)
                self.assertIn("复制块", d.reason)

    def test_prompt_reminder_must_stay(self):
        out = self.EMPTY + "\n\n**去 rh2-zeta 点一下弹窗**（收件箱发现的，提出方没报）· 等了 9 分钟"
        self.assertTrue(self.check(self.transcript(out, self.EMPTY)).block)
        self.assertFalse(self.check(self.transcript(out, out)).block)

    def test_summary_instead_of_cards_blocks(self):
        d = self.check(self.transcript(self.VIEW, "有两项等你：47 批 Plan，49 选做法。"))
        self.assertTrue(d.block)

    def test_code_block_without_pending_blocks(self):
        d = self.check(self.transcript(self.EMPTY, self.EMPTY + "\n\n```\n47 A\n```"))
        self.assertTrue(d.block)
        self.assertIn("没有待答", d.reason)
        self.assertFalse(self.check(self.transcript(self.EMPTY, self.EMPTY)).block)

    def test_reply_json_show_is_used(self):
        import json
        out = json.dumps({"show": self.VIEW, "sends": [], "patrolDue": False}, ensure_ascii=False)
        cmd = "decision-inbox inbox reply di-p0 --text-file /x/said.txt --agents /x/agents.json"
        self.assertFalse(self.check(self.transcript(out, self.VIEW, command=cmd)).block)
        self.assertTrue(self.check(self.transcript(out, "已转达", command=cmd)).block)

    def test_passes(self):
        self.assertFalse(self.check(self.transcript(self.VIEW, "随便", command="ls -la")).block)  # no view this turn
        self.assertFalse(self.check(self.transcript(self.VIEW, "不客气", extra_turn=True)).block)  # earlier turn
        payload = self.transcript(self.VIEW, "随便")
        self.assertFalse(self.check(dict(payload, stop_hook_active=True)).block)
        self.assertFalse(self.check({"transcript_path": str(self.dir / "none.jsonl")}).block)
        (self.dir / "bad.jsonl").write_text("{oops\n", encoding="utf-8")
        self.assertFalse(self.check({"transcript_path": str(self.dir / "bad.jsonl")}).block)
        self.assertFalse(self.check({}).block)

    def test_persisted_output_is_read_from_its_file(self):
        saved = self.dir / "out.txt"
        saved.write_text(self.VIEW, encoding="utf-8")
        output = f"<persisted-output>\nOutput too large. Full output saved to: {saved}\n\nPreview…\n</persisted-output>"
        self.assertTrue(self.check(self.transcript(output, "摘要")).block)
        self.assertFalse(self.check(self.transcript(output, self.VIEW)).block)

    def test_hook_entry_passes_outside_any_group(self):
        """hub-stop-scope: only the hub's own session gets the card check (was: blocked wherever it ran)."""
        import json, subprocess, sys
        payload = self.transcript(self.VIEW, "摘要")
        env = dict(os.environ, DECISION_INBOX_HOME=str(self.dir / "home"))
        done = subprocess.run([sys.executable, "-m", "decision_inbox", "hook", "stop"], input=json.dumps(payload),
                              capture_output=True, text=True, cwd=str(Path(__file__).resolve().parent.parent), env=env)
        self.assertEqual(done.returncode, 0)
        self.assertEqual(done.stdout, "")


class HubScopeHookTest(HookCase):
    """hub-stop-scope: the hub's card check runs only for the roster's hub session."""

    def setUp(self):
        super().setUp()
        self.hub_dir = self.repos / "hub"
        self.hub_dir.mkdir()
        with self.g.transaction() as tx:
            tx.write_state("onboarding", {"files": {"hub": str(self.hub_dir / "CLAUDE.md")}})
        self.outside = self.repos / "elsewhere"
        self.outside.mkdir()

    def run_hook(self, cwd, *args):
        import json, subprocess, sys
        rows = [{"type": "user", "message": {"role": "user", "content": "看一下"}},
                {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t1", "name": "Bash",
                                                               "input": {"command": "decision-inbox view demo"}}]}},
                {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1",
                                                          "content": HubTurnCheckTest.VIEW}]}},
                {"type": "assistant", "message": {"content": [{"type": "text", "text": "有两项等你，我看过了。"}]}}]
        path = self.repos / "t.jsonl"
        path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
        payload = {"transcript_path": str(path), "stop_hook_active": False, "hook_event_name": "Stop"}
        if cwd is not None:
            payload["cwd"] = str(cwd)
        done = subprocess.run([sys.executable, "-m", "decision_inbox", "hook", "stop", *args],
                              input=json.dumps(payload), capture_output=True, text=True,
                              cwd=str(Path(__file__).resolve().parent.parent))
        self.assertEqual(done.returncode, 0)
        return (json.loads(done.stdout).get("decision") if done.stdout.strip() else None), done.stderr

    def test_other_sessions_running_view_pass(self):
        for cwd in (self.repos / "api", self.repos / "api" / "src", self.outside):
            with self.subTest(cwd=cwd.name):
                self.assertIsNone(self.run_hook(cwd)[0])

    def test_hub_session_still_blocks(self):
        self.assertEqual(self.run_hook(self.hub_dir)[0], "block")

    def test_no_cwd_passes_with_reason(self):
        decision, err = self.run_hook(None)
        self.assertIsNone(decision)
        self.assertIn("收件箱停止检查放行", err)

    def test_session_flag_decides_role(self):
        self.assertIsNone(self.run_hook(self.outside, "--group", "demo", "--session", "api-codex")[0])
        self.assertEqual(self.run_hook(self.outside, "--group", "demo", "--session", "hub")[0], "block")


class PatrolDirHookTest(HookCase):
    """stage-c2-fixes I-17, replaying the 2026-10-20 probe: a line waits on the hub; the patrol session stops."""

    def setUp(self):
        super().setUp()
        from decision_inbox import onboard
        self.hub_dir = self.repos / "hub"
        self.hub_dir.mkdir()
        (self.hub_dir / "CLAUDE.md").write_text("x", encoding="utf-8")
        with self.g.transaction() as tx:
            doc = tx.read_state("onboarding")
            doc.setdefault("files", {})["hub"] = str(self.hub_dir / "CLAUDE.md")
            tx.write_state("onboarding", doc)
        self.patrol_dir = onboard.patrol_dir("demo")
        self.patrol_dir.mkdir(parents=True, exist_ok=True)
        self.wait("fe-codex", "决策收件箱", 5, what="转达答复")

    def run_hook(self, cwd):
        import contextlib
        import io
        import json
        from unittest import mock
        from decision_inbox.__main__ import main
        out = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(json.dumps(self.payload(cwd)))), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            main(["hook", "stop"])
        return out.getvalue()

    def test_in_hub_folder_it_is_taken_for_the_hub(self):
        self.assertIn('"block"', self.run_hook(self.hub_dir))

    def test_in_patrol_folder_it_passes(self):
        self.assertEqual(self.run_hook(self.patrol_dir).strip(), "")


class InheritedItemTest(AnsweredNotResumedTest):
    """stage-c2-fixes I-18: an answered item a previous session under the same mailbox name raised."""

    def transcript(self, first_at):
        import json
        path = self.repos / "session.jsonl"
        path.write_text("\n".join([json.dumps({"type": "summary", "summary": "x"}),
                                   json.dumps({"type": "user", "timestamp": first_at}),
                                   json.dumps({"type": "assistant", "timestamp": "2099-01-01T00:00:00Z"})]) + "\n",
                        encoding="utf-8")
        return str(path)

    def decide_with(self, transcript):
        payload = dict(self.payload(), transcript_path=transcript)
        return stophook.decide(self.g, payload=payload, session=None, now=NOW)

    def test_session_start_read_from_transcript(self):
        self.assertEqual(stophook.session_start({"transcript_path": self.transcript(at(10))}), at(10))
        self.assertIsNone(stophook.session_start({}))
        self.assertIsNone(stophook.session_start({"transcript_path": str(self.repos / "nope.jsonl")}))

    def test_item_from_before_this_session_says_so(self):
        no = self.answered()  # raised 30 minutes ago, answered 3 minutes ago
        d = self.decide_with(self.transcript(at(1)))
        self.assertTrue(d.block)
        raised, answered = stophook._local(at(30)), stophook._local(at(3))
        self.assertIn(f"- #{no} 是这个邮箱名之前的会话在 {raised} 抛出的，用户 {answered} 答复：「{no} A」", d.reason)
        self.assertIn(f"已经处理完就发【已恢复】结项（结束行写 #{no}）", d.reason)
        self.assertIn(f"不归你处理就发【撤回】，写「事项：#{no}」", d.reason)

    def test_own_item_unchanged(self):
        no = self.answered()
        d = self.decide_with(self.transcript(at(60)))
        self.assertIn(f"- #{no} 用户已答复：「{no} A」（3 分钟前）", d.reason)
        self.assertNotIn("之前的会话", d.reason)

    def test_unreadable_transcript_unchanged(self):
        no = self.answered()
        d = self.decide_with(str(self.repos / "nope.jsonl"))
        self.assertIn(f"- #{no} 用户已答复：「{no} A」（3 分钟前）", d.reason)
