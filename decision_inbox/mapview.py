"""Read-only /map views over spec-guard's module table (see spec/map-view.md).

Module state comes only from spec-guard (via spec-guard-reader); this module
adds the architecture-review column, items waiting for the user and external
waits, and never changes a state spec-guard gave.
"""

from __future__ import annotations

from decision_inbox import protocol

_NODE_NAMES = {code: name for name, code in protocol.REVIEW_NODES.items()}
_REVIEW_MARKS = {"approved": "✔", "pending": "待审", "revised": "已改待复审", "invalid": "标记无效", "none": "—"}
_STEPS = {"spec": "写 Spec", "plan": "写 Plan"}


def status_cell(m) -> str:
    """Icon plus reason, all from spec-guard's fields (spec 关键决策 3)."""
    if m.status == "done":
        return "✅ 已完成"
    if m.status == "in_progress":
        return f"🔨 {_STEPS.get(m.step, f'进行中 {m.progress_done}/{m.progress_total}')}"
    if m.status == "suspended":
        return f"⏸ 挂起：{m.suspended_reason or '未记原因'} · 挡住 {len(m.blocks)} 个"
    if m.status == "blocked":
        return f"⛔ 阻塞：等 {'、'.join(m.blocked_on)}"
    if m.status == "ready":
        return "🟢 可以开始"
    if m.status == "not_ready":
        return f"○ 未就绪：缺 {'、'.join(m.missing_deps)}"
    return m.status


def review_cell(m) -> str:
    return f"Spec {_REVIEW_MARKS.get(m.review_spec, m.review_spec)} Plan {_REVIEW_MARKS.get(m.review_plan, m.review_plan)}"


def _verdict(r) -> str:
    if r.verdict == "passed":
        return "通过"
    if r.verdict == "passed-with-advice":
        return f"通过，附建议{r.advice_count}条"
    return f"有须修改项（第 {r.rounds} 轮）"


def arch_cell(reviews) -> str:
    """Latest verdict of each review of this module, by node (spec 关键决策 5)."""
    return " · ".join(f"{_NODE_NAMES.get(r.node, r.node)} {_verdict(r)}" for r in reviews) or "—"
