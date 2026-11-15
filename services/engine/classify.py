"""Step 2: classify a filing into one of the 17 reference categories.

Rules first (free, deterministic). Anything the rules cannot place is returned as
`unclassified` with classified_by="none" so the caller can send only those to the cheap model.
"""
import re
from functools import lru_cache
from .config import load
from .models import Filing


@lru_cache
def _rules():
    out = []
    for r in load("categories")["rules"]:
        comp = lambda pats: [re.compile(p, re.I) for p in pats or []]
        out.append((r["category"], comp(r.get("any")), comp(r.get("all")), comp(r.get("none")), r.get("why", "")))
    return out


def haystack(f: Filing) -> str:
    return " | ".join(x for x in (f.raw_category, f.subject, f.body[:600]) if x)


_BOILER = re.compile(r"^.{0,90}? has (?:informed|submitted to) the Exchange,?\s*(?:about|regarding|that)?\s*", re.I)


def headline(f: Filing) -> str:
    """NSE bodies start 'X Limited has informed the Exchange regarding ...'. Keep what follows; fall back to the subject."""
    text = _BOILER.sub("", f.body).strip(" '.\"")
    text = text[:1].upper() + text[1:]
    if len(text) < 6 or text.lower() == f.subject.lower():
        return f.subject
    return text if len(text) <= 160 else text[:157].rsplit(" ", 1)[0] + "…"


def classify(f: Filing) -> Filing:
    f.headline = headline(f)
    text = haystack(f)
    for category, any_, all_, none_, why in _rules():
        hit = next((p for p in any_ if p.search(text)), None)
        if not hit:
            continue
        if any(p.search(text) for p in none_) or not all(p.search(text) for p in all_):
            continue
        f.category, f.classified_by = category, "rule"
        f.rule_why = why or f"matched /{hit.pattern}/"
        return f
    f.category, f.classified_by, f.rule_why = "unclassified", "none", "no rule matched"
    return f


def needs_llm(f: Filing) -> bool:
    return f.classified_by == "none"
