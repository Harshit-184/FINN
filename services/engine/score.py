"""Step 4: priority = 0.30 M + 0.20 S + 0.20 T + 0.15 P + 0.15 C  (0-100). No LLM anywhere in here."""
import re
from .config import load, holdings
from .classify import haystack
from .models import Filing

_AMOUNT = re.compile(r"(?:rs\.?|inr|₹)\s*([\d,]+(?:\.\d+)?)\s*(crores?|cr\b|lakhs?|lacs?|million|mn\b|billion|bn\b)", re.I)
_TO_CR = {"crore": 1, "crores": 1, "cr": 1, "lakh": 0.01, "lakhs": 0.01, "lac": 0.01, "lacs": 0.01,
          "million": 0.1, "mn": 0.1, "billion": 100, "bn": 100}


def amount_cr(text: str) -> float | None:
    """Largest rupee amount mentioned, in Rs crore. Used only for the severity size band."""
    vals = [float(m[1].replace(",", "")) * _TO_CR[m[2].lower()] for m in _AMOUNT.finditer(text)]
    return max(vals) if vals else None


def materiality(f: Filing) -> float:
    return float(load("categories")["materiality"][f.category])


def severity(f: Filing, market_cap_cr: float | None = None) -> float:
    cfg = load("categories")["severity"]
    spec = cfg.get(f.category) or {}
    text = haystack(f)
    s = spec.get("default", cfg["default"])
    for r in spec.get("rules", []):
        if any(re.search(p, text, re.I) for p in r["any"]):
            s = r["score"]
            break
    f.amount_cr = amount_cr(text)
    if f.amount_cr and market_cap_cr and f.category in ("m_and_a", "fund_raise", "capex", "litigation"):
        pct = 100 * f.amount_cr / market_cap_cr
        for band in load("categories")["size_bands"]:
            if pct >= band["pct"]:
                s = max(s, band["score"])
                break
    return float(s)


def thesis(f: Filing) -> float:
    """100 if a configured pillar keyword appears, 50 for a core-business category, else 0."""
    h = holdings().get(f.symbol)
    if not h:
        return 0.0
    text = haystack(f).lower()
    for p in h.get("pillars", []):
        kw = next((k for k in p["keywords"] if re.search(rf"\b{re.escape(k)}", text)), None)
        if kw:
            f.pillar, f.pillar_evidence = p["id"], kw
            return 100.0
    return 50.0 if f.category in ("results", "capex", "m_and_a", "press_release") else 0.0


def exposure(symbol: str) -> float:
    """Demo weight scaled so the largest holding is 100."""
    hs = holdings()
    if symbol not in hs:
        return 0.0
    return 100.0 * hs[symbol]["weight"] / max(h["weight"] for h in hs.values())


def score(f: Filing, market_cap_cr: float | None = None) -> Filing:
    cfg = load("categories")
    terms = {
        "M": materiality(f),
        "S": severity(f, market_cap_cr),
        "T": thesis(f),
        "P": exposure(f.symbol),
        "C": float(cfg["confidence_score"][f.confidence]),
    }
    f.score_terms = terms
    f.score = round(sum(cfg["weights"][k] * v for k, v in terms.items()), 1)
    t = cfg["tiers"]
    f.tier = "critical" if f.score >= t["critical"] else "notable" if f.score >= t["notable"] else "routine"
    # A small holding never hides a serious risk.
    if f.category in cfg["override_categories"] and terms["S"] >= cfg["override_severity"]:
        f.tier = "critical"
        f.score_terms["override"] = 1.0
    # Unclassified compliance noise is never promoted by exposure alone.
    if f.category == "unclassified":
        f.tier = "routine"
    return f
