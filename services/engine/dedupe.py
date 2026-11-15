"""Step 1: one item per real-world filing.

- The same announcement on NSE and BSE is merged (same symbol, within 10 minutes, similar subject).
- A revised / corrigendum / addendum filing becomes the latest version; the original is linked, not shown.
"""
import re
from datetime import timedelta
from difflib import SequenceMatcher
from .models import Filing

WINDOW = timedelta(minutes=10)
AMEND_LOOKBACK = timedelta(days=30)
_AMEND = re.compile(r"\b(revised|revision|corrigendum|addendum|amendment|amended|rectif\w+|erratum)\b", re.I)
_NOISE = re.compile(r"\b(revised|revision|corrigendum|addendum|amendment|amended|rectif\w+|erratum|to|of|the|for|under|regulation|reg|sebi|lodr|\d+)\b|[^a-z ]", re.I)


def _norm(s: str) -> str:
    return " ".join(_NOISE.sub(" ", s.lower()).split())


def similar(a: str, b: str) -> float:
    """Exchanges word the same filing differently and in a different order, so compare word sets
    (share of the shorter subject's words found in the other) as well as the character sequence."""
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return 0.0
    ta, tb = set(na.split()), set(nb.split())
    overlap = len(ta & tb) / min(len(ta), len(tb))
    return max(overlap, SequenceMatcher(None, na, nb).ratio())


def is_amendment(f: Filing) -> bool:
    return bool(_AMEND.search(f.subject) or _AMEND.search(f.body[:300]))


def merge_exchanges(filings: list[Filing], threshold: float = 0.6) -> list[Filing]:
    """Keep the earliest copy; record the other exchange's id on it. NSE wins a tie (richer XBRL links)."""
    out: list[Filing] = []
    for f in sorted(filings, key=lambda x: (x.filed_at, x.exchange != "NSE")):
        twin = next((k for k in reversed(out)
                     if k.symbol == f.symbol and k.exchange != f.exchange
                     and abs(k.filed_at - f.filed_at) <= WINDOW
                     and (similar(k.subject, f.subject) >= threshold or (k.pdf_url and k.pdf_url == f.pdf_url))), None)
        if twin:
            twin.also_on.append(f.id)
            if not twin.pdf_url:
                twin.pdf_url = f.pdf_url
            if len(f.body) > len(twin.body):
                twin.body = f.body
        else:
            out.append(f)
    return out


def link_amendments(filings: list[Filing], threshold: float = 0.6) -> list[Filing]:
    """Mark originals as superseded. Returns all filings; callers show only `superseded_by is None`."""
    ordered = sorted(filings, key=lambda x: x.filed_at)
    for i, f in enumerate(ordered):
        if not is_amendment(f):
            continue
        for prior in reversed(ordered[:i]):
            if f.filed_at - prior.filed_at > AMEND_LOOKBACK:
                break
            if prior.symbol == f.symbol and prior.superseded_by is None and similar(prior.subject, f.subject) >= threshold:
                f.amends, prior.superseded_by = prior.id, f.id
                break
    return ordered


def dedupe(filings: list[Filing]) -> list[Filing]:
    return link_amendments(merge_exchanges(filings))


def latest(filings: list[Filing]) -> list[Filing]:
    return [f for f in filings if f.superseded_by is None]
