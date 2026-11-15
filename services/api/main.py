"""FINN API. Brief, Portfolio and Alerts read stored data only, so they work with every source and model down."""
import os
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from ..engine import brief as brief_engine
from ..engine.alerts import avg_volume
from ..engine.config import company, holdings, load
from ..engine.eventprice import strip
from . import store

app = FastAPI(title="FINN", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("FINN_ORIGINS", "*").split(","), allow_methods=["*"], allow_headers=["*"])
WINDOWS = {"24h": 24, "3d": 72, "7d": 168}


def _now() -> datetime:
    """The Brief is anchored to the snapshot time, so a stale snapshot still shows its own last day."""
    g = store.meta().get("generated_at")
    return datetime.fromisoformat(g) if g else datetime.now()


@app.get("/health")
def health():
    m = store.meta()
    return {"ok": True, "snapshot": m.get("generated_at"), "sources": m.get("sources", {}),
            "llm": bool(os.getenv("GEMINI_API_KEY")), "store": "snapshot"}


@app.get("/brief")
def brief(window: str = "24h"):
    if window not in WINDOWS:
        raise HTTPException(400, f"window must be one of {list(WINDOWS)}")
    return brief_engine.build(store.filings(), store.alerts(), _now(), WINDOWS[window])


@app.get("/portfolio")
def portfolio():
    rows, week = [], _now().date().toordinal() - 7
    for sym, h in holdings().items():
        bars = store.prices().get(sym, [])
        last, prev = (bars[-1], bars[-2]) if len(bars) > 1 else (None, None)
        avg = avg_volume(bars, last.d, load("categories")["alerts"]["volume_window"]) if last else None
        recent = [f for f in store.filings() if f.symbol == sym and f.superseded_by is None and f.filed_at.date().toordinal() >= week]
        rows.append({"symbol": sym, "name": h["name"], "sector": h["sector"], "weight": h["weight"],
                     "close": last.close if last else None, "as_of": last.d.isoformat() if last else None,
                     "day_pct": round(100 * (last.close - prev.close) / prev.close, 2) if last else None,
                     "volume_x": round(last.volume / avg, 2) if last and avg else None,
                     "critical": sum(f.tier == "critical" for f in recent),
                     "pillars_touched": sorted({f.pillar for f in recent if f.pillar}),
                     "spark": [b.close for b in bars[-30:]]})
    return {"weights_note": "Illustrative demo weights, not real holdings.", "holdings": rows}


@app.get("/alerts")
def alerts():
    return [a.model_dump(mode="json") for a in store.alerts()]


@app.get("/rules")
def rules():
    return load("categories")["alerts"]


@app.get("/company/{symbol}")
def company_page(symbol: str):
    symbol = symbol.upper()
    c = company(symbol)
    if not c:
        raise HTTPException(404, f"{symbol} is not in the portfolio. Use /research/{symbol} for any NSE ticker.")
    bars = store.prices().get(symbol, [])
    fs = sorted((f for f in store.filings() if f.symbol == symbol and f.superseded_by is None), key=lambda f: f.filed_at, reverse=True)
    return {"symbol": symbol, "name": c["name"], "sector": c["sector"], "pillars": c.get("pillars", []),
            "prices": [b.model_dump(mode="json") for b in bars[-120:]],
            "filings": [{**f.model_dump(mode="json"), "event_price": strip(bars, f.filed_at) if f.tier != "routine" else None} for f in fs]}
