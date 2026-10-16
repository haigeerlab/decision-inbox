import unittest

from decision_inbox import mapview
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


if __name__ == "__main__":
    unittest.main()
