"""Builders for unit tests. Every value here is a made-up test input, not real company data.
Real, hand-verified filings live in tests/benchmark/ and are added during ingestion."""
from datetime import date, datetime, timedelta
from services.engine.models import Bar, Fact, Filing, GuidanceItem


def filing(subject, symbol="INFY", exchange="BSE", at="2026-11-13 18:05", raw="", body="", id=None, pdf=None):
    return Filing(id=id or f"{exchange}:{abs(hash((subject, at, exchange))) % 10**8}", symbol=symbol, exchange=exchange,
                  filed_at=datetime.fromisoformat(at), subject=subject, raw_category=raw, body=body, pdf_url=pdf)


def fact(metric, value, period, company="TEST", basis="consolidated", source="xbrl", **kw):
    return Fact(company=company, metric=metric, value=value, period=period, basis=basis, source_type=source, **kw)


def quarter(period, revenue, pbt, tax, pat, fin=10, dep=40, oi=20, **kw):
    vals = dict(revenue=revenue, pbt=pbt, tax=tax, pat=pat, finance_costs=fin, depreciation=dep, other_income=oi)
    return [fact(m, v, period, **kw) for m, v in vals.items()]


def bars(closes, volumes=None, start=date(2026, 10, 1)):
    volumes = volumes or [1000] * len(closes)
    out, d = [], start
    for c, v in zip(closes, volumes):
        while d.weekday() >= 5:
            d += timedelta(days=1)
        out.append(Bar(d=d, open=c, high=c, low=c, close=c, volume=v))
        d += timedelta(days=1)
    return out


def guide(metric, kind, low, high, period, stated_in, **kw):
    return GuidanceItem(company="TEST", metric=metric, kind=kind, low=low, high=high,
                        unit="PCT" if kind != "absolute" else "INR_CRORE", period=period, stated_in=stated_in,
                        quote="(test quote)", document="test.pdf", page=1, **kw)
