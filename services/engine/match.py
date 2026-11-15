"""Promised vs Delivered: match each guidance item to verified actuals. Code only, no model.

Seven statuses. Silence is not a status: a target that is not repeated gets a note, never a verdict.
A full-year target is judged only against full-year actuals; before year-end it is Pending with YTD progress.
"""
from typing import Literal
from pydantic import BaseModel
from . import periods
from .models import Fact, GuidanceItem

Status = Literal["delivered", "partially_delivered", "missed", "pending", "revised", "withdrawn", "not_verifiable"]
PARTIAL_BAND = 0.20            # shortfall of up to 20% of the target still counts as partial
LOWER_IS_BETTER = {"net_debt", "credit_cost", "gnpa", "attrition", "working_capital_days"}


class Verdict(BaseModel):
    item: GuidanceItem
    status: Status
    actual: float | None = None
    actual_basis: str = ""                 # how the actual was computed, in words
    progress: str = ""                     # for Pending
    replaced_by: GuidanceItem | None = None
    note: str = ""
    evidence: list[Fact] = []


def order(period: str) -> tuple[int, int]:
    q, fy = periods.parse(period)
    return (fy, q or 5)


def _get(facts: dict, metric: str, period: str) -> Fact | None:
    return facts.get((metric, period))


def _annual(facts: dict, metric: str, fy: str) -> tuple[float | None, list[Fact], int]:
    """Full-year value: the annual fact if present, else the sum of four quarters. Returns quarters found too."""
    if (a := _get(facts, metric, fy)):
        return a.value, [a], 4
    qs = [f for p in periods.quarters_of(fy) if (f := _get(facts, metric, p))]
    return (sum(f.value for f in qs) if len(qs) == 4 else None), qs, len(qs)


def _actual(item: GuidanceItem, facts: dict) -> tuple[float | None, str, list[Fact], str]:
    """-> (actual in the target's unit, how, evidence, YTD progress text if the year is incomplete)."""
    q, _ = periods.parse(item.period)
    if q is not None:                                   # quarterly target
        cur = _get(facts, item.metric, item.period)
        if item.kind == "growth":
            ref = _get(facts, item.metric, periods.year_ago(item.period))
            if cur and ref and ref.value:
                return 100 * (cur.value / ref.value - 1), f"{item.period} vs {ref.period}", [cur, ref], ""
            return None, "", [], ""
        return (cur.value, item.period, [cur], "") if cur else (None, "", [], "")

    fy, prev = item.period, periods.year_ago(item.period)
    if item.kind == "margin":                           # metric is e.g. "ebitda": margin = metric / revenue
        num, ev1, n1 = _annual(facts, item.metric, fy)
        den, ev2, n2 = _annual(facts, "revenue", fy)
        if num is not None and den:
            return 100 * num / den, f"{item.metric} / revenue, {fy}", ev1 + ev2, ""
        n = min(n1, n2)
        if n:
            ytd = 100 * sum(f.value for f in ev1[:n]) / sum(f.value for f in ev2[:n])
            return None, "", ev1[:n] + ev2[:n], f"{ytd:.1f}% over the first {n} quarter(s) of {fy}"
        return None, "", [], ""
    cur, ev, n = _annual(facts, item.metric, fy)
    if item.kind == "absolute":
        if cur is not None:
            return cur, f"{fy} full year", ev, ""
        return None, "", ev, (f"{sum(f.value for f in ev):,.0f} cr after {n} quarter(s) of {fy}" if n else "")
    # growth
    base, ev0, _ = _annual(facts, item.metric, prev)
    if cur is not None and base:
        return 100 * (cur / base - 1), f"{fy} vs {prev}", ev + ev0, ""
    if n:
        same = [f for p in periods.quarters_of(prev)[:n] if (f := _get(facts, item.metric, p))]
        if len(same) == n and sum(f.value for f in same):
            ytd = 100 * (sum(f.value for f in ev) / sum(f.value for f in same) - 1)
            return None, "", ev + same, f"{ytd:+.1f}% YoY over the first {n} quarter(s) of {fy}"
    return None, "", [], ""


def _judge(item: GuidanceItem, actual: float) -> Status:
    lo, hi = item.low, item.high
    if item.metric in LOWER_IS_BETTER:
        if actual <= hi:
            return "delivered"
        return "partially_delivered" if actual <= hi + PARTIAL_BAND * abs(hi) else "missed"
    if actual >= lo:
        return "delivered"
    return "partially_delivered" if actual >= lo - PARTIAL_BAND * abs(lo) else "missed"


def scorecard(items: list[GuidanceItem], facts: list[Fact], latest_transcript: str | None = None) -> list[Verdict]:
    fx = {(f.metric, f.period): f for f in facts}
    by_target: dict[tuple, list[GuidanceItem]] = {}
    for it in sorted(items, key=lambda i: order(i.stated_in)):
        chain = by_target.setdefault((it.metric, it.kind, it.period), [])
        if chain and chain[-1].stated_in == it.stated_in:          # said twice on the same call (remarks, then Q&A)
            continue
        chain.append(it)

    out: list[Verdict] = []
    for chain in by_target.values():
        # Earlier statements whose numbers management later changed are Revised (old and new both shown).
        for old, new in zip(chain, chain[1:]):
            if new.withdrawn:
                continue
            if new.supersedes_explicitly or (new.low, new.high) != (old.low, old.high):
                out.append(Verdict(item=old, status="revised", replaced_by=new))
        live = chain[-1]
        if live.withdrawn:
            out.append(Verdict(item=live, status="withdrawn"))
            continue
        actual, how, ev, progress = _actual(live, fx)
        if live.caveat:
            # The filed statements cannot measure this target (e.g. constant-currency growth), so the reported
            # figure is shown as context and never turned into Delivered or Missed.
            shown = f"{actual:+.1f}% ({how})" if actual is not None else progress
            v = Verdict(item=live, status="not_verifiable" if actual is not None else "pending", evidence=ev,
                        note=(f"Reported figure for context: {shown}. " if shown else "") + live.caveat)
        elif actual is not None:
            v = Verdict(item=live, status=_judge(live, actual), actual=round(actual, 2), actual_basis=how, evidence=ev)
        elif progress:
            v = Verdict(item=live, status="pending", progress=progress, evidence=ev)
        else:
            v = Verdict(item=live, status="not_verifiable", note="No verified actuals for this metric and period.")
        if latest_transcript and v.status == "pending" and order(live.stated_in) < order(latest_transcript):
            v.note = (v.note + " " if v.note else "") + f"Not reiterated in the latest available transcript ({periods.label(latest_transcript)})."
        out.append(v)
    return out
