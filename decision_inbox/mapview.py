"""Read-only /map views over spec-guard's module table (see spec/map-view.md).

Module state comes only from spec-guard (via spec-guard-reader); this module
adds the architecture-review column, items waiting for the user and external
waits, and never changes a state spec-guard gave.
"""

from __future__ import annotations

from datetime import datetime

from decision_inbox import items, protocol, reviews, store, tickets

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


def arch_cell(cells) -> str:
    """Latest verdict of each review of this module, by node (spec 关键决策 5)."""
    return " · ".join(f"{_NODE_NAMES.get(r.node, r.node)} {_verdict(r)}" for r in cells) or "—"


_TOTAL_ICONS = (("done", "✅"), ("in_progress", "🔨"), ("suspended", "⏸"), ("blocked", "⛔"),
                ("ready", "🟢"), ("not_ready", "○"))


def _clock(value: str) -> str:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone().strftime("%H:%M")


def _waited(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes} 分钟"
    return f"{minutes // 60} 小时" if minutes < 24 * 60 else f"{minutes // (24 * 60)} 天"


def external_waits(g: store.Group, now: str, session: str) -> list[str]:
    """Open tickets of this line that wait on someone other than the user (spec 已定事项 3)."""
    return [f"外部等待：等 {t.target} 交付「{''.join(x.strip() for x in t.what.splitlines())}」（已等 {_waited(t.minutes)}）"
            for t in tickets.open_tickets(g, now) if t.waiter == session and t.target not in tickets.USER_TARGETS]


def _asks(g: store.Group, entry: dict) -> list[int]:
    return sorted(it["no"] for it in items.pending(g)
                  if it["sender"] == entry["relayName"] or (it["multi"] and entry["shortName"] in it["lines"]))


def header_lines(g: store.Group, now: str, entry: dict, line_map) -> list[str]:
    """Total line, bottlenecks and asks, unmerged/unpushed, and the optional fourth line (spec 关键决策 6)."""
    totals = line_map.totals
    counts = " ".join(f"{icon} {totals.get(key, 0)}" for key, icon in _TOTAL_ICONS)
    out = [f"{entry['shortName']} · {sum(totals.values())} 个模块 · {counts} · 更新于 {_clock(line_map.generated_at)}"]
    second = "关键卡点：" + ("；".join(f"{b.id} 挂起 → 挡住 {len(b.blocks)} 个模块" for b in line_map.bottlenecks) or "无")
    asks = _asks(g, entry)
    if asks:
        second += " · 等你决定：" + "、".join(f"#{no}" for no in asks)
    out.append(second)
    unmerged = (f"{line_map.unmerged_count} 个提交（相对 {line_map.unmerged_base}）"
                if line_map.unmerged_count is not None else "判断不了")
    unpushed = (f"{line_map.unpushed_count} 个提交（相对 {line_map.unpushed_upstream}）"
                if line_map.unpushed_count is not None else "判断不了")
    out.append(f"未合入主线：{unmerged}；未推送：{unpushed}")
    fourth = []
    if not any(m.id == line_map.active_module for m in line_map.modules):
        fourth += external_waits(g, now, entry["relayName"])
    if reviews.registration_at(g, entry["relayName"], now) is None:
        fourth.append("架构审查：本线无审查者")
    else:
        _, unmarked = reviews.module_reviews(g, entry["relayName"])
        if unmarked:
            fourth.append(f"架构审查：未标模块的审查 {len(unmarked)} 个")
    if fourth:
        out.append(" · ".join(fourth))
    return out


def note_cell(g: store.Group, now: str, entry: dict, line_map, m) -> str:
    """External waits go into the current module's note only (spec 已定事项 3)."""
    return "；".join(external_waits(g, now, entry["relayName"])) if m.id == line_map.active_module else ""
