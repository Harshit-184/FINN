"""End-of-day prices from Yahoo Finance. One batched call for the whole portfolio. EOD only, by design."""
from ..engine.models import Bar


def eod(symbols: list[str], period: str = "6mo") -> dict[str, list[Bar]]:
    import yfinance as yf                      # imported here so the engine and API never need it
    df = yf.download([f"{s}.NS" for s in symbols], period=period, interval="1d", auto_adjust=True,
                     group_by="ticker", progress=False, threads=True)
    out: dict[str, list[Bar]] = {}
    for s in symbols:
        try:
            sub = df[f"{s}.NS"].dropna(subset=["Close"])
        except KeyError:
            out[s] = []
            continue
        out[s] = [Bar(d=i.date(), open=round(float(r.Open), 2), high=round(float(r.High), 2), low=round(float(r.Low), 2),
                      close=round(float(r.Close), 2), volume=float(r.Volume)) for i, r in sub.iterrows()]
    return out
