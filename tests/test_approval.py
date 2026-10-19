"""approval-display Task 3: background around an approval item (project, map position, rounds, decisions)."""

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from helpers import TempHomeTestCase

from decision_inbox import approval, items, specguard, store

T1, T2, T3 = "2026-10-19T09:00:00+08:00", "2026-10-19T10:00:00+08:00", "2026-10-19T11:00:00+08:00"


def module(mid, position, status="in_progress", deps=(), step="spec"):
    return {"id": mid, "position": position, "responsibility": "r", "dependsOn": list(deps), "status": status,
            "step": step, "progress": {"done": 0, "total": 0}, "suspendedReason": None, "blockedOn": [],
            "missingDeps": [], "blocks": {"count": 0, "ids": []}, "review": {"spec": "pending", "plan": "none"},
            "lastTickAt": None, "firstTickAt": None, "tickCommits": None, "suspendedAt": None}


def fake_map(*modules, title="crew-rehearsal"):
    doc = {"schemaVersion": 1, "generatedAt": T1, "generator": {"name": "spec-guard", "version": "0.72.0"},
           "project": {"root": "/repo", "title": title},
           "head": {"sha": None, "branch": None, "unmerged": None, "unpushed": None},
           "stage": "BUILDING", "activeModule": None, "nextGate": None, "history": "complete", "totals": {},
           "bottlenecks": [], "awaitingReview": [], "modules": list(modules)}
    return lambda root: specguard.ReadResult("ok", None, 0, specguard.parse_map(json.dumps(doc)))


class ApprovalCase(TempHomeTestCase):
    def setUp(self):
        super().setUp()
        self.g, _ = store.init_group("demo")
        with self.g.transaction() as tx:
            for relay, short, role in (("hub", "收件枢纽", "hub"), ("coord", "门店", "dev")):
                entry = {"relayName": relay, "shortName": short, "role": role, "line": [short] if role == "dev" else [],
                         "host": "claude-desktop"}
                if role == "dev":
                    entry["repo"] = "/tmp/coord"
                tx.add_session(entry)
        self.tmp = Path(tempfile.mkdtemp(prefix="di-approval-"))
        self.repo = self.tmp / "repo"
        (self.repo / "spec").mkdir(parents=True)
        for args in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "t"]):
            subprocess.run(["git", "-C", str(self.repo), *args], check=True)
        (self.repo / "spec" / "alpha.md").write_text("# alpha\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "x"], check=True)
        self.commit = subprocess.run(["git", "-C", str(self.repo), "rev-parse", "--short=7", "HEAD"], check=True,
                                     capture_output=True, text=True).stdout.strip()
        self.relay_ids = iter(range(700, 800))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        super().tearDown()

    def original(self, name, text):
        path = self.tmp / name
        path.write_text(text, encoding="utf-8")
        return f"{path} sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]}"

    def ask(self, node="Spec", at=T1, project="项目：crew-rehearsal\n"):
        sub = self.original(f"sub-{at[11:13]}.txt", f"【交审】\n结束：无\n模块：alpha\n节点：{node}\n要点：x\n")
        text = (f"【等待用户】\n结束：无\n来自：门店\n{project}要你决定：alpha 的 {node} 是否批准\n"
                f"要点：两行\n第二行\n产物：\nalpha：{self.repo}/spec/alpha.md ＠ {self.commit}\n交审原文：\n{sub}\n"
                "选项与我的建议：\n推荐 A：批准\n  选了会怎样：开始写计划\nB. 先不批\n  选了会怎样：说明要改哪里\n"
                "你该回：A\n是否完全停住：是\n")
        r = items.receive(self.g, text, sender="coord", relay_id=next(self.relay_ids), received_at=at)
        self.assertTrue(r.accepted, r.problems)
        return r.item


class RecordTest(ApprovalCase):
    def test_recorded_and_recognised(self):
        no = self.ask()
        it = items.get(self.g, no)
        self.assertTrue(approval.is_approval(it))
        self.assertEqual((it["approvalModule"], it["approvalNode"]), ("alpha", "Spec"))
        self.assertEqual(it["artifacts"][0]["commit"], self.commit)
        self.assertEqual(it["project"], "crew-rehearsal")

    def test_plain_item_is_not_approval(self):
        r = items.receive(self.g, "【等待用户】\n结束：无\n来自：门店\n要你决定：x\n要点：a\nb\n选项与我的建议：\n推荐 A：好\n"
                          "  选了会怎样：好\n是否完全停住：否\n", sender="coord", relay_id=1, received_at=T1)
        self.assertFalse(approval.is_approval(items.get(self.g, r.item)))


class BackgroundTest(ApprovalCase):
    def test_map_position_and_dependencies(self):
        no = self.ask()
        read = fake_map(module("base", 1, "done"), module("alpha", 2, deps=["base"]), module("beta", 3, "ready"))
        bg = approval.background(self.g, items.get(self.g, no), read_map=read)
        self.assertEqual(bg.project, "crew-rehearsal")
        self.assertEqual(bg.module, "alpha")
        self.assertEqual(bg.node, "Spec")
        self.assertEqual(bg.map_lines, ["1. base ✅ 已完成（依赖）", "2. alpha 🔨 写 Spec ← 本项", "3. beta 🟢 可以开始"])
        self.assertEqual(Path(bg.repo).resolve(), self.repo.resolve())

    def test_map_unreadable_says_why(self):
        no = self.ask(project="")
        bg = approval.background(self.g, items.get(self.g, no),
                                 read_map=lambda root: specguard.ReadResult("not-installed", "没装 spec-guard"))
        self.assertEqual(bg.map_lines, [])
        self.assertIn("没装 spec-guard", bg.map_error)
        self.assertEqual(bg.project, "（没写项目）")

    def test_rounds_last_answer_and_related(self):
        first = self.ask(at=T1)
        items.answer(self.g, [items.Answer(first, "B", f"{first} B 验收标准太含糊")], answered_at=T2)
        second = self.ask(at=T2)
        bg = approval.background(self.g, items.get(self.g, second), read_map=fake_map())
        self.assertEqual(bg.round, 2)
        self.assertEqual(bg.last_answer, f"{first} B 验收标准太含糊")
        self.assertEqual(bg.related, [f"#{first}（10-19）你答：{first} B 验收标准太含糊"])


from decision_inbox import health, hub, relay, view  # noqa: E402

NOW = "2026-10-19T12:00:00+08:00"


class DisplayTest(ApprovalCase):
    """Tasks 4, 5: the approval card in order, originals verbatim, recommendation last; one card open."""

    def render(self, no):
        return view.render_approval(self.g, items.get(self.g, no), NOW, read_map=fake_map(module("alpha", 1)))

    def test_sections_in_order_verbatim_and_no_copy_block(self):
        no = self.ask()
        text = self.render(no)
        heads = [line for line in text.split("\n") if line.startswith("━━")]
        self.assertTrue(heads[0].startswith(f"━━ #{no} · crew-rehearsal · 模块 alpha · 审 Spec"))
        self.assertEqual([h.split("【")[-1] for h in heads[1:]],
                         ["原文】", "原文】", "决策收件箱补充】", "决策收件箱补充】"])
        self.assertIn("开发会话的交审原文", heads[1])
        self.assertIn(f"spec/alpha.md @ {self.commit}", heads[2])
        self.assertIn("│ 【交审】\n│ 结束：无\n│ 模块：alpha\n│ 节点：Spec\n│ 要点：x\n", text)  # verbatim, marked
        self.assertIn("# alpha\n", text)
        self.assertTrue(heads[-1].startswith("━━ 选项与推荐"))
        self.assertNotIn("```", text.split("━━ 选项与推荐")[1])  # no copy block for the answer
        self.assertIn("│ 【交审】", text)  # decision-cards: plain-text originals marked, never fenced
        self.assertIn("Spec 批准后，授权写 Plan", text)
        self.assertIn("开始写计划", text)  # the proposer's own consequence
        self.assertTrue(text.rstrip().endswith(f"答复写法示例：{no} A"))

    def test_unreadable_original_says_why_not_brief(self):
        no = self.ask()
        Path(items.get(self.g, no)["originals"]["submission"][0]["path"]).write_text("改过了", encoding="utf-8")
        text = self.render(no)
        self.assertIn("原文取不到", text)
        self.assertIn("指纹对不上", text)
        self.assertNotIn("第二行", text)  # never the brief instead

    def test_main_view_opens_none_and_look_commands(self):
        a = self.ask(at=T1)
        b = self.ask(node="Plan", at=T2)
        with self.g.transaction() as tx:  # a second sender so b does not supersede a
            tx.add_session({"relayName": "coord2", "shortName": "后台", "role": "dev", "line": ["后台"],
                            "host": "claude-desktop", "repo": "/tmp/c2"})
        doc = store.read_state(self.g, "items")
        doc["items"][str(b)]["sender"] = "coord2"
        doc["items"][str(a)]["status"] = "pending"
        with self.g.transaction() as tx:
            tx.write_state("items", doc)
        out = view.render(self.g, now=NOW, assessment=health.assess(self.g, now=NOW, relay=None))
        # decision-cards DI-3: no original opens in the main view; 「看 N」 is the card, 「看 N 全文」 the originals
        self.assertEqual(out.count("━━ 开发会话的交审原文"), 0)
        self.assertEqual(out.count("```\n"), 2 * 2 + 2)  # one copy block per card, and 「一次答完」
        look = hub.reply(self.g, f"看 {b}", now=NOW).show
        self.assertNotIn("━━ 开发会话的交审原文", look)
        self.assertIn(f"**#{b} ·", look)
        self.assertIn("━━ 开发会话的交审原文", hub.reply(self.g, f"看 {b} 全文", now=NOW).show)
        self.assertIn(f"#{b} 详情", hub.reply(self.g, f"{b} 详情", now=NOW).show)


class SplitAndEvidenceTest(ApprovalCase):
    """Tasks 6, 7: several modules in one item; final acceptance criteria against evidence."""

    def test_two_modules_split_and_receipt_hint(self):
        sub_a = self.original("a.txt", "【交审】\n模块：alpha\n节点：Spec\n")
        sub_b = self.original("b.txt", "【交审】\n模块：beta\n节点：Spec\n")
        text = (f"【等待用户】\n结束：无\n来自：门店\n项目：p\n要你决定：两个 Spec\n要点：a\nb\n"
                f"产物：\nalpha：{self.repo}/spec/alpha.md ＠ {self.commit}\nbeta：{self.repo}/spec/alpha.md ＠ {self.commit}\n"
                f"交审原文：\nalpha：{sub_a}\nbeta：{sub_b}\n选项与我的建议：\n推荐 A：批准\n  选了会怎样：开工\n"
                "是否完全停住：否\n")
        r = hub.receive(self.g, relay.Inbox(agent="hub", messages=(relay.InboxMessage(**{
            **{f: None for f in relay.InboxMessage.__dataclass_fields__}, "id": 801, "sender": "coord",
            "body": text, "created_at": T1, "truncated": False, "expects_reply": True}),), has_more=False), now=NOW)
        receipt = Path(r.sends[0]["bodyFile"]).read_text(encoding="utf-8")
        self.assertIn("按决定 47 应各自一项（这一项合了 alpha、beta）", receipt)
        out = view.render_approval(self.g, items.get(self.g, 1), NOW, read_map=fake_map())
        self.assertIn("━━ 模块 alpha", out)
        self.assertIn("━━ 模块 beta", out)
        self.assertLess(out.index("模块：alpha"), out.index("━━ 模块 beta"))

    def test_final_acceptance_evidence_first(self):
        spec = self.repo / "spec" / "alpha.md"
        spec.write_text("# alpha\n\n## 验收标准\n\n1. 能登录\n2. 令牌会刷新\n3. 出错有提示\n\n## 假设\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qam", "spec"], check=True)
        self.commit = subprocess.run(["git", "-C", str(self.repo), "rev-parse", "--short=7", "HEAD"], check=True,
                                     capture_output=True, text=True).stdout.strip()
        sub = self.original("final.txt", "【交审】\n模块：alpha\n节点：最终验收\n验收标准与证据：\n1：test_login 通过\n2：无\n")
        text = (f"【等待用户】\n结束：无\n来自：门店\n项目：p\n要你决定：alpha 最终验收\n要点：a\nb\n"
                f"产物：\n{self.repo}/spec/alpha.md ＠ {self.commit}\n交审原文：\n{sub}\n"
                "选项与我的建议：\n推荐 A：批准\n  选了会怎样：合并\n是否完全停住：否\n")
        no = items.receive(self.g, text, sender="coord", relay_id=900, received_at=T1).item
        out = view.render_approval(self.g, items.get(self.g, no), NOW, read_map=fake_map())
        table = out.split("━━ 验收标准与证据")[1].split("━━")[0]
        self.assertIn("1. 能登录 —— test_login 通过", table)
        self.assertIn("2. 令牌会刷新 —— ⚠ 缺证据（写的是「无」）", table)
        self.assertIn("3. 出错有提示 —— ⚠ 缺证据", table)
        self.assertLess(out.index("━━ 验收标准与证据"), out.index("━━ 开发会话的交审原文"))
        self.assertIn("合并进集成分支", out)


class VerbatimTest(unittest.TestCase):
    def test_no_fence_at_all(self):
        """decision-cards DI-3 (I-9): originals are never a code block; plain text is marked line by line."""
        self.assertEqual(view._verbatim("a ```` b\nc\n", "x.txt"), ["│ a ```` b\n│ c"])
        self.assertEqual(view._verbatim("# 标题\n", "spec/a.md"), ["# 标题"])


class LoopHeadTest(ApprovalCase):
    """loop-detection: the full approval opens with the DI-5 head; the rest stays as it was."""

    def test_head(self):
        from types import SimpleNamespace as NS
        no = self.ask()
        it = items.get(self.g, no)
        with self.g.transaction() as tx:
            doc = tx.read_state("items")
            doc["items"][str(no)]["module"] = "alpha"
            tx.write_state("items", doc)
        it = dict(items.get(self.g, no), blocks=1)
        f = NS(line="coord", module="alpha", project="crew-rehearsal", items=(it,), asked=4, baseline=3, over=1,
               still=0, unread=None, worked_hours=2.4, progress=(1, 4), hit=None, ready=())
        text = view.render_approval(self.g, it, T1, read_map=fake_map(module("alpha", 1)), loop_facts=[f])
        first = text.split("\n")[0]
        self.assertTrue(first.startswith(f"━━ #{no} · crew-rehearsal（门店） · 模块 alpha · 审 Spec · "
                                         "第 4 次问你（基准 3，超出第 1 次） · 你答了 0 次进度没动 · 开工 2 小时 · 进度 1/4"),
                        first)
        self.assertIn("项目：crew-rehearsal", text.split("\n")[1])
