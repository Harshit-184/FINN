"""Step 6: alerts. Evaluated after each EOD fetch / announcement poll. One alert per rule, per stock, per day."""
from datetime import date
from .config import load
from .models import Alert, Bar, Filing


def thresholds(symbol: str, user_rules: dict | None = None) -> dict:
    cfg = dict(load("categories")["alerts"])
    cfg.update((user_rules or {}).get("global", {}))
    cfg.update(load("categories")["alerts"].get("per_stock", {}).get(symbol, {}))
    cfg.update((user_rules or {}).get("per_stock", {}).get(symbol, {}))
    return cfg


def avg_volume(bars: list[Bar], d: date, window: int) -> float | None:
    """Mean volume of the `window` trading sessions before d. Suspended (zero-volume) sessions are skipped."""
    prior = [b.volume for b in bars if b.d < d and b.volume > 0][-window:]
    return sum(prior) / len(prior) if len(prior) >= window // 2 else None


def price_volume_alerts(symbol: str, bars: list[Bar], d: date, rules: dict | None = None) -> list[Alert]:
    t = thresholds(symbol, rules)
    bars = sorted(bars, key=lambda b: b.d)
    today = next((b for b in bars if b.d == d), None)
    prev = next((b for b in reversed(bars) if b.d < d), None)
    out: list[Alert] = []
    if not today or not prev:
        return out
    avg = avg_volume(bars, d, t["volume_window"])
    if avg and today.volume / avg > t["volume_multiple"]:
        mult = today.volume / avg
        out.append(Alert(symbol=symbol, d=d, rule="volume_spike", value=round(mult, 2), threshold=t["volume_multiple"],
                         headline=f"{symbol} volume {mult:.1f}x its {t['volume_window']}-day average"))
    move = 100 * (today.close - prev.close) / prev.close
    if abs(move) > t["price_move_pct"]:
        out.append(Alert(symbol=symbol, d=d, rule="price_move", value=round(move, 2), threshold=t["price_move_pct"],
                         headline=f"{symbol} {move:+.1f}% close-to-close"))
    return out


def filing_alerts(filings: list[Filing], rules: dict | None = None) -> list[Alert]:
    out = []
    for f in filings:
        if f.superseded_by is None and f.category in thresholds(f.symbol, rules)["material_categories"]:
            out.append(Alert(symbol=f.symbol, d=f.filed_at.date(), rule="material_filing", filing_ids=[f.id],
                             headline=f"{f.symbol}: {f.category.replace('_', ' ')} filing"))
    return out


def combine(alerts: list[Alert], filings: list[Filing]) -> list[Alert]:
    """Apply the cooldown, then add a combo alert when price/volume fires on a Critical-filing day."""
    folded: dict[tuple, Alert] = {}
    for a in alerts:
        key = (a.symbol, a.d, a.rule)
        if key in folded:
            folded[key].folded += 1
            folded[key].filing_ids += [i for i in a.filing_ids if i not in folded[key].filing_ids]
        else:
            folded[key] = a.model_copy(deep=True)
    critical = {}
    for f in filings:
        if f.tier == "critical" and f.superseded_by is None:
            critical.setdefault((f.symbol, f.filed_at.date()), []).append(f.id)
    out = list(folded.values())
    for (sym, d), ids in critical.items():
        moves = [a for a in out if a.symbol == sym and a.d == d and a.rule in ("volume_spike", "price_move")]
        if moves:
            out.append(Alert(symbol=sym, d=d, rule="combo", filing_ids=ids,
                             headline=f"{sym}: critical filing and {' + '.join(a.rule.replace('_', ' ') for a in moves)} on the same day"))
    return sorted(out, key=lambda a: (a.d, a.symbol, a.rule), reverse=True)
