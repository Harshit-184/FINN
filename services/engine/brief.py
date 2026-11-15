"""Assembles the Daily Brief from scored filings and alerts. Rules only; no model is needed to place an item."""
from datetime import datetime, timedelta
from .config import holdings
from .dedupe import latest
from .models import Alert, Filing

NEGATIVE = ("resign", "downgrad", "penalty", "show cause", "warning letter", "invocation", "creation of pledge", "tax demand", "default")
POSITIVE = ("upgrad", "order", "bags", "wins", "commissioning", "commencement")


def direction(f: Filing, alerts: list[Alert]) -> str:
    """positive / negative / mixed / neutral, from the filing text and the day's price move. A signal, not a verdict."""
    t = f"{f.subject} {f.body[:300]}".lower()
    signs = set()
    if any(k in t for k in NEGATIVE):
        signs.add("negative")
    if any(k in t for k in POSITIVE):
        signs.add("positive")
    for a in alerts:
        if a.symbol == f.symbol and a.d == f.filed_at.date() and a.rule == "price_move" and a.value:
            signs.add("positive" if a.value > 0 else "negative")
    return "mixed" if len(signs) > 1 else next(iter(signs), "neutral")


def card(f: Filing, alerts: list[Alert]) -> dict:
    h = holdings().get(f.symbol, {})
    pillar = next((p for p in h.get("pillars", []) if p["id"] == f.pillar), None)
    return {**f.model_dump(mode="json"), "company": h.get("name", f.symbol), "direction": direction(f, alerts),
            "pillar_name": pillar["name"] if pillar else None, "revised": f.amends is not None}


def headline(critical: list[dict], alerts: list[Alert], n_holdings: int) -> str:
    bits = [f"{c['symbol']} {c['category'].replace('_', ' ')}" for c in critical[:3]]
    seen = {c["symbol"] for c in critical[:3]}
    bits += [a.headline for a in alerts if a.rule in ("volume_spike", "price_move") and a.symbol not in seen][: 3 - len(bits)]
    if not bits:
        return f"Quiet day. 0 critical filings in your {n_holdings} holdings."
    return f"{len(bits)} thing{'s' if len(bits) > 1 else ''} matter{'' if len(bits) > 1 else 's'}: " + ", ".join(bits) + "."


def build(filings: list[Filing], alerts: list[Alert], now: datetime, window_hours: int = 24, last_session=None) -> dict:
    since = now - timedelta(hours=window_hours)
    note = None
    # On a weekend or holiday a strict 24h window is empty by construction. Reach back to the last trading session and say so.
    if last_session and last_session < since.date():
        since = datetime.combine(last_session, datetime.min.time())
        note = f"Markets have been closed since {last_session:%a %d %b}, so this covers that session onwards."
    shown = sorted((f for f in latest(filings) if since <= f.filed_at <= now and f.symbol in holdings()),
                   key=lambda f: (f.score, f.filed_at), reverse=True)
    al = [a for a in alerts if since.date() <= a.d <= now.date()]
    cards = [card(f, al) for f in shown]
    critical = [c for c in cards if c["tier"] == "critical"]
    attention: dict[str, dict] = {}
    for c in critical:
        e = attention.setdefault(c["symbol"], {"symbol": c["symbol"], "company": c["company"], "reasons": [], "directions": set()})
        e["reasons"].append(c["headline"] or c["subject"]); e["directions"].add(c["direction"])
    for a in al:
        e = attention.setdefault(a.symbol, {"symbol": a.symbol, "company": holdings().get(a.symbol, {}).get("name", a.symbol), "reasons": [], "directions": set()})
        if a.headline not in e["reasons"]:
            e["reasons"].append(a.headline)
        if a.rule == "price_move" and a.value:
            e["directions"].add("positive" if a.value > 0 else "negative")
    for e in attention.values():
        d = e.pop("directions") - {"neutral"}
        e["direction"] = "mixed" if len(d) > 1 else next(iter(d), "neutral")
    return {"as_of": now.isoformat(), "window_hours": window_hours, "note": note,
            "headline": headline(critical, al, len(holdings())),
            "needs_attention": list(attention.values()),
            "critical": critical,
            "notable": [c for c in cards if c["tier"] == "notable"],
            "routine": [c for c in cards if c["tier"] == "routine"],
            "alerts": [a.model_dump(mode="json") for a in al]}
