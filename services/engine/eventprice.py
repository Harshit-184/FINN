"""Event-to-price strip. Timing association, not cause — the UI says so on every strip."""
from datetime import datetime, time
from .alerts import avg_volume
from .models import Bar

MARKET_CLOSE = time(15, 30)


def strip(bars: list[Bar], filed_at: datetime, window: int = 20) -> dict | None:
    bars = sorted(bars, key=lambda b: b.d)
    # A filing after the close cannot have moved that day's close, so that close is the "before" price.
    after_close = filed_at.time() >= MARKET_CLOSE
    before = [b for b in bars if (b.d <= filed_at.date() if after_close else b.d < filed_at.date())]
    after = [b for b in bars if (b.d > filed_at.date() if after_close else b.d >= filed_at.date())]
    if not before:
        return None
    base = before[-1]

    def leg(n: int):
        if len(after) < n:
            return None
        b = after[n - 1]
        return {"d": b.d.isoformat(), "close": b.close, "pct": round(100 * (b.close - base.close) / base.close, 2)}

    first = after[0] if after else None
    avg = avg_volume(bars, first.d, window) if first else None
    return {"before": {"d": base.d.isoformat(), "close": base.close},
            "t1": leg(1), "t5": leg(5),
            "volume_x": round(first.volume / avg, 2) if first and avg else None,
            "label": "timing association, not cause"}
