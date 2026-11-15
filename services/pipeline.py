"""Scheduled job: fetch -> dedupe -> classify -> score -> alerts -> write the snapshot.

    python -m services.pipeline --days 7

Run from a laptop or GitHub Actions (NSE blocks many cloud IPs). Every source is optional: if one fails
the run continues and meta.json records what was and was not fetched.
"""
import argparse, json
from datetime import date, datetime, timedelta
from pathlib import Path
import httpx
from .engine import alerts as alert_engine
from .engine.classify import classify
from .engine.config import holdings
from .engine.dedupe import dedupe
from .engine.models import Bar, Filing
from .engine.score import score
from .ingest import bse, nse, prices
from .ingest.http import SourceError

SNAP = Path(__file__).resolve().parents[1] / "data" / "snapshot"


def process(raw: list[Filing], bars: dict[str, list[Bar]], rules: dict | None = None):
    """Pure function over fetched data, so the acceptance tests can run it without a network."""
    filings = [score(classify(f)) for f in dedupe(raw)]
    found = alert_engine.filing_alerts(filings, rules)
    for sym, series in bars.items():
        for b in series[-10:]:
            found += alert_engine.price_volume_alerts(sym, series, b.d, rules)
    return filings, alert_engine.combine(found, filings)


def say(msg: str) -> None:
    """Progress to the console and to data/ingest_log.txt, so a silent window is never ambiguous."""
    print(msg, flush=True)
    log = SNAP.parent / "ingest_log.txt"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"{datetime.now():%H:%M:%S} {msg}\n")


def run(days: int) -> dict:
    end, start = date.today(), date.today() - timedelta(days=days)
    status: dict[str, str] = {}
    raw: list[Filing] = []
    say(f"FINN ingest {start} to {end}")
    try:
        say("prices: Yahoo Finance, one batched call...")
        bars = prices.eod(list(holdings()))
        status["prices"] = f"ok ({sum(1 for v in bars.values() if v)}/{len(bars)} symbols)"
    except Exception as e:                                     # yfinance raises many types
        bars, status["prices"] = {}, f"failed: {type(e).__name__}: {e}"
    say(f"prices: {status['prices']}")
    with httpx.Client(follow_redirects=True) as client:
        for name, fetch in (("nse", lambda h: nse.announcements(client, h["symbol"], start, end)),
                            ("bse", lambda h: bse.announcements(client, h["symbol"], h["bse_code"], start, end) if h.get("bse_code") else [])):
            ok = fail = 0
            last = ""
            for h in holdings().values():
                if fail >= 2 and ok == 0:                      # source is down or blocking us: stop, don't wait 18 times
                    break
                try:
                    got = fetch(h); raw += got; ok += 1
                    say(f"{name}: {h['symbol']} {len(got)} filings")
                except (SourceError, httpx.HTTPError, KeyError, ValueError) as e:
                    fail += 1; last = f"{type(e).__name__}: {e}"
                    say(f"{name}: {h['symbol']} FAILED {last}")
            status[name] = f"ok ({ok} symbols)" if not fail else f"{ok} ok, {fail} failed, last error: {last}"
    filings, alerts = process(raw, bars)
    SNAP.mkdir(parents=True, exist_ok=True)
    (SNAP / "filings.json").write_text(json.dumps([f.model_dump(mode="json") for f in filings], indent=1))
    (SNAP / "alerts.json").write_text(json.dumps([a.model_dump(mode="json") for a in alerts], indent=1))
    (SNAP / "prices.json").write_text(json.dumps({s: [b.model_dump(mode="json") for b in v] for s, v in bars.items()}))
    meta = {"generated_at": datetime.now().isoformat(timespec="seconds"), "from": start.isoformat(), "to": end.isoformat(),
            "sources": status, "filings_raw": len(raw), "filings_after_dedupe": len(filings),
            "sent_to_llm": sum(f.classified_by == "none" for f in filings)}
    (SNAP / "meta.json").write_text(json.dumps(meta, indent=1))
    say("done: " + json.dumps(meta))
    return meta


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    run(ap.parse_args().days)
