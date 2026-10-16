import json
import unittest
from pathlib import Path

from helpers import TempHomeTestCase
from test_health import NOW, WAIT_USER, at

from decision_inbox import items, mapview, protocol, reviews, specguard, store, tickets
from decision_inbox.reviews import ModuleReview
from decision_inbox.specguard import ModuleFact


def fact(mid="pay", position=1, status="in_progress", step="build", done=6, total=11, reason=None,
         blocked_on=(), missing=(), blocks=(), spec="approved", plan="approved", last_tick=None,
         responsibility="支付页"):
    return ModuleFact(id=mid, position=position, responsibility=responsibility, depends_on=(), status=status,
                      step=step, progress_done=done, progress_total=total, suspended_reason=reason,
                      blocked_on=tuple(blocked_on), missing_deps=tuple(missing), blocks=tuple(blocks),
                      review_spec=spec, review_plan=plan, last_tick_at=last_tick, first_tick_at=None,
                      tick_commits=None, suspended_at=None)


class CellTest(unittest.TestCase):
    def test_status(self):
        cases = [
            (fact(status="done", step=None), "✅ 已完成"),
            (fact(step="spec"), "🔨 写 Spec"),
            (fact(step="plan"), "🔨 写 Plan"),
            (fact(step="build"), "🔨 进行中 6/11"),
            (fact(status="suspended", step=None, reason="等设计稿", blocks=("a", "b", "c")), "⏸ 挂起：等设计稿 · 挡住 3 个"),
            (fact(status="suspended", step=None), "⏸ 挂起：未记原因 · 挡住 0 个"),
            (fact(status="blocked", step=None, blocked_on=("pay", "cart")), "⛔ 阻塞：等 pay、cart"),
            (fact(status="ready", step=None), "🟢 可以开始"),
            (fact(status="not_ready", step=None, missing=("orders",)), "○ 未就绪：缺 orders"),
        ]
        for module, want in cases:
            with self.subTest(want=want):
                self.assertEqual(mapview.status_cell(module), want)

    def test_spec_plan_review(self):
        cases = {("approved", "approved"): "Spec ✔ Plan ✔", ("pending", "none"): "Spec 待审 Plan —",
                 ("revised", "invalid"): "Spec 已改待复审 Plan 标记无效"}
        for (spec, plan), want in cases.items():
            with self.subTest(want=want):
                self.assertEqual(mapview.review_cell(fact(spec=spec, plan=plan)), want)

    def test_architecture_review(self):
        cells = (ModuleReview("R-3", "spec", "changes-required", None, 2, False),
                 ModuleReview("R-4", "plan", "passed-with-advice", 2, 1, True),
                 ModuleReview("R-5", "interface", "passed", None, 1, True),
                 ModuleReview("R-6", "final", "changes-required", None, 1, False))
        self.assertEqual(mapview.arch_cell(cells), "Spec 有须修改项（第 2 轮） · Plan 通过，附建议2条 · 接口提案 通过 · "
                                                   "最终验收 有须修改项（第 1 轮）")
        self.assertEqual(mapview.arch_cell(()), "—")


MULTI = (Path(__file__).resolve().parent / "fixtures" / "protocol" / "wait-user-multiline.txt").read_text(encoding="utf-8")


def module_doc(mid, position, status="done", step=None, done=3, total=3, reason=None, blocked_on=(), missing=(),
               blocks=(), spec="approved", plan="approved", last_tick=None, responsibility=None):
    return {"id": mid, "position": position, "responsibility": responsibility or f"{mid} 的作用", "dependsOn": [],
            "status": status, "step": step, "progress": {"done": done, "total": total}, "suspendedReason": reason,
            "blockedOn": list(blocked_on), "missingDeps": list(missing),
            "blocks": {"count": len(blocks), "ids": list(blocks)}, "review": {"spec": spec, "plan": plan},
            "lastTickAt": last_tick, "firstTickAt": None, "tickCommits": None, "suspendedAt": None}


def make_map(modules, active=None, bottlenecks=(), unmerged=(91, "origin/main"), unpushed=None, stage="BUILDING"):
    totals = {k: 0 for k in ("done", "in_progress", "suspended", "blocked", "ready", "not_ready")}
    for m in modules:
        totals[m["status"]] += 1
    doc = {"schemaVersion": 1, "generatedAt": "2026-10-16T11:37:00+08:00",
           "generator": {"name": "spec-guard", "version": "0.63.1"}, "project": {"root": "/r/fe", "title": "t"},
           "head": {"sha": None, "branch": None,
                    "unmerged": {"count": unmerged[0], "base": unmerged[1]} if unmerged else None,
                    "unpushed": {"count": unpushed[0], "upstream": unpushed[1]} if unpushed else None},
           "stage": stage, "activeModule": active, "nextGate": None, "history": "complete", "totals": totals,
           "bottlenecks": [{"id": b, "suspendedReason": None, "blocks": list(ids)} for b, ids in bottlenecks],
           "awaitingReview": [], "modules": modules}
    return specguard.parse_map(json.dumps(doc))


class MapCase(TempHomeTestCase):
    def setUp(self):
        super().setUp()
        self.g, _ = store.init_group("demo")
        people = [("hub", "收件枢纽", "hub", [], "claude-desktop", None),
                  ("fe-codex", "前端", "dev", ["前端"], "codex-desktop", "/r/fe"),
                  ("api-codex", "API", "dev", ["API"], "codex-desktop", "/r/api"),
                  ("bg-codex", "后台", "dev", ["后台"], "codex-desktop", "/r/bg"),
                  ("fe-owner", "前端负责人", "owner", ["前端"], "claude-desktop", None),
                  ("coord", "总协调", "coordinator", [], "codex-desktop", None)]
        with self.g.transaction() as tx:
            for name, short, role, line, host, repo in people:
                entry = {"relayName": name, "shortName": short, "role": role, "line": line, "host": host}
                if repo:
                    entry["repo"] = repo
                tx.add_session(entry)
        self.fe = store.find_session(self.g, relay_name="fe-codex")

    def register(self):
        reviews.register(self.g, session="fe-codex", reviewer="fe-owner", nodes=("spec", "plan"),
                         approval_item=None, approval_note="接入时用户确认", at=at(300))

    def conclude(self, verdict, ref, node="Spec", module=None, minutes_ago=60):
        extra = f"模块：{module}\n" if module else ""
        msg = protocol.parse(f"【审查结论】\n审查编号：{ref}\n节点：{node}\n{extra}送审方：前端\n结论：{verdict}\n")
        self.assertTrue(reviews.record_conclusion(self.g, msg, sender="fe-owner", at=at(minutes_ago)).recorded)

    def wait(self, waiter, target, minutes_ago, what="订单接口"):
        text = f"【等待其他会话】\n结束：无\n在等谁：{target}\n等什么：{what}\n"
        return tickets.receive(self.g, text, sender=waiter, relay_id=1, sent_at=at(minutes_ago)).opened

    def ask(self, sender="fe-codex", text=WAIT_USER):
        return items.receive(self.g, text, sender=sender, relay_id=2, received_at=at(5)).item


class HeaderTest(MapCase):
    def test_three_lines(self):
        self.register()
        line = make_map([module_doc("a", 1), module_doc("pay", 2, "in_progress", "build", 6, 11),
                         module_doc("cart", 3, "suspended", reason="等设计稿", blocks=("x", "y")),
                         module_doc("x", 4, "blocked", blocked_on=("cart",)), module_doc("y", 5, "not_ready")],
                        active="pay", bottlenecks=[("cart", ("x", "y")), ("z", ("q",))], unpushed=(2, "origin/fe"))
        self.assertEqual(mapview.header_lines(self.g, NOW, self.fe, line), [
            "前端 · 5 个模块 · ✅ 1 🔨 1 ⏸ 1 ⛔ 1 🟢 0 ○ 1 · 更新于 " + mapview._clock("2026-10-16T11:37:00+08:00"),
            "关键卡点：cart 挂起 → 挡住 2 个模块；z 挂起 → 挡住 1 个模块",
            "未合入主线：91 个提交（相对 origin/main）；未推送：2 个提交（相对 origin/fe）",
        ])

    def test_asks_unknowns_and_fourth_line(self):
        own = self.ask("fe-codex")
        multi = self.ask("coord", MULTI)
        self.ask("api-codex")
        self.wait("fe-codex", "API", 40)
        self.wait("fe-codex", "用户", 40)
        line = make_map([module_doc("a", 1)], active=None, unmerged=None)
        head = mapview.header_lines(self.g, NOW, self.fe, line)
        self.assertEqual(head[1], f"关键卡点：无 · 等你决定：#{own}、#{multi}")
        self.assertEqual(head[2], "未合入主线：判断不了；未推送：判断不了")
        self.assertEqual(head[3], "外部等待：等 API 交付「订单接口」（已等 40 分钟） · 架构审查：本线无审查者")

    def test_unmarked_reviews(self):
        self.register()
        self.conclude("有须修改项", "R-1", module="pay")
        self.conclude("有须修改项", "R-2")
        self.conclude("通过", "R-3")
        head = mapview.header_lines(self.g, NOW, self.fe, make_map([module_doc("pay", 1)], active="pay"))
        self.assertEqual(head[3], "架构审查：未标模块的审查 2 个")

    def test_no_fourth_line(self):
        self.register()
        self.wait("fe-codex", "API", 40)
        head = mapview.header_lines(self.g, NOW, self.fe, make_map([module_doc("pay", 1, "in_progress", "build")],
                                                                   active="pay"))
        self.assertEqual(len(head), 3)

    def test_note_only_on_current_module(self):
        self.wait("fe-codex", "API", 90, what="订单接口的 Mock 数据，\n  交付后我才能接着做")
        self.wait("fe-codex", "用户", 5)
        line = make_map([module_doc("a", 1), module_doc("pay", 2, "in_progress", "build")], active="pay")
        self.assertEqual(mapview.note_cell(self.g, NOW, self.fe, line, line.modules[1]),
                         "外部等待：等 API 交付「订单接口的 Mock 数据，交付后我才能接着做」（已等 1 小时）")
        self.assertEqual(mapview.note_cell(self.g, NOW, self.fe, line, line.modules[0]), "")


class TableTest(MapCase):
    def scenario(self):
        self.register()
        self.conclude("通过，附建议1条", "R-1", "Spec", module="pay")
        self.conclude("有须修改项", "R-2", "Plan", module="pay", minutes_ago=50)
        self.conclude("有须修改项", "R-2", "Plan", module="pay", minutes_ago=40)
        self.conclude("通过", "R-9", "Spec")
        self.wait("fe-codex", "API", 40)
        own = self.ask("fe-codex")
        line = make_map([
            module_doc("a", 1, last_tick="2026-10-16T10:00:00+08:00"),
            module_doc("b", 2, last_tick="2026-10-16T11:00:00+08:00"),
            module_doc("c", 3),
            module_doc("pay", 4, "in_progress", "build", 6, 11, responsibility="支付页：接微信与支付宝，" + "长" * 30),
            module_doc("cart", 5, "suspended", reason="等设计稿", blocks=("x", "z")),
            module_doc("x", 6, "blocked", blocked_on=("cart",), spec="pending", plan="none"),
            module_doc("y", 7, "ready", spec="none", plan="none"),
            module_doc("z", 8, "not_ready", missing=("x",), spec="none", plan="none"),
            module_doc("w", 9, "not_ready", missing=("y",), spec="none", plan="none"),
        ], active="pay", bottlenecks=[("cart", ("x", "z"))])
        return own, line

    def test_default_view_exact(self):
        own, line = self.scenario()
        clock = mapview._clock("2026-10-16T11:37:00+08:00")
        expected = "\n".join([
            f"前端 · 9 个模块 · ✅ 3 🔨 1 ⏸ 1 ⛔ 1 🟢 1 ○ 2 · 更新于 {clock}",
            f"关键卡点：cart 挂起 → 挡住 2 个模块 · 等你决定：#{own}",
            "未合入主线：91 个提交（相对 origin/main）；未推送：判断不了",
            "架构审查：未标模块的审查 1 个",
            "",
            "| 位 | 编号 | 作用 | 状态 | Spec/Plan 评审 | 架构审查 | 备注 |",
            "|---|---|---|---|---|---|---|",
            "| 1–3 | 其余 2 个已完成 | | ✅ | | | |",
            "| 2 | b | b 的作用 | ✅ 已完成 | Spec ✔ Plan ✔ | — |  |",
            "| 4 | pay | 支付页：接微信与支付宝，" + "长" * 28 + "… | 🔨 进行中 6/11 | Spec ✔ Plan ✔ | "
            "Spec 通过，附建议1条 · Plan 有须修改项（第 2 轮） | 外部等待：等 API 交付「订单接口」（已等 40 分钟） |",
            "| 5 | cart | cart 的作用 | ⏸ 挂起：等设计稿 · 挡住 2 个 | Spec ✔ Plan ✔ | — |  |",
            "| 6 | x | x 的作用 | ⛔ 阻塞：等 cart | Spec 待审 Plan — | — |  |",
            "| 7 | y | y 的作用 | 🟢 可以开始 | Spec — Plan — | — |  |",
            "| 8–9 | 2 个未就绪 | | ○ | | | |",
        ])
        self.assertMultiLineEqual(mapview.render_table(self.g, NOW, self.fe, line), expected)

    def test_full_has_no_merged_rows(self):
        _, line = self.scenario()
        rows = mapview.table_rows(self.g, NOW, self.fe, line, full=True)
        self.assertEqual(len(rows), 1 + 9)  # column header block + one row per module
        self.assertFalse(any("其余" in r or "个未就绪 |" in r for r in rows))
        self.assertIn("| 8 | z | z 的作用 | ○ 未就绪：缺 x |", "\n".join(rows))

    def test_latest_done_without_ticks_is_highest_position(self):
        line = make_map([module_doc("a", 1), module_doc("b", 2), module_doc("c", 5)])
        rows = mapview.table_rows(self.g, NOW, self.fe, line)
        self.assertEqual(rows[1:], ["| 1–2 | 其余 2 个已完成 | | ✅ | | | |",
                                    "| 5 | c | c 的作用 | ✅ 已完成 | Spec ✔ Plan ✔ | — |  |"])

    def test_single_folded_position(self):
        line = make_map([module_doc("a", 1), module_doc("b", 2, last_tick="2026-10-16T11:00:00+08:00"),
                         module_doc("z", 3, "not_ready", missing=("q",))])
        rows = mapview.table_rows(self.g, NOW, self.fe, line)
        self.assertEqual(rows[1], "| 1 | 其余 1 个已完成 | | ✅ | | | |")
        self.assertEqual(rows[3], "| 3 | 1 个未就绪 | | ○ | | | |")

    def test_real_fixture(self):
        line = specguard.parse_map((Path(__file__).resolve().parent / "fixtures" / "specguard" /
                                    "map-0.63.json").read_text(encoding="utf-8"))
        text = mapview.render_table(self.g, NOW, self.fe, line)
        self.assertIn("| spec-guard-reader |", text)
        self.assertIn("🔨 进行中 1/6", text)
        self.assertIn("未合入主线：3 个提交（相对 origin/main）；未推送：判断不了", text)


if __name__ == "__main__":
    unittest.main()
