"""approval-display Task 3: background around an approval item (project, map position, rounds, decisions)."""

import hashlib
import json
import shutil
import subprocess
import tempfile
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
