"""Results card: headline metrics with QoQ / YoY, built only from verified facts."""
from .config import load, template_for
from .models import Check, Fact
from . import periods, verify

Store = dict[tuple[str, str, str], Fact]          # (metric, period, basis) -> Fact


def index(facts: list[Fact]) -> Store:
    return {(f.metric, f.period, f.basis): f for f in facts}


def ebitda(store: Store, company: str, period: str, basis: str) -> Fact | None:
    """PBT + finance costs + depreciation - other income, before exceptional items. Same definition every quarter."""
    need = {m: store.get((m, period, basis)) for m in ("pbt", "finance_costs", "depreciation", "other_income")}
    if any(v is None for v in need.values()):
        return None
    exc = store.get(("exceptional", period, basis))
    value = need["pbt"].value - (exc.value if exc else 0.0) + need["finance_costs"].value \
        + need["depreciation"].value - need["other_income"].value
    return Fact(company=company, metric="ebitda", value=round(value, 2), period=period, basis=basis,
                source_type="derived", document=need["pbt"].document, evidence="reported", confidence="medium")


def results_card(company: str, period: str, facts: list[Fact], basis: str = "consolidated") -> dict:
    store = index(facts)
    template = template_for(company)
    if template == "standard":
        for p in (period, periods.prev_quarter(period), periods.year_ago(period)):
            if (e := ebitda(store, company, p, basis)):
                store[("ebitda", p, basis)] = e
    checks: list[Check] = []
    pbt, tax, pat = (store.get((m, period, basis)) for m in ("pbt", "tax", "pat"))
    if pbt and tax and pat:
        checks.append(verify.pat_identity(pbt.value, tax.value, pat.value))

    rows = []
    for metric in load("metrics")["headline"][template]:
        cur = store.get((metric, period, basis))
        if cur is None:
            rows.append({"metric": metric, "value": None, "note": "not in the filing"})
            continue
        row = {"metric": metric, "label": load("metrics")["metrics"][metric]["label"],
               "value": cur.value, "source": cur.source_type, "evidence": cur.evidence}
        for key, ref_period in (("qoq", periods.prev_quarter(period)), ("yoy", periods.year_ago(period))):
            ref = store.get((metric, ref_period, basis))
            row[key] = None
            if ref is None:
                continue
            c = verify.comparable(cur, ref)
            change = verify.pct_change(cur.value, ref.value) if c.ok else None
            sane = verify.range_sanity(change)
            if not c.ok or not sane.ok:
                checks.append(c if not c.ok else sane)
            row[key] = None if change is None else round(change, 1)       # shown, but held at Medium if out of range
        rows.append(row)

    margin = None
    if template == "standard":
        def m(p):
            e, r = store.get(("ebitda", p, basis)), store.get(("revenue", p, basis))
            return 100 * e.value / r.value if e and r and r.value else None
        now, yago = m(period), m(periods.year_ago(period))
        margin = {"pct": None if now is None else round(now, 1),
                  "yoy_bps": None if now is None or yago is None else round((now - yago) * 100)}

    main_source = pat.source_type if pat else "xbrl"
    conf = verify.confidence(main_source, checks)
    return {"company": company, "period": period, "basis": basis, "template": template, "rows": rows,
            "ebitda_margin": margin, "checks": [c.model_dump() for c in checks], "confidence": conf,
            "reconciles": all(c.ok for c in checks if c.name == "arithmetic")}
