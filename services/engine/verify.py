"""Layer 4: verification. Runs on every extracted number before it can reach a card, a score or a verdict."""
from .config import load
from .models import Check, Confidence, Fact


def to_crore(value: float, scale: str) -> float:
    """Convert a reported figure to INR crore. Unknown scale => the record is rejected."""
    table = load("metrics")["scale_to_crore"]
    key = scale.strip().lower()
    if key not in table:
        raise ValueError(f"unknown unit scale: {scale!r}")
    return value * table[key]


def pct_change(new: float, old: float) -> float | None:
    if old is None or new is None or old == 0:
        return None
    return 100.0 * (new - old) / abs(old)


def pat_identity(pbt: float, tax: float, pat: float) -> Check:
    tol = load("metrics")["tolerances"]["pat_identity_pct"]
    gap = abs((pbt - tax) - pat)
    ok = gap <= max(abs(pat) * tol / 100, 0.5)        # 0.5 cr floor for rounding in small numbers
    return Check(name="arithmetic", ok=ok, detail=f"PBT {pbt:,.0f} - tax {tax:,.0f} vs PAT {pat:,.0f} (gap {gap:,.1f} cr)")


def comparable(a: Fact, b: Fact) -> Check:
    """Two facts may be compared only on the same metric, unit, basis and period type."""
    for attr in ("metric", "unit", "basis", "period_type"):
        if getattr(a, attr) != getattr(b, attr):
            return Check(name="alignment", ok=False, detail=f"{attr}: {getattr(a, attr)} vs {getattr(b, attr)}")
    return Check(name="alignment", ok=True)


def range_sanity(change_pct: float | None) -> Check:
    lim = load("metrics")["tolerances"]["range_sanity_pct"]
    ok = change_pct is None or abs(change_pct) <= lim
    return Check(name="range", ok=ok, detail="" if ok else f"change of {change_pct:+.0f}% is outside +/-{lim:.0f}%")


def cross_source(primary: Fact, other: Fact, tol_pct: float = 0.5) -> Check:
    """XBRL is the value shown; a second source only confirms or flags."""
    gap = pct_change(other.value, primary.value)
    ok = gap is not None and abs(gap) <= tol_pct
    return Check(name="cross_source", ok=ok,
                 detail=f"{primary.source_type} {primary.value:,.1f} vs {other.source_type} {other.value:,.1f}")


def confidence(source_type: str, checks: list[Check]) -> Confidence:
    """High: directly reported and every check passed. Medium: derived, or held by range sanity.
    Low: arithmetic or cross-source disagreement, or an LLM-read number."""
    failed = {c.name for c in checks if not c.ok}
    if failed & {"arithmetic", "cross_source"} or source_type == "pdf_llm" and failed:
        return "low"
    if failed or source_type in ("derived", "pdf_llm", "screener"):    # a compiled copy is not the filing itself
        return "medium"
    return "high"
